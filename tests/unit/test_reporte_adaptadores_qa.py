import json
from datetime import datetime, timedelta, timezone

import fakeredis
import pytest
import redis
from fastapi.testclient import TestClient

import src.coordinator.main as main
from src.adapters.redis_case_catalog import RedisCaseCatalog
from src.adapters.redis_finding_store import RedisFindingStore
from src.coordinator import conexion, rutas_reporte
from src.domain.consolidated_report import CaseInfo, CaseSource
from src.domain.finding import EvidenceRef, Finding, Severity
from tests.dobles import FakeClock, FakeObjectStore
from tests.sembrado_redis import sembrar_caso

SHA = "a" * 64
INICIO = datetime(2026, 11, 3, 8, 0, tzinfo=timezone.utc)
AHORA = datetime(2026, 11, 3, 10, 0, tzinfo=timezone.utc)
RUTA = "/cases/c1/consolidated-report"
MARCA = "2026-11-03T09:00:00+00:00"


def hallazgo(posicion="mensajes 3", detalle=f"3 {MARCA} wa-3"):
    return Finding("amenaza", Severity.ALTA, 0.9, EvidenceRef(SHA, posicion), detalle)


def crudo(**cambios):
    base = {"category": "amenaza", "severity": "alta", "confidence": 0.9, "sha256": SHA, "position": "mensajes 3", "detail": ""}
    return json.dumps({**base, **cambios})


@pytest.fixture
def redis_falso(monkeypatch):
    cliente = fakeredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(conexion, "redis_client", cliente)
    return cliente


@pytest.fixture
def cliente(redis_falso):
    almacen = FakeObjectStore()
    almacen.objetos[SHA] = b"x"
    main.app.dependency_overrides[rutas_reporte.obtener_almacen] = lambda: almacen
    main.app.dependency_overrides[rutas_reporte.obtener_reloj] = lambda: FakeClock(AHORA)
    yield TestClient(main.app, raise_server_exceptions=False)
    main.app.dependency_overrides.clear()


def sembrar_basico(redis_falso, case_id="c1"):
    redis_falso.hset(f"case:{case_id}", mapping={"status": "completed", "created_at": INICIO.isoformat()})


def volcado(redis_falso):
    return {k: redis_falso.dump(k) for k in redis_falso.keys("*")}


class RedisCaido:
    def __getattr__(self, nombre):
        def falla(*args, **kwargs):
            raise redis.ConnectionError("Error 111 connecting to 10.0.0.5:6379 password=hunter2")

        return falla


# Lo que se sostiene

@pytest.mark.parametrize("case_id", ["a:b", "*", "a%0Ab", "%F0%9F%98%80", "x" * 3000, "%00", "c1%3A*", "[ab]", "c1%20"])
def test_case_id_raro_da_404_limpio_y_no_escribe(cliente, redis_falso, case_id):
    sembrar_basico(redis_falso)
    antes = volcado(redis_falso)
    respuesta = cliente.get(f"/cases/{case_id}/consolidated-report")
    assert respuesta.status_code == 404
    assert volcado(redis_falso) == antes


def test_comodin_en_el_id_no_lee_otros_casos(cliente, redis_falso):
    sembrar_basico(redis_falso)
    RedisFindingStore(redis_falso).add("c1", [hallazgo()])
    assert cliente.get("/cases/c*/consolidated-report").status_code == 404
    assert cliente.get("/cases/*/consolidated-report").status_code == 404


def test_hallazgos_de_id_con_dos_puntos_no_se_mezclan_con_otro_caso(redis_falso):
    almacen = RedisFindingStore(redis_falso)
    almacen.add("a", [hallazgo("mensajes 1")])
    almacen.add("a:b", [hallazgo("mensajes 2")])
    assert [f.evidence.position for f in almacen.list("a")] == ["mensajes 1"]
    assert [f.evidence.position for f in almacen.list("a:b")] == ["mensajes 2"]


def test_consultar_no_escribe_nada_en_redis(cliente, redis_falso):
    sembrar_basico(redis_falso)
    redis_falso.rpush("case:c1:subtasks", "s1")
    redis_falso.hset("subtask:s1", mapping={"task_type": "analyze_text", "file_path": SHA, "status": "completed"})
    RedisFindingStore(redis_falso).add("c1", [hallazgo()])
    antes = volcado(redis_falso)
    assert cliente.get(RUTA).status_code == 200
    assert cliente.get("/cases/zz/consolidated-report").status_code == 404
    assert volcado(redis_falso) == antes


@pytest.mark.parametrize("metodo", ["post", "put", "delete", "patch"])
def test_metodos_de_escritura_dan_405(cliente, redis_falso, metodo):
    sembrar_basico(redis_falso)
    antes = volcado(redis_falso)
    assert getattr(cliente, metodo)(RUTA).status_code == 405
    assert volcado(redis_falso) == antes


def test_ruta_sin_id_y_ruta_vieja_no_colisionan(cliente, redis_falso):
    assert cliente.get("/cases/consolidated-report").status_code == 404
    rutas = main.app.openapi()["paths"]
    assert "/cases/{case_id}/report" in rutas and "/cases/{case_id}/consolidated-report" in rutas


def test_hash_real_de_subtarea_con_task_type_y_sin_kind(cliente, redis_falso):
    sembrar_basico(redis_falso)
    redis_falso.rpush("case:c1:subtasks", "s1")
    redis_falso.hset(
        "subtask:s1",
        mapping={"subtask_id": "s1", "case_id": "c1", "operation": "analyze_text", "task_type": "analyze_text",
                 "file_path": SHA, "status": "completed", "params": "{}", "metadata": "{}", "priority": "5"},
    )
    fuente = RedisCaseCatalog(redis_falso).case("c1").sources[0]
    assert (fuente.kind, fuente.file_path, fuente.sha256, fuente.error_type) == ("analyze_text", SHA, "", None)


def test_subtarea_inexistente_y_estado_desconocido_no_rompen(cliente, redis_falso):
    sembrar_basico(redis_falso)
    redis_falso.rpush("case:c1:subtasks", "fantasma", "s1")
    redis_falso.hset("subtask:s1", mapping={"task_type": "x", "status": "raro"})
    assert cliente.get(RUTA).status_code == 200
    assert len(RedisCaseCatalog(redis_falso).case("c1").sources) == 1


def test_estado_de_caso_desconocido_es_no_finalizado(cliente, redis_falso):
    redis_falso.hset("case:c1", mapping={"status": "zzz"})
    datos = cliente.get(RUTA).json()
    assert datos["status"] == "zzz" and datos["finalizado"] is False


def test_hash_vacio_de_caso_cuenta_como_inexistente(cliente, redis_falso):
    redis_falso.rpush("case:c1:findings", crudo())
    assert cliente.get(RUTA).status_code == 404


def test_lista_enorme_de_hallazgos_se_atiende_completa(cliente, redis_falso):
    sembrar_basico(redis_falso)
    RedisFindingStore(redis_falso).add("c1", [hallazgo(f"mensajes {i}", "") for i in range(3000)])
    respuesta = cliente.get(RUTA)
    assert respuesta.status_code == 200 and len(respuesta.json()["hallazgos"]) == 3000


def test_unicode_y_saltos_en_detalle_sobreviven_al_ciclo(redis_falso):
    almacen = RedisFindingStore(redis_falso)
    original = hallazgo(detalle="ñandú 😀\n\x00 línea   dos")
    almacen.add("c1", [original])
    assert almacen.list("c1") == [original]


def test_almacen_sin_configurar_da_503_sin_filtrar_rutas_ni_secretos(redis_falso):
    sembrar_basico(redis_falso)
    cliente = TestClient(main.app, raise_server_exceptions=False)
    respuesta = cliente.get(RUTA)
    assert respuesta.status_code == 503
    texto = respuesta.text
    assert "/home" not in texto and "Traceback" not in texto and "password" not in texto.lower()


def test_error_500_no_trae_traza_ni_rutas(cliente, redis_falso):
    sembrar_basico(redis_falso)

    def falla():
        raise RuntimeError("/home/x/src/secreto.py")

    main.app.dependency_overrides[rutas_reporte.obtener_hallazgos] = falla
    respuesta = cliente.get(RUTA)
    assert respuesta.status_code == 500
    assert "Traceback" not in respuesta.text and "/home" not in respuesta.text and "src/" not in respuesta.text


# Defectos

def test_redis_caido_responde_503_limpio(cliente, monkeypatch):
    monkeypatch.setattr(conexion, "redis_client", RedisCaido())
    respuesta = cliente.get(RUTA)
    assert respuesta.status_code == 503
    assert "Traceback" not in respuesta.text


@pytest.mark.parametrize(
    "raw",
    [
        "{rota",
        "[1, 2]",
        "null",
        json.dumps({"category": "a"}),
        crudo(severity="critica"),
        crudo(confidence="0.5"),
        crudo(confidence=7),
        crudo(sha256=None, position=None, detail=None),
    ],
    ids=["json-roto", "json-lista", "json-null", "campos-faltan", "severidad-desconocida", "confianza-str", "confianza-fuera-de-rango", "campos-null"],
)
def test_hallazgo_corrupto_en_la_lista_no_tumba_el_reporte(cliente, redis_falso, raw):
    sembrar_basico(redis_falso)
    redis_falso.rpush("case:c1:findings", crudo(), raw)
    respuesta = cliente.get(RUTA)
    assert respuesta.status_code == 200
    assert len(respuesta.json()["hallazgos"]) >= 1


def test_marca_de_tiempo_malformada_no_da_500(cliente, redis_falso):
    redis_falso.hset("case:c1", mapping={"status": "completed", "created_at": "ayer por la tarde"})
    assert cliente.get(RUTA).status_code == 200


def test_bytes_no_utf8_en_el_hash_del_caso_no_da_500(cliente, redis_falso):
    redis_falso.hset("case:c1", mapping={"status": b"\xff\xfe"})
    assert cliente.get(RUTA).status_code in (200, 404)


@pytest.mark.parametrize("case_id", ["c1:findings", "c1:subtasks"])
def test_case_id_que_coincide_con_clave_de_lista_da_404(cliente, redis_falso, case_id):
    sembrar_basico(redis_falso)
    redis_falso.rpush("case:c1:subtasks", "s1")
    redis_falso.hset("subtask:s1", mapping={"task_type": "x", "file_path": SHA, "status": "completed"})
    RedisFindingStore(redis_falso).add("c1", [hallazgo()])
    assert cliente.get(f"/cases/{case_id}/consolidated-report").status_code == 404


def test_fuente_unida_por_file_path_lleva_el_sha256_del_objeto(cliente, redis_falso):
    sembrar_basico(redis_falso)
    redis_falso.rpush("case:c1:subtasks", "s1")
    redis_falso.hset("subtask:s1", mapping={"task_type": "analyze_text", "file_path": SHA, "status": "completed"})
    RedisFindingStore(redis_falso).add("c1", [hallazgo()])
    fuente = cliente.get(RUTA).json()["hallazgos"][0]["evidencia"][0]["fuente"]
    assert fuente["sha256"] == SHA
