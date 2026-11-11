from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Depends, HTTPException

from src.application.alerting import notify_case_closed
from src.application.ports import AlertPublisher
from src.coordinator import conexion
from src.coordinator.apoyo import (
    final_case_status,
    json_dict,
    json_list,
    now_iso,
    str_or_empty,
)
from src.coordinator.modelos import SubtaskReport
from src.coordinator.rutas_alertas import obtener_publicador_alertas

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/subtasks/report", status_code=200, response_model=dict, tags=["Subtasks"])
def report_subtask(
    report: SubtaskReport,
    publicador: AlertPublisher = Depends(obtener_publicador_alertas),
) -> dict:
    """
    Receive a worker result report for a sub-task.

    Idempotency (FIX 1 — atomic via SADD)
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    ``SADD case:{id}:done <subtask_id>`` returns 1 only the FIRST time.
    On retry (worker didn't get our response) it returns 0 → early return,
    no counter decrement. This prevents double-counting and premature close.

    Barrier / Join
    ~~~~~~~~~~~~~~
    When ``pending_subtasks`` reaches ≤ 0 all subtasks have reported.
    Failure detection uses the per-case subtask list (no SCAN).
    """
    subtask_id = report.subtask_id
    case_id = report.case_id
    subtask_key = f"subtask:{subtask_id}"
    case_key = f"case:{case_id}"
    done_set_key = f"case:{case_id}:done"

    # --- guard: subtask must exist ---
    if not conexion.redis_client.exists(subtask_key):
        raise HTTPException(status_code=404, detail=f"Sub-tarea '{subtask_id}' no encontrada.")

    # --- [FIX 1] atomic idempotency via SADD ---
    added = conexion.redis_client.sadd(done_set_key, subtask_id)
    if added == 0:
        # Already processed — return current case status without touching counters
        current_case_status = conexion.redis_client.hget(case_key, "status") or "unknown"
        logger.info(
            "Reporte duplicado ignorado (SADD=0): subtask=%s case=%s",
            subtask_id, case_id,
        )
        return {
            "message": "Reporte ignorado por idempotencia",
            "subtask_id": subtask_id,
            "case_id": case_id,
            "case_status": current_case_status,
        }

    # --- validate reported status ---
    if report.status not in ("completed", "failed"):
        # Undo the sadd so the report can be retried with a correct status
        conexion.redis_client.srem(done_set_key, subtask_id)
        raise HTTPException(
            status_code=422,
            detail=(
                f"El campo 'status' debe ser 'completed' o 'failed'. "
                f"Recibido: '{report.status}'"
            ),
        )

    # --- update subtask hash with ALL worker metrics (None → "") ---
    subtask_updates: dict[str, str] = {
        "status": report.status,
        "worker_id": str_or_empty(report.worker_id),
        "host": str_or_empty(report.host),
        "started_at": str_or_empty(report.started_at),
        "finished_at": str_or_empty(report.finished_at),
        "processing_s": str_or_empty(report.processing_s),
        "media_duration_s": str_or_empty(report.media_duration_s),
        "output_bytes": str_or_empty(report.output_bytes) if report.output_bytes is not None else "0",
        "attempts": str_or_empty(report.attempts),
        "outputs": json.dumps(report.outputs or []),   # list → JSON string
        "error": str_or_empty(report.error),
        "error_type": str_or_empty(report.error_type),
        "encoder": str_or_empty(report.encoder),
    }
    conexion.redis_client.hset(subtask_key, mapping=subtask_updates)

    # --- decrement pending counter ---
    remaining = conexion.redis_client.hincrby(case_key, "pending_subtasks", -1)
    case_status = conexion.redis_client.hget(case_key, "status")

    # --- Barrier / Join (un caso cancelado nunca cambia de estado) ---
    if remaining <= 0 and case_status != "cancelled":
        final_status = final_case_status(case_id)
        conexion.redis_client.hset(case_key, mapping={
            "status": final_status,
            "finished_at": now_iso(),
        })
        case_status = final_status
        logger.info(
            "Caso %s finalizado → %s (pending=%d)", case_id, final_status, remaining
        )
        try:
            notify_case_closed(publicador, case_id, final_status)
        except Exception:
            logger.exception("Alerta de cierre del caso %r no publicada", case_id)

    return {
        "message": "Reporte procesado correctamente",
        "subtask_id": subtask_id,
        "case_id": case_id,
        "subtask_status": report.status,
        "case_status": case_status,
        "pending_subtasks": remaining,
    }




@router.get("/subtasks/{subtask_id}", response_model=dict, tags=["Dashboard"])
def get_subtask(subtask_id: str) -> dict:
    """Return the subtask hash with outputs/params/metadata parsed to JSON."""
    data = conexion.redis_client.hgetall(f"subtask:{subtask_id}")
    if not data:
        raise HTTPException(status_code=404, detail=f"Sub-tarea '{subtask_id}' no encontrada.")
    data["outputs"] = json_list(data.get("outputs"))
    data["params"] = json_dict(data.get("params"))
    data["metadata"] = json_dict(data.get("metadata"))
    return data
