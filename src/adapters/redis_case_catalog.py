import re
from datetime import datetime

from src.domain.consolidated_report import CaseInfo, CaseSource

# Los ids de caso son uuid; restringir el formato evita que un id colisione con claves de lista (`c1:findings`).
CASE_ID_FORMAT = re.compile(r"[A-Za-z0-9_-]{1,128}")


class RedisCaseCatalog:
    def __init__(self, client) -> None:
        self._client = client

    def case(self, case_id: str) -> CaseInfo | None:
        if not CASE_ID_FORMAT.fullmatch(case_id):
            return None
        try:
            return self._read(case_id)
        except UnicodeDecodeError:
            # Bytes no UTF-8 en el hash: el caso no es legible, se trata como inexistente.
            return None

    def _read(self, case_id: str) -> CaseInfo | None:
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
    try:
        return datetime.fromisoformat(value) if value else None
    except ValueError:
        return None
