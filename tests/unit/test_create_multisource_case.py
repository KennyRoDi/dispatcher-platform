"""Pruebas unitarias del caso de uso de creacion de caso multifuente (F-01).

TDD: pruebas en rojo, sin implementacion aun.
"""
from datetime import datetime, timezone

import fakeredis
import pytest

from src.domain.priority import Priority


class _SubidasFalsas:
    """Doble minimo de ChunkedUpload: solo el metodo que F-01 necesita."""

    def __init__(self, almacenadas):
        self._almacenadas = set(almacenadas)

    def already_stored(self, sha256):
        return sha256 in self._almacenadas


class _RelojFijo:
    def now(self):
        return datetime(2026, 11, 12, tzinfo=timezone.utc)


def fuentes_heterogeneas():
    from src.coordinator.modelos import SourceRef

    return [
        SourceRef(sha256="sha-texto", name="nota.txt"),
        SourceRef(sha256="sha-imagen", name="foto.jpg"),
        SourceRef(sha256="sha-audio", name="voz.mp3"),
        SourceRef(sha256="sha-video", name="clip.mp4"),
    ]


class TestCrearCasoMultifuente:
    def test_crear_caso_con_varias_fuentes_las_registra(self):
        from src.adapters.redis_type_queue import RedisTypeQueue
        from src.application.create_case import CreateMultiSourceCase

        redis = fakeredis.FakeStrictRedis(decode_responses=True)
        cola = RedisTypeQueue(redis, capacity=100)
        subidas = _SubidasFalsas({"sha-texto", "sha-imagen", "sha-audio", "sha-video"})
        caso_de_uso = CreateMultiSourceCase(redis, cola, _RelojFijo(), subidas)

        resultado = caso_de_uso.execute("caso1", fuentes_heterogeneas(), Priority.ALTA)

        assert resultado["case_id"] == "caso1"
        assert resultado["status"] == "queued"
        # El video expande a audio + imagen: 3 fuentes directas + 2 del video = 5 sub-tareas
        assert resultado["total_subtasks"] == 5
        assert len(resultado["subtask_ids"]) == 5

        caso = redis.hgetall("case:caso1")
        assert caso["status"] == "queued"
        assert caso["total_subtasks"] == "5"
        assert caso["pending_subtasks"] == "5"

        ids_en_redis = redis.lrange("case:caso1:subtasks", 0, -1)
        assert set(ids_en_redis) == set(resultado["subtask_ids"])

        tipos = set()
        for sid in ids_en_redis:
            sub = redis.hgetall(f"subtask:{sid}")
            assert sub["status"] == "pending"
            assert sub["case_id"] == "caso1"
            tipos.add(sub["task_type"])
        assert tipos == {"text", "image", "audio"}

        assert redis.llen("queue:text") == 1
        assert redis.llen("queue:image") == 2  # directa + la del video
        assert redis.llen("queue:audio") == 2  # directa + la del video

        assert "caso1" in redis.smembers("cases:registry")

    def test_fuente_sin_objeto_subido_rechaza_sin_encolar_nada(self):
        from src.adapters.redis_type_queue import RedisTypeQueue
        from src.application.create_case import CreateMultiSourceCase, FuenteNoSubida

        redis = fakeredis.FakeStrictRedis(decode_responses=True)
        cola = RedisTypeQueue(redis, capacity=100)
        subidas = _SubidasFalsas({"sha-texto"})  # falta sha-imagen, sha-audio, sha-video
        caso_de_uso = CreateMultiSourceCase(redis, cola, _RelojFijo(), subidas)

        with pytest.raises(FuenteNoSubida):
            caso_de_uso.execute("caso2", fuentes_heterogeneas(), Priority.ALTA)

        assert redis.exists("case:caso2") == 0
        assert redis.llen("queue:text") == 0
        assert redis.llen("queue:image") == 0
        assert redis.llen("queue:audio") == 0

    def test_extension_no_soportada_rechaza_sin_encolar_nada(self):
        from src.adapters.redis_type_queue import RedisTypeQueue
        from src.application.create_case import CreateMultiSourceCase
        from src.coordinator.modelos import SourceRef

        redis = fakeredis.FakeStrictRedis(decode_responses=True)
        cola = RedisTypeQueue(redis, capacity=100)
        subidas = _SubidasFalsas({"sha-raro"})
        caso_de_uso = CreateMultiSourceCase(redis, cola, _RelojFijo(), subidas)

        with pytest.raises(ValueError):
            caso_de_uso.execute("caso3", [SourceRef(sha256="sha-raro", name="archivo.xyz")], Priority.ALTA)

        assert redis.exists("case:caso3") == 0
        assert redis.llen("queue:text") == 0

    def test_sin_fuentes_rechaza_en_vez_de_crear_caso_vacio(self):
        """Hallazgo de QA: execute([]) no debe crear un caso con 0 sub-tareas en silencio."""
        from src.adapters.redis_type_queue import RedisTypeQueue
        from src.application.create_case import CreateMultiSourceCase

        redis = fakeredis.FakeStrictRedis(decode_responses=True)
        cola = RedisTypeQueue(redis, capacity=100)
        caso_de_uso = CreateMultiSourceCase(redis, cola, _RelojFijo(), _SubidasFalsas(set()))

        with pytest.raises(ValueError):
            caso_de_uso.execute("caso4", [], Priority.ALTA)

        assert redis.exists("case:caso4") == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
