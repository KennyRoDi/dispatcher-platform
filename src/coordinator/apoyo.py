from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from src.coordinator import conexion


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def str_or_empty(value: Any) -> str:
    """Safely coerce any value to string; None → empty string (Redis rejects None)."""
    if value is None:
        return ""
    return str(value)


def subtask_statuses(case_id: str) -> list[str | None]:
    """Statuses of every subtask of a case using the per-case list (no SCAN)."""
    subtask_ids = conexion.redis_client.lrange(f"case:{case_id}:subtasks", 0, -1)
    pipe = conexion.redis_client.pipeline()
    for sid in subtask_ids:
        pipe.hget(f"subtask:{sid}", "status")
    return pipe.execute()


def final_case_status(case_id: str) -> str:
    """
    completed → sin fallidas; failed → todas fallidas;
    partially_completed → al menos una fallida y al menos una completada.
    """
    statuses = subtask_statuses(case_id)
    failed = sum(1 for s in statuses if s == "failed")
    completed = sum(1 for s in statuses if s == "completed")
    if failed == 0:
        return "completed"
    if completed == 0:
        return "failed"
    return "partially_completed"


TERMINAL_CASE_STATUSES = frozenset(
    {"completed", "partially_completed", "failed", "cancelled"}
)


def fetch_subtasks(case_id: str) -> list[dict]:
    """
    Fetch all subtask hashes for a case using the pre-stored list.
    O(N) with one pipeline — no SCAN required.
    """
    subtask_ids = conexion.redis_client.lrange(f"case:{case_id}:subtasks", 0, -1)
    if not subtask_ids:
        return []
    pipe = conexion.redis_client.pipeline()
    for sid in subtask_ids:
        pipe.hgetall(f"subtask:{sid}")
    results = pipe.execute()
    return [r for r in results if r]


def float_or_none(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def int_or_none(value: str | None) -> int | None:
    if not value:
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def json_list(value: str | None) -> list:
    if not value:
        return []
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


def json_dict(value: str | None) -> dict:
    if not value:
        return {}
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, dict) else {}
    except (json.JSONDecodeError, TypeError):
        return {}
