from __future__ import annotations

from typing import Any, List, Literal, Optional

from pydantic import BaseModel


class SubtaskRequest(BaseModel):
    """
    Description of a single sub-task inside a case creation request.

    ``task_type`` puede ser cualquiera de las 5 operaciones válidas,
    ``"auto"`` (detección por extensión) o ``None`` (equivalente a auto).
    """

    task_type: Optional[str] = "auto"   # "auto" → router elige por extensión
    file_path: str                       # MinIO object key
    params: Optional[dict[str, Any]] = None
    metadata: Optional[dict[str, Any]] = None


class SourceRef(BaseModel):
    """Referencia a una fuente ya subida (F-01): sha256 de un objeto existente + nombre original."""

    sha256: str
    name: str


class CaseRequest(BaseModel):
    """Payload for POST /cases.

    ``subtasks`` es el camino heredado (operación FFmpeg explícita por sub-tarea).
    ``sources`` (F-01) es el camino nuevo: fuentes que el sistema clasifica y
    decompone automáticamente (F-05/F-06). Se envía uno u otro, no ambos.
    """

    case_id: Optional[str] = None       # auto-generated if not provided
    subtasks: List[SubtaskRequest] = []
    sources: Optional[List[SourceRef]] = None
    priority: Literal["normal", "high"] = "normal"
    metadata: Optional[dict[str, Any]] = None


class SubtaskReport(BaseModel):
    """
    Extended report model sent by workers via POST /subtasks/report.
    Exactly matches the payload built in worker_node.py → Worker.handle_subtask().
    """

    subtask_id: str
    case_id: str
    status: str                          # "completed" | "failed"
    worker_id: Optional[str] = None
    host: Optional[str] = None
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    processing_s: Optional[float] = None
    media_duration_s: Optional[float] = None
    output_bytes: Optional[int] = None
    attempts: Optional[int] = None
    outputs: Optional[List[str]] = None  # MinIO result keys
    error: Optional[str] = None
    error_type: Optional[str] = None
    encoder: Optional[str] = None        # FFmpeg encoder used (libx264, h264_nvenc...)
