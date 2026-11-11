from datetime import datetime

from src.domain.consolidated_report import CaseInfo, CaseSource


class RedisCaseCatalog:
    def __init__(self, client) -> None:
        self._client = client

    def case(self, case_id: str) -> CaseInfo | None:
        case = self._client.hgetall(f"case:{case_id}")
        if not case:
            return None
        return CaseInfo(
            case_id,
            case.get("status", ""),
            _instant(case.get("created_at")),
            _instant(case.get("finished_at")),
            self._sources(case_id),
        )

    def _sources(self, case_id: str) -> tuple[CaseSource, ...]:
        ids = self._client.lrange(f"case:{case_id}:subtasks", 0, -1)
        pipe = self._client.pipeline()
        for subtask_id in ids:
            pipe.hgetall(f"subtask:{subtask_id}")
        return tuple(_source(h) for h in pipe.execute() if h)


def _source(subtask: dict) -> CaseSource:
    return CaseSource(
        sha256=subtask.get("source_sha256", ""),
        file_path=subtask.get("file_path", ""),
        # El hash real de la sub-tarea trae task_type (operación); `kind` solo si alguien lo agrega.
        kind=subtask.get("kind") or subtask.get("task_type", ""),
        status=subtask.get("status", ""),
        error_type=subtask.get("error_type") or None,
    )


def _instant(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None
