from datetime import datetime, timezone

from sqlalchemy import Integer, event, text
from sqlalchemy.orm import Session, object_session

from .extensions import db


def utcnow():
    return datetime.now(timezone.utc)


class RenderJob(db.Model):
    __tablename__ = "render_jobs"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    content_id = db.Column(db.Integer, db.ForeignKey("contents.id"), nullable=False, index=True)
    provider = db.Column(db.String(32), nullable=False, default="dsp")
    job_type = db.Column(db.String(32), nullable=False, default="single_video")
    status = db.Column(db.String(32), nullable=False, default="queued", index=True)
    priority = db.Column(db.Integer, nullable=False, default=5)

    request_payload_json = db.Column(db.JSON)
    latest_response_json = db.Column(db.JSON)

    external_job_id = db.Column(db.String(128), index=True)
    external_trace_id = db.Column(db.String(128))

    retry_count = db.Column(db.Integer, nullable=False, default=0)
    error_code = db.Column(db.String(64))
    error_message = db.Column(db.Text)

    submitted_by = db.Column(db.Integer, db.ForeignKey("users.id"), index=True)
    started_at = db.Column(db.DateTime)
    finished_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    content = db.relationship("Content", backref=db.backref("render_jobs", lazy="dynamic", cascade="all, delete-orphan"))
    submitter = db.relationship("User", foreign_keys=[submitted_by])
    media_assets = db.relationship("MediaAsset", backref="render_job", lazy="dynamic", cascade="all, delete-orphan")
    storyboard_scenes = db.relationship("StoryboardScene", backref="render_job", lazy="dynamic", cascade="all, delete-orphan")


class MediaAsset(db.Model):
    __tablename__ = "media_assets"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    render_job_id = db.Column(db.Integer, db.ForeignKey("render_jobs.id"), nullable=False, index=True)
    content_id = db.Column(db.Integer, db.ForeignKey("contents.id"), nullable=False, index=True)

    asset_type = db.Column(db.String(32), nullable=False, index=True)
    source_type = db.Column(db.String(32), nullable=False, default="generated")
    provider = db.Column(db.String(32), nullable=False, default="dsp")

    label = db.Column(db.String(128))
    file_url = db.Column(db.Text)
    local_path = db.Column(db.Text)
    storage_key = db.Column(db.String(255))
    mime_type = db.Column(db.String(64))

    duration_seconds = db.Column(db.Numeric(10, 2))
    file_size_bytes = db.Column(db.BigInteger)
    checksum = db.Column(db.String(128))

    metadata_json = db.Column(db.JSON)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    content = db.relationship("Content", backref=db.backref("media_assets", lazy="dynamic", cascade="all, delete-orphan"))


class StoryboardScene(db.Model):
    __tablename__ = "storyboard_scenes"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    render_job_id = db.Column(db.Integer, db.ForeignKey("render_jobs.id"), nullable=False, index=True)
    content_id = db.Column(db.Integer, db.ForeignKey("contents.id"), nullable=False, index=True)

    seq_no = db.Column(db.Integer, nullable=False, index=True)
    scene_id = db.Column(db.String(64), nullable=False)
    duration_seconds = db.Column(db.Integer, nullable=False, default=3)

    narration = db.Column(db.Text)
    onscreen_text = db.Column(db.Text)
    shot_type = db.Column(db.String(64))
    transition_name = db.Column(db.String(64))
    objective = db.Column(db.Text)

    visual_prompt = db.Column(db.Text)
    negative_prompt = db.Column(db.Text)
    camera_motion = db.Column(db.Text)

    metadata_json = db.Column(db.JSON)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    __table_args__ = (
        db.UniqueConstraint("render_job_id", "scene_id", name="uk_storyboard_scene"),
    )

    content = db.relationship("Content", backref=db.backref("storyboard_scenes", lazy="dynamic", cascade="all, delete-orphan"))


class AudioTrack(db.Model):
    __tablename__ = "audio_tracks"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    title = db.Column(db.String(255), nullable=False)
    artist = db.Column(db.String(255))
    platform = db.Column(db.String(32), nullable=False, default="douyin", index=True)
    source_type = db.Column(db.String(32), nullable=False, default="hot_music", index=True)

    mood_tag = db.Column(db.String(64))
    bpm = db.Column(db.Integer)
    use_count = db.Column(db.BigInteger)
    rank_no = db.Column(db.Integer, index=True)

    share_url = db.Column(db.Text)
    cover_url = db.Column(db.Text)
    external_ref = db.Column(db.String(128), index=True)

    metadata_json = db.Column(db.JSON)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow, nullable=False)


_SQLITE_PK_MEMO: dict[tuple[int, str], int] = {}


def _sqlite_assign_integer_pk(mapper, connection, target) -> None:
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
    RenderJob,
    MediaAsset,
    StoryboardScene,
    AudioTrack,
):
    event.listen(_model, "before_insert", _sqlite_assign_integer_pk)
