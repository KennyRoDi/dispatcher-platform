"""
Coordinator service — Plataforma Distribuida de Procesamiento Multimedia
========================================================================
Persona 1 · Coordinador y Orquestador  (v4.0)

Responsabilidades
-----------------
* Recibir casos (POST /cases), validar/resolver la operación de cada sub-tarea
  (router.py; "auto" → por extensión) y encolarlas en Redis de forma atómica,
  en queue:{op} o queue:{op}:high según la prioridad del caso.
* Barrier/Join: POST /subtasks/report es idempotente (SADD en case:{id}:done)
  y cierra el caso cuando pending_subtasks llega a 0.
* Consultas para dashboard/clientes: GET /cases[?status=], /cases/{id},
  /cases/{id}/report, /subtasks/{id}, /workers, /stats.

Novedades v4 (sobre v3)
-----------------------
  1. priority ("normal" | "high") por caso → colas queue:{op}:high, que los
     workers consumen antes que las normales.
  2. metadata libre por caso y por sub-tarea (se guarda como JSON string).
  3. Estados de caso: queued → processing → retrying → completed |
     partially_completed | failed | cancelled. El coordinador crea "queued" y
     fija los terminales; el worker pasa a "processing" al tomar la primera
     sub-tarea; el reaper marca "retrying" y suma case.retries al reencolar.
  4. POST /cases/{id}/cancel (409 si el caso ya es terminal; un caso cancelado
     nunca cambia de estado).
  5. GET /subtasks/{id}, GET /workers (heartbeats, campo alive), GET /stats
     (colas, casos por estado, workers vivos) y GET /cases?status=.
  6. El reporte añade priority, metadata, retries, subtasks_by_type y
     totals_by_type_and_operation.

Contratos respetados
--------------------
* Workers (src/workers): payload JSON completo en la cola; hash subtask:{id}
  con 'operation', 'file_path', 'params', 'priority'.
* Reporter (worker_node.py): SubtaskReport acepta todos los campos del worker.
* Detalle de claves y estados: docs/WORKER_CONTRACT.md.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Mapping

from fastapi import Depends, FastAPI

from src.coordinator import rutas_alertas, rutas_archivos, rutas_casos, rutas_monitoreo, rutas_reporte, rutas_subtareas
from src.coordinator.seguridad import AutenticacionPrevia, autorizar

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

VALORES_QUE_DESACTIVAN = frozenset({"0", "false", "no", "off"})


def auth_habilitada(env: Mapping[str, str]) -> bool:
    return env.get("AUTH_ENABLED", "").strip().lower() not in VALORES_QUE_DESACTIVAN


def crear_app(env: Mapping[str, str] | None = None) -> FastAPI:
    env = os.environ if env is None else env
    protegida = auth_habilitada(env)
    app = FastAPI(
        title="Nodo Coordinador — Plataforma Distribuida de Procesamiento Multimedia",
        version="4.0.0",
        description=(
            "Orquesta casos de procesamiento multimedia, encola sub-tareas en Redis "
            "y consolida resultados mediante el patrón Barrier/Join."
        ),
    )
    dependencias = [Depends(autorizar)] if protegida else []
    routers = (
        rutas_casos.router,
        rutas_subtareas.router,
        rutas_monitoreo.router,
        rutas_archivos.router,
        rutas_alertas.router,
        rutas_reporte.router,
    )
    for router in routers:
        app.include_router(router, dependencies=dependencias)
    if protegida:
        app.add_middleware(AutenticacionPrevia)
    return app


app = crear_app()
