from __future__ import annotations

from collections import defaultdict


def resumen_por_nodo(workers: list[dict] | None) -> list[dict]:
    """Agrupa los heartbeats de `GET /workers` por `host` (RF-17); sin Streamlit, para probarla sola."""
    por_nodo: dict[str, list[dict]] = defaultdict(list)
    for trabajador in workers or []:
        por_nodo[trabajador.get("host") or "desconocido"].append(trabajador)
    return [_resumir(nodo, trabajadores) for nodo, trabajadores in sorted(por_nodo.items())]


def _resumir(nodo: str, trabajadores: list[dict]) -> dict:
    vivos = [t for t in trabajadores if t.get("alive")]
    usado = _suma(vivos, "cgroup_memory_current")
    limite = _suma(vivos, "cgroup_memory_max")
    con_gpu = [t for t in vivos if t.get("gpu") not in (None, "", "none", "unknown")]
    return {
        "nodo": nodo,
        "workers": len(trabajadores),
        "workers_vivos": len(vivos),
        "activas": int(_suma(vivos, "active_subtasks") or 0),
        "cpu_percent": _promedio(vivos, "cpu_percent"),
        "mem_percent": _promedio(vivos, "mem_percent"),
        "cgroup_memory_current": usado,
        "cgroup_memory_max": limite,
        "cgroup_percent": round(100 * usado / limite, 1) if usado is not None and limite else None,
        "gpu": con_gpu[0]["gpu"] if con_gpu else (vivos[0].get("gpu") if vivos else None),
        "gpu_percent": _promedio(con_gpu, "gpu_percent"),
    }


def _numeros(trabajadores: list[dict], campo: str) -> list[float]:
    valores = []
    for trabajador in trabajadores:
        try:
            valores.append(float(trabajador.get(campo)))
        except (TypeError, ValueError):
            continue
    return valores


def _suma(trabajadores: list[dict], campo: str) -> int | None:
    valores = _numeros(trabajadores, campo)
    return int(sum(valores)) if valores else None


def _promedio(trabajadores: list[dict], campo: str) -> float | None:
    valores = _numeros(trabajadores, campo)
    return round(sum(valores) / len(valores), 1) if valores else None
