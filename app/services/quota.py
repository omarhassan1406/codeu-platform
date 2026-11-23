"""Daily question quota (freemium: DAILY_QUESTION_LIMIT questions per UTC day)."""

from datetime import datetime, timedelta, timezone

from app.core.config import settings
from app.schemas.learners import QuotaStatus
from app.services.learner_store import LearnerRepository


def utc_day(now: datetime | None = None) -> str:
    return (now or datetime.now(timezone.utc)).astimezone(timezone.utc).date().isoformat()


def quota_status(repo: LearnerRepository, learner_id: str, now: datetime | None = None) -> QuotaStatus:
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    used = repo.questions_used(learner_id, utc_day(now))
    limit = settings.DAILY_QUESTION_LIMIT or None
    tomorrow = datetime.combine(now.date() + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc)
    return QuotaStatus(
        limit=limit,
        used=used,
        remaining=None if limit is None else max(0, limit - used),
        resets_at=tomorrow.isoformat(),
    )


def limit_message(limit: int) -> str:
    return (
        f"You've used your {limit} free questions for today. "
        "They reset at midnight UTC; you can keep studying the lessons meanwhile."
    )
