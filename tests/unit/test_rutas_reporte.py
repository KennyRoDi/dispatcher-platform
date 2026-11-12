import json
from datetime import datetime, timedelta, timezone

import fakeredis
import pytest
from fastapi.testclient import TestClient

import src.coordinator.main as main
from src.adapters.redis_finding_store import RedisFindingStore
from src.coordinator import conexion, rutas_reporte
from src.domain.consolidated_report import CaseInfo, CaseSource
from src.domain.finding import EvidenceRef, Finding, Severity
from tests.dobles import FakeCaseCatalog, FakeClock, FakeFindingStore, FakeObjectStore
from tests.sembrado_redis import sembrar_caso


pytestmark = pytest.mark.usefixtures("sin_autorizacion")


SHA_T = "a" * 64
SHA_A = "b" * 64
INICIO = datetime(2026, 11, 3, 8, 0, tzinfo=timezone.utc)
AHORA = datetime(2026, 11, 3, 10, 0, tzinfo=timezone.utc)
CLAVES = [
    "case_id", "status", "finalizado", "generado_en", "hallazgos",
    "categorias", "linea_temporal", "sin_marca_absoluta", "incidencias",
]
RUTA = "/cases/c1/consolidated-report"


def caso(estado="completed"):
    fuentes = (CaseSource(SHA_T, f"{SHA_T}.txt", "texto", "completed"), CaseSource(SHA_A, f"{SHA_A}.wav", "audio", "completed"))
    return CaseInfo("c1", estado, INICIO, INICIO + timedelta(minutes=30), fuentes)


def hallazgos_sinteticos():
    marca = "2026-11-03T09:00:00+00:00"
    return [
        Finding("amenaza", Severity.ALTA, 0.9, EvidenceRef(SHA_T, "mensajes 3"), f"3 {marca} wa-3"),
        Finding("transcripcion", Severity.MEDIA, 0.8, EvidenceRef(SHA_A, "segmento 2 t=1.00-4.50s"), "hola"),
    ]


@pytest.fixture
def dobles():
    hallazgos = FakeFindingStore()
    hallazgos.add("c1", hallazgos_sinteticos())
    almacen = FakeObjectStore()
    almacen.objetos[SHA_T] = almacen.objetos[SHA_A] = b"x"
    return hallazgos, FakeCaseCatalog([caso()]), almacen


@pytest.fixture
def cliente(dobles):
    hallazgos, catalogo, almacen = dobles
    main.app.dependency_overrides[rutas_reporte.obtener_hallazgos] = lambda: hallazgos
    main.app.dependency_overrides[rutas_reporte.obtener_catalogo] = lambda: catalogo
    main.app.dependency_overrides[rutas_reporte.obtener_almacen] = lambda: almacen
    main.app.dependency_overrides[rutas_reporte.obtener_reloj] = lambda: FakeClock(AHORA)
    yield TestClient(main.app)
    main.app.dependency_overrides.clear()


def test_ruta_registrada_junto_a_la_del_i_proyecto_sin_pisarla():
    rutas = main.app.openapi()["paths"]
    assert "get" in rutas["/cases/{case_id}/consolidated-report"]
    assert "get" in rutas["/cases/{case_id}/report"]


def test_caso_inexistente_responde_404(cliente):
    respuesta = cliente.get("/cases/no-existe/consolidated-report")
    assert respuesta.status_code == 404
    assert "no-existe" in respuesta.json()["detail"]


def test_caso_finalizado_devuelve_las_claves_acordadas(cliente):
    respuesta = cliente.get(RUTA)
    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert list(datos) == CLAVES
    assert datos["case_id"] == "c1" and datos["finalizado"] is True
    assert datos["generado_en"] == AHORA.isoformat()


def test_caso_no_finalizado_responde_200_con_finalizado_falso(cliente, dobles):
    dobles[1].add(caso("processing"))
    respuesta = cliente.get(RUTA)
    assert respuesta.status_code == 200
    assert respuesta.json()["finalizado"] is False and respuesta.json()["status"] == "processing"


def test_caso_sin_hallazgos_devuelve_secciones_vacias(cliente, dobles):
    dobles[0].hallazgos["c1"].clear()
    datos = cliente.get(RUTA).json()
    assert datos["hallazgos"] == [] and datos["categorias"] == []
    assert datos["linea_temporal"] == [] and datos["sin_marca_absoluta"] == [] and datos["incidencias"] == []


def test_cada_fragmento_resuelve_a_fuente_y_marca(cliente):
    datos = cliente.get(RUTA).json()
    por_categoria = {h["categoria"]: h for h in datos["hallazgos"]}
    texto = por_categoria["amenaza"]["evidencia"][0]
    assert texto["fuente"] == {"sha256": SHA_T, "file_path": f"{SHA_T}.txt", "tipo": "texto"}
    assert texto["timestamp_utc"] == "2026-11-03T09:00:00+00:00"
    audio = por_categoria["transcripcion"]["evidencia"][0]
    assert audio["fuente"]["tipo"] == "audio" and audio["tramo_s"] == [1.0, 4.5]
    assert len(datos["linea_temporal"]) == 1 and len(datos["sin_marca_absoluta"]) == 1


def test_el_cuerpo_es_json_estricto_y_utf8(cliente):
    respuesta = cliente.get(RUTA)
    assert respuesta.headers["content-type"].startswith("application/json")
    json.loads(respuesta.content.decode("utf-8"), parse_constant=lambda c: pytest.fail(f"constante no JSON: {c}"))


def test_hallazgos_de_otro_caso_no_aparecen(cliente, dobles):
    dobles[0].add("c2", [Finding("amenaza", Severity.ALTA, 0.9, EvidenceRef(SHA_T, "mensajes 9"), "9 2026-11-03T09:05:00+00:00 x")])
    assert len(cliente.get(RUTA).json()["hallazgos"]) == 2


def test_adaptadores_por_defecto_leen_de_conexion_redis_client(monkeypatch, dobles):
    redis_falso = fakeredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(conexion, "redis_client", redis_falso)
    sembrar_caso(redis_falso, caso())
    RedisFindingStore(redis_falso).add("c1", hallazgos_sinteticos())
    main.app.dependency_overrides[rutas_reporte.obtener_almacen] = lambda: dobles[2]
    main.app.dependency_overrides[rutas_reporte.obtener_reloj] = lambda: FakeClock(AHORA)
    try:
        cliente = TestClient(main.app)
        datos = cliente.get(RUTA).json()
        inexistente = cliente.get("/cases/otro/consolidated-report")
    finally:
        main.app.dependency_overrides.clear()
    assert [h["categoria"] for h in datos["hallazgos"]] == ["amenaza", "transcripcion"]
    assert {i["tipo"] for i in datos["incidencias"]} == {"severidad_alta"}
    assert inexistente.status_code == 404


def test_reporte_consolidado_usa_el_almacen_de_lectura(monkeypatch, dobles):
    hallazgos, catalogo, almacen = dobles
    monkeypatch.setattr(rutas_reporte, "_almacen", None)
    monkeypatch.setattr(rutas_reporte, "crear_almacen_lectura", lambda: almacen)
    main.app.dependency_overrides[rutas_reporte.obtener_hallazgos] = lambda: hallazgos
    main.app.dependency_overrides[rutas_reporte.obtener_catalogo] = lambda: catalogo
    main.app.dependency_overrides[rutas_reporte.obtener_reloj] = lambda: FakeClock(AHORA)
    try:
        respuesta = TestClient(main.app).get(RUTA)
    finally:
        main.app.dependency_overrides.clear()
    assert respuesta.status_code == 200
    assert rutas_reporte._almacen is almacen


def test_reporte_consolidado_responde_503_sin_configuracion_del_almacen(monkeypatch, dobles):
    hallazgos, catalogo, _ = dobles
    monkeypatch.setattr(rutas_reporte, "_almacen", None)
    for variable in ("MINIO_ENDPOINT", "MINIO_ACCESS_KEY", "MINIO_SECRET_KEY"):
        monkeypatch.setenv(variable, "")
    monkeypatch.setenv("MINIO_SECRET_KEY", "clave-que-no-debe-filtrarse")
    main.app.dependency_overrides[rutas_reporte.obtener_hallazgos] = lambda: hallazgos
    main.app.dependency_overrides[rutas_reporte.obtener_catalogo] = lambda: catalogo
    main.app.dependency_overrides[rutas_reporte.obtener_reloj] = lambda: FakeClock(AHORA)
    try:
        respuesta = TestClient(main.app).get(RUTA)
    finally:
        main.app.dependency_overrides.clear()
    assert respuesta.status_code == 503
    assert "no configurado" in respuesta.json()["detail"]
    assert "clave-que-no-debe-filtrarse" not in respuesta.text
    assert rutas_reporte._almacen is None
