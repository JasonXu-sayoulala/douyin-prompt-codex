import os
import sys

from flask import Flask

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

try:
    from dotenv import load_dotenv

    load_dotenv(os.path.join(_ROOT, ".env"))
except ImportError:
    pass

from sqlalchemy import text

from config import Config

from .extensions import db, login_manager
from .models import User
from .services.llm_service import LLMService
from .services.risk_service import RiskService
from .services.media_generation_service import media_service as media_service_singleton


def create_app(config_object=None):
    app = Flask(__name__)
    app.config.from_object(config_object or Config)

    os.makedirs(app.config["INSTANCE_PATH"], exist_ok=True)

    # SQLAlchemy 2 + SQLite：insertmanyvalues 批量插入多行时，RETURNING id 与自增主键
    # 在部分环境（如 Python 3.14 + sqlite）会触发 NOT NULL failed on *.id
    db_uri = str(app.config.get("SQLALCHEMY_DATABASE_URI") or "")
    if db_uri.startswith("sqlite"):
        eng_opts = dict(app.config.get("SQLALCHEMY_ENGINE_OPTIONS") or {})
        eng_opts.setdefault("insertmanyvalues_page_size", 1)
        app.config["SQLALCHEMY_ENGINE_OPTIONS"] = eng_opts

    db.init_app(app)
    login_manager.init_app(app)

    llm = LLMService()
    llm.init_app(app)
    risk = RiskService()
    risk.init_app(app)
    # 必须与 routes 里用的是同一实例，否则模块级 media_service 未 init_app，_output_dir 为 None
    media_service_singleton.init_app(app)
    app.extensions["llm_service"] = llm
    app.extensions["risk_service"] = risk
    app.extensions["media_service"] = media_service_singleton

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    from .routes.auth import auth_bp
    from .routes.dashboard import dashboard_bp
    from .routes.topics import topics_bp
    from .routes.contents import contents_bp
    from .routes.reviews import reviews_bp
    from .routes.prompt_templates import templates_bp
    from .routes.media import bp as media_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(topics_bp, url_prefix="/topics")
    app.register_blueprint(contents_bp, url_prefix="/contents")
    app.register_blueprint(reviews_bp, url_prefix="/reviews")
    app.register_blueprint(templates_bp, url_prefix="/templates")
    app.register_blueprint(media_bp, url_prefix="/media")

    with app.app_context():
        db.create_all()
        _repair_sqlite_schema_if_needed()
        _seed_if_empty()

    return app


def _repair_sqlite_schema_if_needed() -> None:
    """若核心表缺失或 id 不是主键，SQLite 自增会失效；此时整库重建。"""
    uri = str(db.engine.url)
    if not uri.startswith("sqlite"):
        return

    _tables = (
        "users",
        "templates",
        "topics",
        "contents",
        "rewrite_logs",
        "review_records",
        "operation_logs",
    )

    def _id_is_primary_key(table: str) -> bool:
        """表存在且存在名为 id 的主键列时为 True。"""
        assert table in _tables
        with db.engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name=:t LIMIT 1"
                ),
                {"t": table},
            ).first()
            if not row:
                return False
            rows = conn.execute(text(f'PRAGMA table_info("{table}")')).fetchall()
        for r in rows:
            if r[1] == "id":
                return r[5] == 1
        return False

    if not all(_id_is_primary_key(t) for t in _tables):
        db.drop_all()
        db.create_all()


def _seed_if_empty():
    from .models import CopyTemplate, User

    if User.query.first():
        return

    admin = User(id=1, username="admin", role="admin")
    admin.set_password("admin123")
    db.session.add(admin)

    op = User(id=2, username="operator", role="operator")
    op.set_password("operator123")
    db.session.add(op)

    cr = User(id=3, username="creator", role="creator")
    cr.set_password("creator123")
    db.session.add(cr)
    db.session.flush()

    defaults = [
        ("强冲突开场", "strong_conflict", "开头直接对立，双方都有理由，引导站队。"),
        ("委屈共鸣型", "委屈共鸣", "第一人称委屈叙事，细节真实，不求对错求理解。"),
        ("现实扎心型", "现实扎心", "金钱/面子/家庭现实，一句点破。"),
        ("反转型", "反转型", "前半认同情绪，后半轻量反转。"),
        ("站队争议型", "站队争议", "明确两种选择，评论区吵架。"),
        ("聊天截图型", "chat", "适合伪聊天记录：短句、已读未回、表情包位。"),
    ]
    for i, (name, ttype, desc) in enumerate(defaults, start=1):
        db.session.add(
            CopyTemplate(
                id=i,
                name=name,
                template_type=ttype,
                prompt=f"结构提示：{desc}\n写作时突出情绪节奏与留白。",
                description=desc,
                is_active=True,
            )
        )
        db.session.flush()

    db.session.commit()
