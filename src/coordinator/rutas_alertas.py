import logging

import redis
from fastapi import APIRouter, Depends, HTTPException, Query

from src.adapters.redis_alert_stream import RedisAlertStream
from src.application.alerting import SafeAlertPublisher
from src.application.ports import AlertPublisher, AlertReader
from src.coordinator import conexion
from src.infrastructure.clock import SystemClock

router = APIRouter()
logger = logging.getLogger(__name__)


def crear_flujo_alertas() -> RedisAlertStream:
    return RedisAlertStream(conexion.redis_client, SystemClock())


def obtener_lector_alertas() -> AlertReader:
    return crear_flujo_alertas()


def obtener_publicador_alertas() -> AlertPublisher:
    return SafeAlertPublisher(crear_flujo_alertas(), logger)


@router.get("/alerts", response_model=dict, tags=["Alerts"])
def alerts(limit: int = Query(50, ge=1, le=200), lector: AlertReader = Depends(obtener_lector_alertas)) -> dict:
    """Alertas recientes, la más reciente primero."""
    try:
        recientes = lector.recent(limit)
    except redis.exceptions.RedisError as error:
        # Detalle fijo: el texto de redis-py trae host y puerto.
        logger.error("Alertas no disponibles: %s", error)
        raise HTTPException(status_code=503, detail="Alertas no disponibles: Redis no responde o devolvió un error.")
    return {
        "alertas": [
            {
                "alert_id": alerta.alert_id,
                "kind": alerta.kind,
                "case_id": alerta.case_id,
                "detail": alerta.detail,
                "emitted_at": alerta.emitted_at.isoformat(),
            }
            for alerta in recientes
        ]
    }
