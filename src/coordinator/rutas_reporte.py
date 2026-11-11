import redis
from fastapi import APIRouter, Depends, HTTPException

from src.adapters.redis_case_catalog import RedisCaseCatalog
from src.adapters.redis_finding_store import RedisFindingStore
from src.application.build_report import CaseNotFound, build_report
from src.application.ports import CaseCatalog, Clock, FindingStore, ObjectStore
from src.application.report_json import report_to_dict
from src.coordinator import conexion
from src.coordinator.conexion import redis_unavailable
from src.infrastructure.clock import SystemClock

router = APIRouter()


def obtener_hallazgos() -> FindingStore:
    return RedisFindingStore(conexion.redis_client)


def obtener_catalogo() -> CaseCatalog:
    return RedisCaseCatalog(conexion.redis_client)


def obtener_almacen() -> ObjectStore:
    # Aún no hay adaptador de ObjectStore (F-23, Melany); no se inventa uno.
    raise HTTPException(status_code=503, detail="Almacén de objetos no configurado (pendiente F-23).")


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
    except (redis.exceptions.ConnectionError, redis.exceptions.TimeoutError) as error:
        raise redis_unavailable(error)
