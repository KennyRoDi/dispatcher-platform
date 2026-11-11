from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class ProcessMemory:
    rss_bytes: int
    pss_bytes: int
    raw: str = field(default="", compare=False, repr=False)


@dataclass(frozen=True)
class CgroupMemory:
    memory_current: int
    memory_max: int
    memory_swap_max: int | None
    raw: dict[str, str] = field(default_factory=dict, compare=False, repr=False)


def parse_smaps_rollup(text: str) -> ProcessMemory:
    values: dict[str, int] = {}
    for line in text.splitlines():
        parts = line.split()
        if len(parts) < 3 or parts[0] not in ("Rss:", "Pss:"):
            continue
        key = parts[0][:-1]
        if key in values or parts[2] != "kB":
            raise ValueError(f"lectura {key} inválida")
        try:
            value = int(parts[1])
        except ValueError as error:
            raise ValueError(f"lectura {key} inválida") from error
        if value < 0:
            raise ValueError(f"lectura {key} inválida")
        values[key] = value * 1024
    if set(values) != {"Rss", "Pss"}:
        raise ValueError("smaps_rollup debe contener Rss y Pss")
    if values["Pss"] > values["Rss"]:
        raise ValueError("Pss no puede superar Rss")
    return ProcessMemory(rss_bytes=values["Rss"], pss_bytes=values["Pss"], raw=text)


def read_process_memory(pid: int, proc_root: Path = Path("/proc")) -> ProcessMemory:
    if type(pid) is not int or pid <= 0:
        raise ValueError("pid debe ser entero positivo")
    path = proc_root / str(pid) / "smaps_rollup"
    return parse_smaps_rollup(path.read_text(encoding="utf-8"))


def read_cgroup_memory(cgroup_root: Path = Path("/sys/fs/cgroup")) -> CgroupMemory:
    raw = {
        name: (cgroup_root / name).read_text(encoding="utf-8").strip()
        for name in ("memory.current", "memory.max", "memory.swap.max")
    }
    current = _integer(raw["memory.current"], "memory.current")
    limit = _integer(raw["memory.max"], "memory.max")
    swap_max = None if raw["memory.swap.max"] == "max" else _integer(
        raw["memory.swap.max"], "memory.swap.max"
    )
    if limit <= 0:
        raise ValueError("memory.max debe ser un límite positivo y finito")
    if swap_max != 0:
        raise ValueError("memory.swap.max debe ser cero")
    return CgroupMemory(current, limit, swap_max, raw)


def _integer(value: str, name: str) -> int:
    try:
        parsed = int(value)
    except ValueError as error:
        raise ValueError(f"{name} inválido") from error
    if parsed < 0:
        raise ValueError(f"{name} inválido")
    return parsed
