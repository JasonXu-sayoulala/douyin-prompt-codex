from datetime import datetime, timezone

from flask_login import UserMixin
from sqlalchemy import Integer, event, text
from sqlalchemy.orm import Session, object_session
from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db


def utcnow():
    return datetime.now(timezone.utc)


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(50), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="creator")
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


class Topic(db.Model):
    __tablename__ = "topics"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    title = db.Column(db.String(255), nullable=False)
    category = db.Column(db.String(50))
    tags = db.Column(db.String(255))
    emotion_level = db.Column(db.Integer, default=3)
    source = db.Column(db.String(100))
    status = db.Column(db.String(20), default="draft", nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    contents = db.relationship("Content", backref="topic", lazy="dynamic")


class CopyTemplate(db.Model):
    """提示词模板（表名 templates，避免与 Jinja2 Template 类名冲突）"""

    __tablename__ = "templates"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(100), nullable=False)
    template_type = db.Column(db.String(30))
    prompt = db.Column(db.Text, nullable=False)
    description = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    contents = db.relationship("Content", backref="copy_template", lazy="dynamic")


class Content(db.Model):
    __tablename__ = "contents"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    topic_id = db.Column(db.Integer, db.ForeignKey("topics.id"), nullable=False, index=True)
    template_id = db.Column(db.Integer, db.ForeignKey("templates.id"), index=True)
    title = db.Column(db.Text)
    body = db.Column(db.Text)
    comment_hook = db.Column(db.Text)
    cover_text = db.Column(db.Text)
    content_type = db.Column(db.String(20), default="chat")
    version_no = db.Column(db.Integer, default=1, nullable=False)
    status = db.Column(db.String(20), default="generated", nullable=False)
    risk_level = db.Column(db.String(20), default="low", nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), index=True)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    author = db.relationship("User", foreign_keys=[created_by])
    rewrite_logs = db.relationship("RewriteLog", backref="content", lazy="dynamic", cascade="all, delete-orphan")
    review_records = db.relationship("ReviewRecord", backref="content", lazy="dynamic", cascade="all, delete-orphan")


class RewriteLog(db.Model):
    __tablename__ = "rewrite_logs"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    content_id = db.Column(db.Integer, db.ForeignKey("contents.id"), nullable=False, index=True)
    action = db.Column(db.String(50), nullable=False)
    before_text = db.Column(db.Text)
    after_text = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)


class ReviewRecord(db.Model):
    __tablename__ = "review_records"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    content_id = db.Column(db.Integer, db.ForeignKey("contents.id"), nullable=False, index=True)
    reviewer_id = db.Column(db.Integer, db.ForeignKey("users.id"), index=True)
    review_status = db.Column(db.String(20), default="pending", nullable=False)
    review_note = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    reviewer = db.relationship("User", foreign_keys=[reviewer_id])


class OperationLog(db.Model):
    __tablename__ = "operation_logs"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), index=True)
    action = db.Column(db.String(50), nullable=False)
    target_type = db.Column(db.String(30))
    target_id = db.Column(db.Integer)
    detail = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    user = db.relationship("User", foreign_keys=[user_id])


_SQLITE_PK_MEMO: dict[tuple[int, str], int] = {}


def _sqlite_assign_integer_pk(mapper, connection, target) -> None:
    """部分环境（如 Python 3.14 + SQLite）下 INTEGER 主键自增不生效；用库内 MAX + 会话内递增避免同次 flush 重复。"""
    if connection.dialect.name != "sqlite":
        return
    pks = mapper.primary_key
    if len(pks) != 1:
        return
    col = pks[0]
    if not isinstance(col.type, Integer):
        return
    key = col.key
    if getattr(target, key, None) is not None:
        return
    tablename = mapper.local_table.name
    raw_max = int(
        connection.execute(
            text(f'SELECT COALESCE(MAX("{key}"), 0) FROM "{tablename}"')
        ).scalar()
        or 0
    )
    sess = object_session(target)
    if sess is None:
        setattr(target, key, raw_max + 1)
        return
    cache_key = (id(sess), tablename)
    prev = _SQLITE_PK_MEMO.get(cache_key, raw_max)
    nxt = max(raw_max, prev) + 1
    _SQLITE_PK_MEMO[cache_key] = nxt
    setattr(target, key, nxt)


@event.listens_for(Session, "after_commit")
@event.listens_for(Session, "after_rollback")
def _sqlite_pk_memo_cleanup(session: Session) -> None:
    sid = id(session)
    for k in list(_SQLITE_PK_MEMO):
        if k[0] == sid:
            del _SQLITE_PK_MEMO[k]


for _model in (
    User,
    Topic,
    CopyTemplate,
    Content,
    RewriteLog,
    ReviewRecord,
    OperationLog,
):
    event.listen(_model, "before_insert", _sqlite_assign_integer_pk)
