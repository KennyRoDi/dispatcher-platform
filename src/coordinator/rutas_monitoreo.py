from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any

import redis as redis_lib
from fastapi import APIRouter, HTTPException

from src.coordinator import conexion
from src.coordinator.apoyo import (
    float_or_none,
    int_or_none,
)
from src.coordinator.conexion import redis_unavailable
from src.coordinator.router import VALID_TASK_TYPES, queue_key

logger = logging.getLogger(__name__)
router = APIRouter()


def _worker_entries() -> list[dict]:
    worker_ids = sorted(conexion.redis_client.smembers("workers:registry"))
    entries = []
    for wid in worker_ids:
        heartbeat = conexion.redis_client.hgetall(f"worker:{wid}")
        entries.append({**heartbeat, "worker_id": wid, "alive": bool(heartbeat)})
    return entries


@router.get("/health", response_model=dict, tags=["Dashboard"])
def health_check() -> dict:
    """Comprueba que el coordinador puede alcanzar Redis."""
    try:
        conexion.redis_client.ping()
        return {"status": "ok", "redis": f"{conexion.REDIS_HOST}:{conexion.REDIS_PORT}"}
    except (redis_lib.exceptions.ConnectionError, redis_lib.exceptions.TimeoutError) as e:
        raise HTTPException(
            status_code=503,
            detail=f"Redis no disponible en {conexion.REDIS_HOST}:{conexion.REDIS_PORT} — {e}",
        )


@router.get("/workers", response_model=list, tags=["Dashboard"])
def list_workers() -> list:
    """Workers from ``workers:registry``; ``alive`` = heartbeat key still exists."""
    try:
        return _worker_entries()
    except redis_lib.exceptions.ConnectionError as e:
        raise redis_unavailable(e)


@router.get("/stats", response_model=dict, tags=["Dashboard"])
def get_stats() -> dict:
    """Queue lengths, cases by status and worker liveness."""
    try:
        queues: dict[str, int] = {}
        for op in sorted(VALID_TASK_TYPES):
            for key in (queue_key(op), queue_key(op, "high")):
                queues[key] = conexion.redis_client.llen(key)

        cases_by_status: dict[str, int] = defaultdict(int)
        for cid in conexion.redis_client.smembers("cases:registry"):
            st = conexion.redis_client.hget(f"case:{cid}", "status")
            if st:
                cases_by_status[st] += 1

        workers = _worker_entries()
        alive = [w for w in workers if w["alive"]]
        return {
            "queues": queues,
            "cases_by_status": dict(cases_by_status),
            "workers_alive": len(alive),
            "workers_total": len(workers),
            "subtasks_active": sum(int_or_none(w.get("active_subtasks")) or 0 for w in alive),
        }
    except redis_lib.exceptions.ConnectionError as e:
        raise redis_unavailable(e)


@router.get("/hardware", response_model=list, tags=["Dashboard"])
def get_hardware() -> list:
    """
    Return a lightweight hardware snapshot for every *alive* worker.

    Fields
    ------
    worker_id, host, ip          — identity
    cpu_percent                  — CPU utilization reported by last heartbeat
    mem_percent                  — RAM utilization reported by last heartbeat
    mem_total_gb                 — total physical RAM in GiB (if published)
    cpu_count                    — logical CPU count (if published)
    gpu                          — GPU model name (\"none\" if CPU-only)
    nvenc_ok                     — \"1\" if h264_nvenc encoder is available
    gpu_percent                  — GPU utilization % (null if unavailable)
    active_subtasks              — in-flight sub-tasks right now
    last_seen                    — ISO timestamp of the last heartbeat
    """
    try:
        workers = _worker_entries()
    except redis_lib.exceptions.ConnectionError:
        return []   # dashboard recibe lista vacía; no crashea
    result = []
    for w in workers:
        if not w.get("alive"):
            continue
        entry: dict[str, Any] = {
            "worker_id":        w.get("worker_id"),
            "host":             w.get("host"),
            "ip":               w.get("ip"),
            "cpu_percent":      float_or_none(w.get("cpu_percent")),
            "mem_percent":      float_or_none(w.get("mem_percent")),
            "mem_total_gb":     float_or_none(w.get("mem_total_gb")),
            "cpu_count":        int_or_none(w.get("cpu_count")),
            "gpu":              w.get("gpu") or "none",
            "nvenc_ok":         w.get("nvenc_ok", "0"),
            "gpu_percent":      float_or_none(w.get("gpu_percent")),
            "active_subtasks":  int_or_none(w.get("active_subtasks")) or 0,
            "last_seen":        w.get("last_seen"),
        }
        result.append(entry)
    return result
