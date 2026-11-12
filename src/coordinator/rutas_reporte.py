import logging

import redis
from fastapi import APIRouter, Depends, HTTPException

from src.adapters.redis_case_catalog import RedisCaseCatalog
from src.adapters.redis_finding_store import RedisFindingStore
from src.application.build_report import CaseNotFound, build_report
from src.application.ports import CaseCatalog, Clock, FindingStore, ObjectStore
from src.application.report_json import report_to_dict
from src.coordinator import conexion
from src.infrastructure.clock import SystemClock
from src.infrastructure.object_store import crear_almacen_lectura

logger = logging.getLogger(__name__)
router = APIRouter()
_almacen: ObjectStore | None = None


def obtener_hallazgos() -> FindingStore:
    return RedisFindingStore(conexion.redis_client)


def obtener_catalogo() -> CaseCatalog:
    return RedisCaseCatalog(conexion.redis_client)


def obtener_almacen() -> ObjectStore:
    global _almacen
    if _almacen is None:
        try:
            _almacen = crear_almacen_lectura()
        except Exception as error:
            logger.error("Almacén de objetos no disponible para el reporte: %s", type(error).__name__)
            raise HTTPException(status_code=503, detail="Almacén de objetos no configurado o no disponible.")
    return _almacen


def obtener_reloj() -> Clock:
    return SystemClock()


@router.get("/cases/{case_id}/consolidated-report", response_model=dict, tags=["Cases"])
def consolidated_report(
    case_id: str,
    hallazgos: FindingStore = Depends(obtener_hallazgos),
    catalogo: CaseCatalog = Depends(obtener_catalogo),
    almacen: ObjectStore = Depends(obtener_almacen),
    reloj: Clock = Depends(obtener_reloj),
) -> dict:
    """Reporte consolidado calculado al consultar (AD-38)."""
    try:
        return report_to_dict(build_report(case_id, hallazgos, catalogo, almacen, reloj))
    except CaseNotFound:
        raise HTTPException(status_code=404, detail=f"Caso '{case_id}' no encontrado.")
    except redis.exceptions.RedisError as error:
        # conexion.redis_unavailable filtra host, puerto y texto de la excepción al cliente.
        logger.error("Redis no disponible al armar el reporte de %s: %s", case_id, type(error).__name__)
        raise HTTPException(status_code=503, detail="Redis no está disponible.")
