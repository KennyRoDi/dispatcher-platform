import json
from datetime import datetime, timedelta, timezone

import fakeredis
import pytest
import redis
from fastapi.testclient import TestClient

import src.coordinator.main as main
from src.adapters.redis_finding_store import RedisFindingStore
from src.application.build_report import build_report
from src.application.ports import FindingStore
from src.application.report_json import _locator, report_to_dict
from src.coordinator import rutas_reporte
from src.domain.consolidated_report import CaseInfo, CaseSource, Fragment, ReportedFinding, find_incidents
from src.domain.evidence_position import MessageLocator
from src.domain.finding import EvidenceRef, Finding, Severity
from tests.dobles import FakeCaseCatalog, FakeClock, FakeFindingStore, FakeObjectStore

SHA = "a" * 64
INICIO = datetime(2026, 11, 3, 8, 0, tzinfo=timezone.utc)
AHORA = datetime(2026, 11, 3, 10, 0, tzinfo=timezone.utc)
RUTA = "/cases/c1/consolidated-report"


def caso(fuentes=None):
    fuentes = (CaseSource(SHA, f"{SHA}.txt", "texto", "completed"),) if fuentes is None else fuentes
    return CaseInfo("c1", "completed", INICIO, INICIO + timedelta(minutes=30), tuple(fuentes))


def hallazgo(sha=SHA, posicion="mensajes 1"):
    return Finding("amenaza", Severity.BAJA, 0.9, EvidenceRef(sha, posicion))


def tipos(reporte):
    return [i.kind for i in reporte.incidents]


class AlmacenCaido(FakeObjectStore):
    def exists(self, sha256):
        raise ConnectionError("MinIO caido")


class AlmacenQueCuenta(FakeObjectStore):
    def __init__(self):
        super().__init__()
        self.llamadas = []

    def exists(self, sha256):
        self.llamadas.append(sha256)
        return super().exists(sha256)


def construir(hallazgos, info, almacen):
    store = FakeFindingStore()
    store.add("c1", hallazgos)
    return build_report("c1", store, FakeCaseCatalog([info]), almacen, FakeClock(AHORA))


# --- Almacen no verificable ---


def test_almacen_caido_se_reporta_como_no_verificable_y_no_como_inexistente():
    reporte = construir([hallazgo()], caso(), AlmacenCaido())
    assert tipos(reporte) == ["almacen_no_verificable"]
    assert reporte.findings[0].fragments[0].in_store is None


def test_objeto_ausente_sigue_siendo_inexistente():
    reporte = construir([hallazgo()], caso(), FakeObjectStore())
    assert tipos(reporte) == ["objeto_inexistente"]


def test_incidencia_no_verificable_nombra_el_sha_y_la_categoria():
    reporte = construir([hallazgo()], caso(), AlmacenCaido())
    incidencia = reporte.incidents[0]
    assert (incidencia.sha256, incidencia.category) == (SHA, "amenaza")
    assert SHA in incidencia.detail


def test_no_verificable_se_ordena_despues_de_objeto_inexistente():
    otro = "b" * 64
    fuentes = [CaseSource(SHA, "a.txt", "texto", "completed"), CaseSource(otro, "b.txt", "texto", "completed")]
    fragmentos = (
        Fragment(SHA, fuentes[0], MessageLocator(1, None, None), in_store=None),
        Fragment(otro, fuentes[1], MessageLocator(1, None, None), in_store=False),
    )
    reportados = [ReportedFinding(hallazgo(SHA), fragmentos[:1]), ReportedFinding(hallazgo(otro), fragmentos[1:])]
    assert [i.kind for i in find_incidents(reportados, caso(fuentes))] == ["objeto_inexistente", "almacen_no_verificable"]


def test_evidencia_sin_sha_no_consulta_el_almacen():
    almacen = AlmacenQueCuenta()
    construir([hallazgo(sha="")], caso(), almacen)
    assert almacen.llamadas == []


def test_el_json_lleva_el_tipo_no_verificable():
    datos = report_to_dict(construir([hallazgo()], caso(), AlmacenCaido()))
    assert [i["tipo"] for i in datos["incidencias"]] == ["almacen_no_verificable"]
    json.dumps(datos, allow_nan=False)


def test_serializar_un_localizador_ajeno_lanza_type_error_aunque_se_use_optimizacion():
    with pytest.raises(TypeError):
        _locator(object())


# --- Ruta: Redis ---


@pytest.fixture
def cliente_redis_roto():
    class Roto:
        def lrange(self, *args):
            raise redis.exceptions.ResponseError("OOM redis-secreto:6379 command not allowed")

    store = RedisFindingStore(Roto())
    main.app.dependency_overrides[rutas_reporte.obtener_hallazgos] = lambda: store
    main.app.dependency_overrides[rutas_reporte.obtener_catalogo] = lambda: FakeCaseCatalog([caso()])
    main.app.dependency_overrides[rutas_reporte.obtener_almacen] = lambda: FakeObjectStore()
    main.app.dependency_overrides[rutas_reporte.obtener_reloj] = lambda: FakeClock(AHORA)
    yield TestClient(main.app)
    main.app.dependency_overrides.clear()


@pytest.mark.parametrize(
    "error",
    [
        redis.exceptions.ResponseError("OOM redis-secreto:6379"),
        redis.exceptions.ConnectionError("fallo redis-secreto:6379"),
        redis.exceptions.TimeoutError("lento redis-secreto:6379"),
        redis.exceptions.BusyLoadingError("cargando redis-secreto:6379"),
    ],
)
def test_cualquier_error_de_redis_da_503_sin_filtrar_host_ni_texto(error):
    class Falla:
        def list(self, case_id):
            raise error

    main.app.dependency_overrides[rutas_reporte.obtener_hallazgos] = lambda: Falla()
    main.app.dependency_overrides[rutas_reporte.obtener_catalogo] = lambda: FakeCaseCatalog([caso()])
    main.app.dependency_overrides[rutas_reporte.obtener_almacen] = lambda: FakeObjectStore()
    main.app.dependency_overrides[rutas_reporte.obtener_reloj] = lambda: FakeClock(AHORA)
    try:
        respuesta = TestClient(main.app).get(RUTA)
    finally:
        main.app.dependency_overrides.clear()
    assert respuesta.status_code == 503
    assert "redis-secreto" not in respuesta.text and "6379" not in respuesta.text


def test_error_de_respuesta_de_redis_en_el_adaptador_da_503(cliente_redis_roto):
    respuesta = cliente_redis_roto.get(RUTA)
    assert respuesta.status_code == 503
    assert "redis-secreto" not in respuesta.text


# --- Hallazgos corruptos ---


def redis_con_corrupto():
    cliente = fakeredis.FakeRedis(decode_responses=True)
    almacen = RedisFindingStore(cliente)
    almacen.add("c1", [hallazgo()])
    cliente.rpush("case:c1:findings", "{no es json", '{"category": 3}')
    return almacen


def test_hallazgos_corruptos_se_reflejan_como_incidencia_con_el_recuento():
    almacen = redis_con_corrupto()
    reporte = build_report("c1", almacen, FakeCaseCatalog([caso()]), _con_objeto(), FakeClock(AHORA))
    ilegibles = [i for i in reporte.incidents if i.kind == "hallazgos_ilegibles"]
    assert len(ilegibles) == 1 and "2" in ilegibles[0].detail
    assert len(reporte.findings) == 1


def test_sin_corruptos_no_hay_incidencia_de_ilegibles():
    cliente = fakeredis.FakeRedis(decode_responses=True)
    almacen = RedisFindingStore(cliente)
    almacen.add("c1", [hallazgo()])
    reporte = build_report("c1", almacen, FakeCaseCatalog([caso()]), _con_objeto(), FakeClock(AHORA))
    assert "hallazgos_ilegibles" not in tipos(reporte)


def test_el_puerto_finding_store_no_cambia_y_el_adaptador_sigue_cumpliendolo():
    almacen = redis_con_corrupto()
    assert isinstance(almacen, FindingStore)
    assert len(almacen.list("c1")) == 1


def test_un_almacen_sin_recuento_de_ilegibles_sigue_funcionando():
    reporte = construir([hallazgo()], caso(), _con_objeto())
    assert "hallazgos_ilegibles" not in tipos(reporte)


def _con_objeto():
    almacen = FakeObjectStore()
    almacen.objetos[SHA] = b"x"
    return almacen
