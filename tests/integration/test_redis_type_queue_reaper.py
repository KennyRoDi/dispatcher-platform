"""Prueba de integracion: reencolado de sub-tareas huerfanas (F-06)."""
import json
from datetime import datetime, timezone

import fakeredis
import pytest

from src.domain.priority import Priority
from src.domain.subtask import ContentKind, Subtask


def subtarea(identificador, kind):
    return Subtask(identificador, "c1", kind, "sha-" + identificador, Priority.ALTA,
                   datetime(2026, 11, 12, tzinfo=timezone.utc))


@pytest.mark.integration
class TestReencolarHuerfanas:
    def test_reaper_reencola_huerfanas_a_su_cola_original(self):
        from src.adapters.redis_type_queue import RedisTypeQueue

        redis = fakeredis.FakeStrictRedis(decode_responses=True)
        cola = RedisTypeQueue(redis, capacity=10)

        texto = subtarea("t1", ContentKind.TEXT)
        imagen = subtarea("i1", ContentKind.IMAGE)
        audio = subtarea("a1", ContentKind.AUDIO)
        cola.enqueue("queue:text", texto)
        cola.enqueue("queue:image", imagen)
        cola.enqueue("queue:audio", audio)

        cola.take("queue:text", "w1", timeout=1)
        cola.take("queue:image", "w1", timeout=1)
        cola.take("queue:audio", "w1", timeout=1)
        assert len(cola.in_flight("w1")) == 3

        movidas = cola.reencolar_huerfanas("w1")

        assert movidas == 3
        assert cola.in_flight("w1") == []
        assert redis.lrange("queue:text", 0, -1) == [json.dumps(texto.to_dict())]
        assert redis.lrange("queue:image", 0, -1) == [json.dumps(imagen.to_dict())]
        assert redis.lrange("queue:audio", 0, -1) == [json.dumps(audio.to_dict())]

    def test_reaper_no_pierde_nada_si_se_interrumpe_a_medias(self):
        """Simula una interrupcion tras mover solo una de dos huerfanas: nada queda fuera de inflight o su cola."""
        from src.adapters.redis_type_queue import RedisTypeQueue

        redis = fakeredis.FakeStrictRedis(decode_responses=True)
        cola = RedisTypeQueue(redis, capacity=10)

        texto = subtarea("t1", ContentKind.TEXT)
        imagen = subtarea("i1", ContentKind.IMAGE)
        cola.enqueue("queue:text", texto)
        cola.enqueue("queue:image", imagen)
        cola.take("queue:text", "w1", timeout=1)
        cola.take("queue:image", "w1", timeout=1)

        # "Interrupcion": solo se reencola una, como si el proceso muriera a medias.
        movidas_parcial = cola.reencolar_huerfanas("w1", limite=1)
        assert movidas_parcial == 1

        restantes_en_inflight = cola.in_flight("w1")
        en_colas = redis.lrange("queue:text", 0, -1) + redis.lrange("queue:image", 0, -1)
        total = len(restantes_en_inflight) + len(en_colas)
        assert total == 2, "ninguna sub-tarea debe perderse ni duplicarse tras la interrupcion"

        # El siguiente llamado (reintento) termina de recuperar lo que quedo.
        movidas_resto = cola.reencolar_huerfanas("w1")
        assert movidas_resto == 1
        assert cola.in_flight("w1") == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
