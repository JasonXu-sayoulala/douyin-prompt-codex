import os
import sys

from flask import Flask
from sqlalchemy import text

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(_ROOT, ".env"))
except ImportError:
    pass

from config import Config

from .extensions import csrf, db, login_manager
from .models import User
from .services.llm_service import LLMService
from .services.risk_service import RiskService
from .services.media_generation_service import media_service as media_service_singleton
from .security import register_error_handlers


def create_app(config_object=None):
    app = Flask(__name__)
    app.config.from_object(config_object or Config)
    os.makedirs(app.config["INSTANCE_PATH"], exist_ok=True)

    db_uri = str(app.config.get("SQLALCHEMY_DATABASE_URI") or "")
    if db_uri.startswith("sqlite"):
        eng_opts = dict(app.config.get("SQLALCHEMY_ENGINE_OPTIONS") or {})
        eng_opts.setdefault("insertmanyvalues_page_size", 1)
        app.config["SQLALCHEMY_ENGINE_OPTIONS"] = eng_opts

    db.init_app(app)
    csrf.init_app(app)
    login_manager.init_app(app)

    llm = LLMService()
    llm.init_app(app)
    risk = RiskService()
    risk.init_app(app)
    media_service_singleton.init_app(app)
    app.extensions["llm_service"] = llm
    app.extensions["risk_service"] = risk
    app.extensions["media_service"] = media_service_singleton

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    register_error_handlers(app)

    from .routes.auth import auth_bp
    from .routes.dashboard import dashboard_bp
    from .routes.topics import topics_bp
    from .routes.contents import contents_bp
    from .routes.reviews import reviews_bp
    from .routes.prompt_templates import templates_bp
    from .routes.media import bp as media_bp
    from .routes.materials import materials_bp
    from .routes.render_jobs import render_jobs_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(topics_bp, url_prefix="/topics")
    app.register_blueprint(contents_bp, url_prefix="/contents")
    app.register_blueprint(reviews_bp, url_prefix="/reviews")
    app.register_blueprint(templates_bp, url_prefix="/templates")
    app.register_blueprint(media_bp, url_prefix="/media")
    app.register_blueprint(materials_bp, url_prefix="/materials")
    app.register_blueprint(render_jobs_bp)

    @app.get("/healthz")
    def healthz():
        return {"ok": True}

    with app.app_context():
        from . import models_rendering  # noqa: F401
        db.create_all()
        _repair_sqlite_schema_if_needed()
        _seed_if_empty()

    return app


def _repair_sqlite_schema_if_needed() -> None:
    uri = str(db.engine.url)
    if not uri.startswith("sqlite"):
        return

    tables = (
        "users",
        "templates",
        "topics",
        "contents",
        "source_materials",
        "material_insights",
        "rewrite_logs",
        "review_records",
        "operation_logs",
        "render_jobs",
        "media_assets",
        "storyboard_scenes",
        "audio_tracks",
    )

    def _id_is_primary_key(table: str) -> bool:
        with db.engine.connect() as conn:
            row = conn.execute(
                text("SELECT 1 FROM sqlite_master WHERE type='table' AND name=:t LIMIT 1"),
                {"t": table},
            ).first()
            if not row:
                return False
            rows = conn.execute(text(f'PRAGMA table_info("{table}")')).fetchall()
        for r in rows:
            if r[1] == "id":
                return r[5] == 1
        return False

    if not all(_id_is_primary_key(t) for t in tables):
        db.drop_all()
        db.create_all()


def _seed_if_empty():
    return
