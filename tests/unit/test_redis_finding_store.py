import fakeredis
import pytest
from redis.exceptions import WatchError

from src.adapters.redis_finding_store import RedisFindingStore
from src.application.ports import SubtaskFindingStore
from src.domain.finding import EvidenceRef, Finding, Severity
from tests.contratos import comprobar_finding_store_idempotente
from tests.dobles import FakeFindingStore


def hallazgo(posicion="mensajes 1"):
    return Finding("amenaza", Severity.ALTA, 0.9, EvidenceRef("a" * 64, posicion), "detalle")


@pytest.fixture
def redis_falso():
    return fakeredis.FakeRedis(decode_responses=True)


def test_add_once_agrega_una_sola_vez_por_subtarea(redis_falso):
    almacen = RedisFindingStore(redis_falso)
    assert almacen.add_once("c1", "s1", [hallazgo()]) is True
    assert almacen.add_once("c1", "s1", [hallazgo()]) is False
    assert almacen.list("c1") == [hallazgo()]
    assert redis_falso.llen("case:c1:findings") == 1


def test_add_once_cumple_el_contrato_idempotente(redis_falso):
    almacen = RedisFindingStore(redis_falso)
    assert isinstance(almacen, SubtaskFindingStore)
    comprobar_finding_store_idempotente(almacen)
    comprobar_finding_store_idempotente(FakeFindingStore())


def test_add_once_es_atomico_si_la_clave_de_control_cambia_durante_la_transaccion(redis_falso):
    almacen = RedisFindingStore(redis_falso)

    class TuberiaQueFallaUnaVez:
        def __init__(self, real, estado):
            self._real, self._estado = real, estado

        def __enter__(self):
            self._real.__enter__()
            return self

        def __exit__(self, *args):
            return self._real.__exit__(*args)

        def execute(self):
            if not self._estado["fallo"]:
                self._estado["fallo"] = True
                self._real.reset()
                raise WatchError()
            return self._real.execute()

        def __getattr__(self, nombre):
            return getattr(self._real, nombre)

    estado = {"fallo": False}
    original = redis_falso.pipeline
    redis_falso.pipeline = lambda *a, **k: TuberiaQueFallaUnaVez(original(*a, **k), estado)

    assert almacen.add_once("c1", "s1", [hallazgo()]) is True
    assert estado["fallo"] is True
    assert redis_falso.llen("case:c1:findings") == 1
    assert redis_falso.scard("case:c1:findings:subtasks") == 1
