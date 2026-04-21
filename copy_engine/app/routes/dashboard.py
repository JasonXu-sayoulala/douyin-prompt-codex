from datetime import datetime, timedelta, timezone

from flask import Blueprint, render_template
from flask_login import login_required

from ..models import Content, CopyTemplate, Topic

dashboard_bp = Blueprint("dashboard", __name__)


def _today_range():
    now = datetime.now(timezone.utc)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return start, now


@dashboard_bp.route("/")
@login_required
def index():
    start, end = _today_range()

    topics_today = Topic.query.filter(Topic.created_at >= start, Topic.created_at <= end).count()
    contents_today = Content.query.filter(Content.created_at >= start, Content.created_at <= end).count()
    pending = Content.query.filter_by(status="pending_review").count()
    approved = Content.query.filter_by(status="approved").count()
    tpl_count = CopyTemplate.query.filter_by(is_active=True).count()

    return render_template(
        "dashboard.html",
        topics_today=topics_today,
        contents_today=contents_today,
        pending=pending,
        approved=approved,
        tpl_count=tpl_count,
    )
