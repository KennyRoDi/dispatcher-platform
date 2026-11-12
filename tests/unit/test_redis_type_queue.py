"""Pruebas unitarias del adaptador Redis confiable de WorkQueue (F-06).

TDD: pruebas en rojo, sin implementacion aun.
"""
import time
from datetime import datetime, timezone

import fakeredis
import pytest

from src.domain.priority import Priority
from src.domain.subtask import ContentKind, Subtask
from tests import contratos


def subtarea(identificador="s1", kind=ContentKind.TEXT):
    return Subtask(identificador, "c1", kind, "abc", Priority.ALTA, datetime(2026, 11, 12, tzinfo=timezone.utc))


def cliente_redis():
    return fakeredis.FakeStrictRedis(decode_responses=True)


class TestRedisTypeQueueContrato:
    def test_redis_type_queue_cumple_el_contrato(self):
        from src.adapters.redis_type_queue import RedisTypeQueue

        redis = cliente_redis()
        contratos.comprobar_work_queue(lambda capacidad: RedisTypeQueue(redis, capacidad))


class TestRedisTypeQueueAtomicidad:
    def test_muerte_tras_blmove_deja_subtarea_en_inflight(self):
        """Tras take(), la sub-tarea esta en in_flight aunque el worker no haga nada mas (simula la muerte)."""
        from src.adapters.redis_type_queue import RedisTypeQueue

        redis = cliente_redis()
        cola = RedisTypeQueue(redis, capacity=10)
        original = subtarea()
        cola.enqueue("queue:text", original)

        tomada = cola.take("queue:text", "w1", timeout=1)

        assert tomada == original
        assert redis.llen("queue:text") == 0, "la sub-tarea ya no debe estar en la cola original"
        assert cola.in_flight("w1") == [original], "debe seguir en inflight aunque el worker muera aqui"

    def test_take_en_cola_vacia_no_bloquea_mas_del_timeout(self):
        from src.adapters.redis_type_queue import RedisTypeQueue

        redis = cliente_redis()
        cola = RedisTypeQueue(redis, capacity=10)

        inicio = time.monotonic()
        resultado = cola.take("queue:text", "w1", timeout=0.3)
        duracion = time.monotonic() - inicio

        assert resultado is None
        assert duracion < 1.5, "no debe colgarse mucho mas alla del timeout pedido"

    def test_acknowledge_quita_la_subtarea_de_inflight(self):
        from src.adapters.redis_type_queue import RedisTypeQueue

        redis = cliente_redis()
        cola = RedisTypeQueue(redis, capacity=10)
        original = subtarea()
        cola.enqueue("queue:text", original)
        tomada = cola.take("queue:text", "w1", timeout=1)

        cola.acknowledge("w1", tomada)

        assert cola.in_flight("w1") == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
