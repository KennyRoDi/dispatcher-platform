import fakeredis
import pytest

from src.adapters.redis_backpressure import mover_acotado
from src.domain.backpressure import QueueLimit

COLA = "queue:transcode_video"


@pytest.fixture
def r():
    return fakeredis.FakeRedis(decode_responses=True)


def test_scheduler_no_mueve_si_cola_llena(r):
    r.rpush(COLA, "a", "b")
    assert mover_acotado(r, COLA, "c", QueueLimit(2, 5)) is False
    assert r.lrange(COLA, 0, -1) == ["a", "b"]


def test_con_espacio_mueve_al_final_de_la_cola(r):
    r.rpush(COLA, "a")
    assert mover_acotado(r, COLA, "b", QueueLimit(2, 5)) is True
    assert r.lrange(COLA, 0, -1) == ["a", "b"]


def test_desactivado_siempre_mueve(r):
    r.rpush(COLA, *[str(i) for i in range(50)])
    assert mover_acotado(r, COLA, "x", QueueLimit(0, 5)) is True
    assert r.llen(COLA) == 51


def test_llena_la_cola_hasta_el_limite_exacto(r):
    movidos = [mover_acotado(r, COLA, str(i), QueueLimit(3, 5)) for i in range(5)]
    assert movidos == [True, True, True, False, False]
    assert r.llen(COLA) == 3
