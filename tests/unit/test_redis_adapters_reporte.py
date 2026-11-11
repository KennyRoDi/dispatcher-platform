import json
from datetime import datetime, timedelta, timezone

import fakeredis
import pytest

from src.adapters.redis_case_catalog import RedisCaseCatalog
from src.adapters.redis_finding_store import RedisFindingStore
from src.application.ports import CaseCatalog, FindingStore
from src.domain.consolidated_report import CaseInfo, CaseSource
from src.domain.finding import EvidenceRef, Finding, Severity
from tests.contratos import comprobar_case_catalog, comprobar_finding_store
from tests.sembrado_redis import sembrar_caso

SHA_A = "a" * 64
SHA_B = "b" * 64
INICIO = datetime(2026, 11, 3, 8, 0, tzinfo=timezone.utc)


@pytest.fixture
def redis_falso():
    return fakeredis.FakeRedis(decode_responses=True)


def hallazgo(categoria="amenaza", sha=SHA_A, posicion="mensajes 3", detalle="", severidad=Severity.ALTA):
    return Finding(categoria, severidad, 0.9, EvidenceRef(sha, posicion), detalle)


def caso(fuentes=(), estado="completed", fin=INICIO + timedelta(minutes=30)):
    return CaseInfo("c1", estado, INICIO, fin, tuple(fuentes))


def fuente(sha=SHA_A, ruta="a.txt", tipo="texto", estado="completed", error_type=None):
    return CaseSource(sha, ruta, tipo, estado, error_type)


def test_finding_store_redis_cumple_el_contrato(redis_falso):
    almacen = RedisFindingStore(redis_falso)
    assert isinstance(almacen, FindingStore)
    comprobar_finding_store(almacen)


def test_finding_store_conserva_el_orden_de_insercion_entre_lotes(redis_falso):
    almacen = RedisFindingStore(redis_falso)
    primero, segundo, tercero = hallazgo(posicion="mensajes 1"), hallazgo(posicion="mensajes 2"), hallazgo(posicion="mensajes 3")
    almacen.add("c1", [primero, segundo])
    almacen.add("c1", [tercero])
    assert almacen.list("c1") == [primero, segundo, tercero]


def test_finding_store_guarda_un_json_por_hallazgo_en_la_lista_del_caso(redis_falso):
    almacen = RedisFindingStore(redis_falso)
    almacen.add("c1", [hallazgo(detalle="3 2026-11-03T09:00:00+00:00 wa-3"), hallazgo("tema", posicion="mensajes 0-49", severidad=Severity.BAJA)])
    assert redis_falso.llen("case:c1:findings") == 2
    primero = json.loads(redis_falso.lindex("case:c1:findings", 0))
    assert primero == {
        "category": "amenaza",
        "severity": "alta",
        "confidence": 0.9,
        "sha256": SHA_A,
        "position": "mensajes 3",
        "detail": "3 2026-11-03T09:00:00+00:00 wa-3",
    }


def test_finding_store_conserva_unicode_y_detalle_vacio(redis_falso):
    almacen = RedisFindingStore(redis_falso)
    con_texto = hallazgo(detalle="canción ñandú ✓")
    sin_texto = hallazgo(posicion="mensajes 4")
    almacen.add("c1", [con_texto, sin_texto])
    assert almacen.list("c1") == [con_texto, sin_texto]


def test_finding_store_lote_vacio_no_falla_ni_crea_la_clave(redis_falso):
    almacen = RedisFindingStore(redis_falso)
    almacen.add("c1", [])
    assert almacen.list("c1") == []
    assert redis_falso.exists("case:c1:findings") == 0


def test_finding_store_separa_casos(redis_falso):
    almacen = RedisFindingStore(redis_falso)
    almacen.add("c1", [hallazgo()])
    almacen.add("c2", [hallazgo(posicion="mensajes 9")])
    assert [h.evidence.position for h in almacen.list("c1")] == ["mensajes 3"]
    assert [h.evidence.position for h in almacen.list("c2")] == ["mensajes 9"]


def test_case_catalog_redis_cumple_el_contrato(redis_falso):
    def crear(info):
        sembrar_caso(redis_falso, info)
        return RedisCaseCatalog(redis_falso)

    comprobar_case_catalog(crear)
    assert isinstance(RedisCaseCatalog(redis_falso), CaseCatalog)


def test_case_catalog_lee_caso_y_subtareas_en_orden(redis_falso):
    info = caso(
        [
            fuente(SHA_A, "a.txt", "texto"),
            fuente(SHA_B, "b.wav", "audio", "failed", "TimeoutError"),
        ],
        estado="partially_completed",
    )
    sembrar_caso(redis_falso, info)
    assert RedisCaseCatalog(redis_falso).case("c1") == info


def test_case_catalog_caso_en_curso_sin_fin_ni_subtareas(redis_falso):
    info = caso(estado="processing", fin=None)
    sembrar_caso(redis_falso, info)
    leido = RedisCaseCatalog(redis_falso).case("c1")
    assert leido.finished_at is None and leido.sources == () and leido.finished is False


def test_case_catalog_subtarea_sin_source_sha256_queda_con_sha_vacio_para_unir_por_file_path(redis_falso):
    sembrar_caso(redis_falso, caso([fuente(sha="", ruta=SHA_A)]))
    origen = RedisCaseCatalog(redis_falso).case("c1").sources[0]
    assert origen.sha256 == "" and origen.file_path == SHA_A


def test_case_catalog_error_type_vacio_es_none(redis_falso):
    sembrar_caso(redis_falso, caso([fuente(error_type=None)]))
    assert RedisCaseCatalog(redis_falso).case("c1").sources[0].error_type is None


def test_case_catalog_omite_subtareas_listadas_cuyo_hash_ya_no_existe(redis_falso):
    sembrar_caso(redis_falso, caso([fuente(), fuente(SHA_B, "b.txt")]))
    redis_falso.delete("subtask:c1-s0")
    assert [s.file_path for s in RedisCaseCatalog(redis_falso).case("c1").sources] == ["b.txt"]


def test_case_catalog_es_de_solo_lectura(redis_falso):
    sembrar_caso(redis_falso, caso([fuente()]))
    antes = {clave: redis_falso.type(clave) for clave in redis_falso.keys("*")}
    foto = {clave: redis_falso.hgetall(clave) for clave, tipo in antes.items() if tipo == "hash"}
    RedisCaseCatalog(redis_falso).case("c1")
    RedisCaseCatalog(redis_falso).case("inexistente")
    assert {clave: redis_falso.type(clave) for clave in redis_falso.keys("*")} == antes
    assert {clave: redis_falso.hgetall(clave) for clave in foto} == foto
