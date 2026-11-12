from __future__ import annotations

import json
import logging
import uuid
from collections import defaultdict
from typing import Optional

from fastapi import APIRouter, HTTPException

from src.coordinator import conexion
from src.coordinator.apoyo import (
    TERMINAL_CASE_STATUSES,
    fetch_subtasks,
    float_or_none,
    int_or_none,
    json_dict,
    json_list,
    now_iso,
)
from src.coordinator.modelos import CaseRequest, SubtaskRequest
from src.coordinator.router import classify, queue_key, resolve_task_type

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/cases", status_code=201, response_model=dict, tags=["Cases"])
@router.post("/cases/", status_code=201, response_model=dict, tags=["Cases"], include_in_schema=False)
def create_case(case_req: CaseRequest) -> dict:
    """
    Create a processing case and enqueue each sub-task atomically.

    Fix 1  — task_type validated / auto-resolved BEFORE any Redis write (fail-fast).
    Fix 2  — uses pipeline(transaction=True): the entire case + subtask creation
             is one atomic Redis transaction. No orphan cases on partial failure.
    Fix 3  — ``RPUSH case:{id}:subtasks <sid>`` persists the subtask list so
             the dashboard and report endpoints don't need SCAN.
    Fix 4  — auto-routing via router.resolve_task_type() (rubric requirement).
    """
    if not case_req.subtasks:
        raise HTTPException(status_code=422, detail="El caso debe tener al menos una sub-tarea.")

    # --- resolve + validate all task types before touching Redis ---
    priority = case_req.priority
    resolved: list[tuple[SubtaskRequest, str, str]] = []  # (st, resolved_type, queue)
    for st in case_req.subtasks:
        op = resolve_task_type(st.task_type, st.file_path)  # raises 422 on invalid
        resolved.append((st, op, queue_key(op, priority)))

    case_id: str = case_req.case_id or str(uuid.uuid4())
    total: int = len(case_req.subtasks)
    created_at: str = now_iso()
    case_metadata_json = json.dumps(case_req.metadata or {})
    case_key = f"case:{case_id}"
    case_subtasks_key = f"case:{case_id}:subtasks"
    done_set_key = f"case:{case_id}:done"

    subtask_ids: list[str] = []
    subtask_id_list: list[str] = []

    # Pre-generate IDs and payloads outside the pipeline
    entries: list[tuple[str, str, str, SubtaskRequest, str, str, str]] = []
    for st, op, q in resolved:
        sid = str(uuid.uuid4())
        params_json = json.dumps(st.params or {})
        metadata_json = json.dumps(st.metadata or {})
        queue_payload = json.dumps({
            "subtask_id": sid,
            "case_id": case_id,
            "task_type": op,
            "file_path": st.file_path,
            "params": st.params or {},
            "priority": priority,
        })
        entries.append((sid, op, q, st, params_json, metadata_json, queue_payload))  # type: ignore[arg-type]
        subtask_id_list.append(sid)

    # --- atomic transaction ---
    pipe = conexion.redis_client.pipeline(transaction=True)

    # Case metadata hash
    pipe.hset(case_key, mapping={
        "case_id": case_id,
        "status": "queued",
        "total_subtasks": total,
        "pending_subtasks": total,
        "created_at": created_at,
        "priority": priority,
        "metadata": case_metadata_json,
        "retries": "0",
    })
    # Register in global set
    pipe.sadd("cases:registry", case_id)
    # Pre-create done set as empty (ensures key exists for SADD checks)
    # We don't need to create it explicitly; SADD will create it on first use.

    for sid, op, q, st, params_json, metadata_json, queue_payload in entries:
        # Subtask hash (fields read by the worker)
        pipe.hset(f"subtask:{sid}", mapping={
            "subtask_id": sid,
            "case_id": case_id,
            "operation": op,       # field the worker reads
            "task_type": op,       # coordinator-side query field
            "file_path": st.file_path,
            "status": "pending",
            "params": params_json,
            "metadata": metadata_json,
            "priority": priority,
        })
        # [FIX 3] Append subtask ID to per-case list (O(1) lookup, no SCAN needed)
        pipe.rpush(case_subtasks_key, sid)
        # Enqueue full JSON payload
        pipe.rpush(q, queue_payload)
        subtask_ids.append(sid)

    pipe.execute()  # atomic: all or nothing

    logger.info(
        "Caso creado: %s | subtareas: %d | ops: %s",
        case_id, total, list({op for _, op, _ in resolved})
    )

    return {
        "case_id": case_id,
        "status": "queued",
        "priority": priority,
        "total_subtasks": total,
        "subtask_ids": subtask_ids,
        "created_at": created_at,
    }


@router.post("/cases/{case_id}/cancel", status_code=200, response_model=dict, tags=["Cases"])
def cancel_case(case_id: str) -> dict:
    """
    Cancel a case. Pending subtasks are marked ``cancelled`` and counted as done
    (SADD + decrement of ``pending_subtasks``); assigned/running subtasks keep
    running and workers skip cancelled subtasks still sitting in the queues.
    """
    case_key = f"case:{case_id}"
    status = conexion.redis_client.hget(case_key, "status")
    if status is None:
        raise HTTPException(status_code=404, detail=f"Caso '{case_id}' no encontrado.")
    if status in TERMINAL_CASE_STATUSES:
        raise HTTPException(
            status_code=409,
            detail=f"El caso '{case_id}' ya está en estado terminal: '{status}'.",
        )

    now = now_iso()
    conexion.redis_client.hset(case_key, mapping={
        "status": "cancelled",
        "cancelled_at": now,
        "finished_at": now,
    })
    conexion.redis_client.set(f"cancel:{case_id}", now)
    conexion.redis_client.publish(f"cancel:{case_id}", case_id)

    done_set_key = f"case:{case_id}:done"
    subtask_ids = conexion.redis_client.lrange(f"case:{case_id}:subtasks", 0, -1)
    pipe = conexion.redis_client.pipeline()
    for sid in subtask_ids:
        pipe.hget(f"subtask:{sid}", "status")
    statuses = pipe.execute()

    cancelled = 0
    running = 0
    for sid, st_status in zip(subtask_ids, statuses):
        if st_status == "pending":
            if conexion.redis_client.sadd(done_set_key, sid):
                conexion.redis_client.hset(f"subtask:{sid}", "status", "cancelled")
                cancelled += 1
        elif st_status not in ("completed", "failed", "cancelled", None):
            running += 1
    if cancelled:
        conexion.redis_client.hincrby(case_key, "pending_subtasks", -cancelled)

    logger.info(
        "Caso %s cancelado | canceladas: %d | en ejecución: %d",
        case_id, cancelled, running,
    )
    return {
        "case_id": case_id,
        "status": "cancelled",
        "cancelled_subtasks": cancelled,
        "running_subtasks": running,
    }


@router.get("/cases", response_model=list, tags=["Dashboard"])
@router.get("/cases/", response_model=list, tags=["Dashboard"], include_in_schema=False)
def list_cases(status: Optional[str] = None) -> list:
    """Return metadata for every registered case, newest first (optional ?status= filter)."""
    case_ids: set[str] = conexion.redis_client.smembers("cases:registry")
    result = []
    for cid in case_ids:
        data = conexion.redis_client.hgetall(f"case:{cid}")
        if data and (status is None or data.get("status") == status):
            result.append(data)
    result.sort(key=lambda c: c.get("created_at", ""), reverse=True)
    return result


@router.get("/cases/{case_id}", response_model=dict, tags=["Dashboard"])
def get_case(case_id: str) -> dict:
    """
    Return full case metadata together with the detailed state and metrics
    for every associated sub-task, using the per-case subtask list (no SCAN).
    """
    case_data = conexion.redis_client.hgetall(f"case:{case_id}")
    if not case_data:
        raise HTTPException(status_code=404, detail=f"Caso '{case_id}' no encontrado.")

    subtasks = fetch_subtasks(case_id)
    return {"case": case_data, "subtasks": subtasks}


@router.get("/cases/{case_id}/report", response_model=dict, tags=["Dashboard"])
def get_case_report(case_id: str) -> dict:
    """
    Consolidated report for a case, grouped by operation type.

    Returns
    -------
    For each operation type present in the case:
      - list of sub-tasks with file_path, status, worker, host,
        started_at, finished_at, processing_s, media_duration_s,
        output_bytes, outputs, error, error_type
    Plus a top-level summary:
      - total, completed, failed counts
      - breakdown of failures by error_type
      - average processing_s per operation + per host
    """
    case_data = conexion.redis_client.hgetall(f"case:{case_id}")
    if not case_data:
        raise HTTPException(status_code=404, detail=f"Caso '{case_id}' no encontrado.")

    subtasks = fetch_subtasks(case_id)

    # --- group subtasks by operation ---
    by_operation: dict[str, list[dict]] = defaultdict(list)
    total_ok = 0
    total_fail = 0
    failure_types: dict[str, int] = defaultdict(int)
    processing_by_op: dict[str, list[float]] = defaultdict(list)
    processing_by_host: dict[str, list[float]] = defaultdict(list)
    by_type: dict[str, list[dict]] = defaultdict(list)
    totals_by_type_op: dict[str, dict[str, dict[str, int]]] = {}

    for st in subtasks:
        op = st.get("task_type") or st.get("operation", "unknown")
        status = st.get("status", "")
        entry = {
            "subtask_id": st.get("subtask_id"),
            "file_path": st.get("file_path"),
            "status": status,
            "worker_id": st.get("worker_id") or None,
            "host": st.get("host") or None,
            "started_at": st.get("started_at") or None,
            "finished_at": st.get("finished_at") or None,
            "processing_s": float_or_none(st.get("processing_s")),
            "media_duration_s": float_or_none(st.get("media_duration_s")),
            "output_bytes": int_or_none(st.get("output_bytes")),
            "outputs": json_list(st.get("outputs")),
            "error": st.get("error") or None,
            "error_type": st.get("error_type") or None,
            "attempts": int_or_none(st.get("attempts")),
            "encoder": st.get("encoder") or None,
            "metadata": json_dict(st.get("metadata")),
            "priority": st.get("priority") or None,
        }
        file_type = classify(st.get("file_path") or "")
        entry["file_type"] = file_type
        by_operation[op].append(entry)
        by_type[file_type].append(entry)
        bucket = totals_by_type_op.setdefault(file_type, {}).setdefault(
            op, {"completed": 0, "failed": 0, "other": 0}
        )
        bucket[status if status in ("completed", "failed") else "other"] += 1

        if status == "completed":
            total_ok += 1
        elif status == "failed":
            total_fail += 1
            etype = st.get("error_type") or "UnknownError"
            failure_types[etype] += 1

        ps = float_or_none(st.get("processing_s"))
        if ps is not None:
            processing_by_op[op].append(ps)
            host = st.get("host") or "unknown"
            processing_by_host[host].append(ps)

    # --- build summary ---
    total = int(case_data.get("total_subtasks", 0))
    pending = int(case_data.get("pending_subtasks", 0))

    avg_by_op = {op: round(sum(v) / len(v), 3) for op, v in processing_by_op.items() if v}
    avg_by_host = {h: round(sum(v) / len(v), 3) for h, v in processing_by_host.items() if v}

    summary_text_parts = []
    if total_ok:
        summary_text_parts.append(f"{total_ok} ok")
    if total_fail:
        ft_str = ", ".join(f"{v} {k}" for k, v in failure_types.items())
        summary_text_parts.append(f"{total_fail} fallida(s) ({ft_str})")
    if pending > 0:
        summary_text_parts.append(f"{pending} pendiente(s)")
    summary_text = "; ".join(summary_text_parts) or "sin sub-tareas"

    return {
        "case_id": case_id,
        "status": case_data.get("status"),
        "created_at": case_data.get("created_at"),
        "finished_at": case_data.get("finished_at"),
        "priority": case_data.get("priority") or "normal",
        "metadata": json_dict(case_data.get("metadata")),
        "retries": int_or_none(case_data.get("retries")) or 0,
        "summary": summary_text,
        "totals": {
            "total": total,
            "completed": total_ok,
            "failed": total_fail,
            "pending": pending,
        },
        "failure_breakdown": dict(failure_types),
        "avg_processing_s_by_operation": avg_by_op,
        "avg_processing_s_by_host": avg_by_host,
        "subtasks_by_operation": dict(by_operation),
        "subtasks_by_type": dict(by_type),
        "totals_by_type_and_operation": totals_by_type_op,
    }
