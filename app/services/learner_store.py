"""Learner persistence: profile, lesson progress, daily question counts.

``LearnerRepository`` is the seam for a future Supabase/Postgres backend: the
API layer only uses these methods, so swapping storage means writing one new
class and returning it from ``get_learner_repository``. The SQLite version
uses the standard library only and keeps one connection guarded by a lock
(FastAPI runs sync handlers in a threadpool).

Learners are anonymous for now: the client sends a random ``X-Learner-Id``.
With real auth, that id becomes the authenticated user id.
"""

import json
import sqlite3
import threading
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Protocol

from app.core.config import settings


class LearnerRepository(Protocol):
    def get_profile(self, learner_id: str) -> dict | None: ...

    def save_profile(self, learner_id: str, profile: dict) -> None: ...

    def mark_lesson_complete(self, learner_id: str, course_id: str, step_id: str) -> None: ...

    def mark_lesson_incomplete(self, learner_id: str, course_id: str, step_id: str) -> None: ...

    def completed_steps(self, learner_id: str, course_id: str) -> list[str]: ...

    def all_completed(self, learner_id: str) -> dict[str, list[str]]: ...

    def questions_used(self, learner_id: str, day: str) -> int: ...

    def record_question(self, learner_id: str, day: str) -> int: ...


SCHEMA = """
CREATE TABLE IF NOT EXISTS learner_profiles (
    learner_id TEXT PRIMARY KEY,
    profile_json TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS lesson_progress (
    learner_id TEXT NOT NULL,
    course_id TEXT NOT NULL,
    step_id TEXT NOT NULL,
    completed_at TEXT NOT NULL,
    PRIMARY KEY (learner_id, course_id, step_id)
);
CREATE TABLE IF NOT EXISTS question_usage (
    learner_id TEXT NOT NULL,
    day TEXT NOT NULL,
    count INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (learner_id, day)
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _step_key(step_id: str):
    # "1.10" sorts after "1.9": compare numeric parts as numbers.
    # Tagged tuples keep mixed ids ("1.2", "old-step") comparable.
    return [(0, int(part), "") if part.isdigit() else (1, 0, part) for part in step_id.replace("-", ".").split(".")]


class SQLiteLearnerRepository:
    def __init__(self, path: str):
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._lock = threading.Lock()
        with self._lock, self._conn:
            self._conn.executescript(SCHEMA)

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def _all(self, sql: str, params: tuple) -> list[tuple]:
        with self._lock:
            return self._conn.execute(sql, params).fetchall()

    def _write(self, sql: str, params: tuple) -> None:
        with self._lock, self._conn:
            self._conn.execute(sql, params)

    def get_profile(self, learner_id: str) -> dict | None:
        rows = self._all("SELECT profile_json FROM learner_profiles WHERE learner_id = ?", (learner_id,))
        return json.loads(rows[0][0]) if rows else None

    def save_profile(self, learner_id: str, profile: dict) -> None:
        self._write(
            "INSERT INTO learner_profiles (learner_id, profile_json, updated_at) VALUES (?, ?, ?) "
            "ON CONFLICT(learner_id) DO UPDATE SET profile_json = excluded.profile_json, updated_at = excluded.updated_at",
            (learner_id, json.dumps(profile, ensure_ascii=False), _now()),
        )

    def mark_lesson_complete(self, learner_id: str, course_id: str, step_id: str) -> None:
        self._write(
            "INSERT OR IGNORE INTO lesson_progress (learner_id, course_id, step_id, completed_at) VALUES (?, ?, ?, ?)",
            (learner_id, course_id, step_id, _now()),
        )

    def mark_lesson_incomplete(self, learner_id: str, course_id: str, step_id: str) -> None:
        self._write(
            "DELETE FROM lesson_progress WHERE learner_id = ? AND course_id = ? AND step_id = ?",
            (learner_id, course_id, step_id),
        )

    def completed_steps(self, learner_id: str, course_id: str) -> list[str]:
        rows = self._all(
            "SELECT step_id FROM lesson_progress WHERE learner_id = ? AND course_id = ?", (learner_id, course_id)
        )
        return sorted((r[0] for r in rows), key=_step_key)

    def all_completed(self, learner_id: str) -> dict[str, list[str]]:
        rows = self._all("SELECT course_id, step_id FROM lesson_progress WHERE learner_id = ?", (learner_id,))
        result: dict[str, list[str]] = {}
        for course_id, step_id in rows:
            result.setdefault(course_id, []).append(step_id)
        return {course: sorted(steps, key=_step_key) for course, steps in sorted(result.items())}

    def questions_used(self, learner_id: str, day: str) -> int:
        rows = self._all("SELECT count FROM question_usage WHERE learner_id = ? AND day = ?", (learner_id, day))
        return rows[0][0] if rows else 0

    def record_question(self, learner_id: str, day: str) -> int:
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO question_usage (learner_id, day, count) VALUES (?, ?, 1) "
                "ON CONFLICT(learner_id, day) DO UPDATE SET count = count + 1",
                (learner_id, day),
            )
            return self._conn.execute(
                "SELECT count FROM question_usage WHERE learner_id = ? AND day = ?", (learner_id, day)
            ).fetchone()[0]


@lru_cache(maxsize=1)
def _default_repository() -> SQLiteLearnerRepository:
    return SQLiteLearnerRepository(settings.LEARNER_DB_PATH)


def get_learner_repository() -> LearnerRepository:
    """FastAPI dependency (override it in tests or to plug in another backend)."""
    return _default_repository()
