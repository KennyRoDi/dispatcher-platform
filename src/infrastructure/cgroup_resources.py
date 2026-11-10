from pathlib import Path

from src.domain.resources import ResourceUsage


class CgroupResourceReader:
    def __init__(self, *, cgroup_path: str | Path, worker_id: str) -> None:
        self._cgroup_path = Path(cgroup_path)
        self._worker_id = worker_id

    def _read_bytes(self, filename: str, minimum: int) -> int:
        path = self._cgroup_path / filename
        content = path.read_text(encoding="utf-8").strip()
        if not content.isascii() or not content.isdecimal():
            raise ValueError(f"{path} debe contener un entero en bytes")
        value = int(content)
        if value < minimum:
            raise ValueError(f"{path} debe ser de al menos {minimum} bytes")
        return value

    def read(self) -> ResourceUsage:
        return ResourceUsage(
            worker_id=self._worker_id,
            memory_current=self._read_bytes("memory.current", 0),
            memory_max=self._read_bytes("memory.max", 1),
        )
