import os
import uuid
from datetime import datetime, timezone

import pytest
import redis

from src.adapters.redis_case_catalog import RedisCaseCatalog
from src.adapters.redis_finding_store import RedisFindingStore
from src.domain.consolidated_report import CaseInfo, CaseSource
from src.domain.finding import EvidenceRef, Finding, Severity
from tests.contratos import comprobar_finding_store
from tests.sembrado_redis import sembrar_caso

pytestmark = pytest.mark.integration

SHA_A = "a" * 64
SHA_B = "b" * 64
INICIO = datetime(2026, 11, 3, 8, 0, tzinfo=timezone.utc)


@pytest.fixture
def cliente():
    conexion = redis.Redis(
        host=os.environ.get("REDIS_HOST", "localhost"),
        port=int(os.environ.get("REDIS_PORT", "6379")),
        password=os.environ.get("REDIS_PASSWORD") or None,
        decode_responses=True,
        socket_connect_timeout=2,
    )
    try:
        conexion.ping()
    except redis.exceptions.RedisError:
        pytest.skip("define REDIS_HOST/REDIS_PORT de un Redis real (Compose)")
    return conexion


@pytest.fixture
def caso_id(cliente):
    identificador = f"f13-{uuid.uuid4().hex[:8]}"
    yield identificador
    claves = cliente.keys(f"*{identificador}*")
    if claves:
        cliente.delete(*claves)


def test_redis_finding_store_conserva_orden(cliente, caso_id):
    almacen = RedisFindingStore(cliente)
    hallazgos = [Finding("amenaza", Severity.ALTA, 0.9, EvidenceRef(SHA_A, f"mensajes {n}"), "d") for n in range(5)]
    almacen.add(caso_id, hallazgos[:2])
    almacen.add(caso_id, hallazgos[2:])
    assert almacen.list(caso_id) == hallazgos


def test_redis_finding_store_cumple_el_contrato_con_redis_real(cliente, caso_id):
    class ConPrefijo:
        def add(self, case_id, findings):
            RedisFindingStore(cliente).add(f"{caso_id}-{case_id}", findings)

        def list(self, case_id):
            return RedisFindingStore(cliente).list(f"{caso_id}-{case_id}")

    comprobar_finding_store(ConPrefijo())


def test_redis_case_catalog_lee_caso_y_subtareas(cliente, caso_id):
    info = CaseInfo(
        caso_id, "partially_completed", INICIO, INICIO,
        (CaseSource(SHA_A, "a.txt", "texto", "completed"), CaseSource(SHA_B, "b.wav", "audio", "failed", "TimeoutError")),
    )
    sembrar_caso(cliente, info)
    assert RedisCaseCatalog(cliente).case(caso_id) == info
    assert RedisCaseCatalog(cliente).case(f"{caso_id}-nada") is None

