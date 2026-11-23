"""Shared request dependencies."""

import re

from fastapi import Header, HTTPException, status

# Anonymous learner id chosen by the client (a UUID in the web app). Kept
# strict so it is safe as a storage key. Real auth will replace this header.
LEARNER_ID_PATTERN = re.compile(r"^[A-Za-z0-9-]{8,64}$")
INVALID_LEARNER_ID = "Send a valid X-Learner-Id header (8-64 letters, digits or dashes)"


def _validate(learner_id: str | None) -> str | None:
    if learner_id is None:
        return None
    if not LEARNER_ID_PATTERN.match(learner_id):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, INVALID_LEARNER_ID)
    return learner_id


def require_learner_id(x_learner_id: str | None = Header(None)) -> str:
    learner_id = _validate(x_learner_id)
    if learner_id is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, INVALID_LEARNER_ID)
    return learner_id


def optional_learner_id(x_learner_id: str | None = Header(None)) -> str | None:
    """Endpoints that also serve untracked clients (no header) use this."""
    return _validate(x_learner_id)
