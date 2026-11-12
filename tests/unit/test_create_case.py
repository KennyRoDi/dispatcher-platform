"""Plataforma con formato tipado (F-43, parte 1): persistir antes de encolar, sin huerfanos."""
import json
from datetime import datetime, timezone

import fakeredis
import pytest

from src.adapters.redis_type_queue import RedisTypeQueue
from src.application.create_case import CreateMultiSourceCase
from src.coordinator.modelos import SourceRef
from src.domain.priority import Priority


class _SubidasFalsas:
    def __init__(self, almacenadas):
        self._almacenadas = set(almacenadas)

    def already_stored(self, sha256):
        return sha256 in self._almacenadas


class _RelojFijo:
    def now(self):
        return datetime(2026, 11, 12, tzinfo=timezone.utc)


class _ColaQueRegistra(RedisTypeQueue):
    def __init__(self, redis_client, capacity, falla_en=None):
        super().__init__(redis_client, capacity)
        self.persistido_al_encolar = []
        self._falla_en = falla_en
        self._llamadas = 0

    def enqueue(self, queue, subtask):
        self._llamadas += 1
        if self._llamadas == self._falla_en:
            raise RuntimeError("redis cayo a mitad del encolado")
        self.persistido_al_encolar.append(bool(self.redis.exists(f"subtask:{subtask.id}")))
        super().enqueue(queue, subtask)


def _fuentes():
    return [
        SourceRef(sha256="sha-texto", name="nota.txt"),
        SourceRef(sha256="sha-video", name="clip.mp4"),
    ]


def _caso_de_uso(redis, cola):
    return CreateMultiSourceCase(redis, cola, _RelojFijo(), _SubidasFalsas({"sha-texto", "sha-video"}))


def test_create_case_persiste_los_hashes_antes_de_encolar():
    redis = fakeredis.FakeStrictRedis(decode_responses=True)
    cola = _ColaQueRegistra(redis, capacity=100)

    resultado = _caso_de_uso(redis, cola).execute("caso1", _fuentes(), Priority.MEDIA)

    assert resultado["total_subtasks"] == 3
    assert cola.persistido_al_encolar == [True, True, True]


def test_create_case_no_deja_huerfanos_si_encolar_falla():
    redis = fakeredis.FakeStrictRedis(decode_responses=True)
    cola = _ColaQueRegistra(redis, capacity=100, falla_en=2)

    with pytest.raises(RuntimeError):
        _caso_de_uso(redis, cola).execute("caso2", _fuentes(), Priority.MEDIA)

    assert redis.exists("case:caso2") == 0
    assert redis.exists("case:caso2:subtasks") == 0
    assert redis.keys("subtask:*") == []
    assert "caso2" not in redis.smembers("cases:registry")
    assert redis.llen("queue:text") == 0
    assert redis.llen("queue:image") == 0


@pytest.mark.parametrize(
    "prioridad, en_hashes, en_la_cola",
    [(Priority.MEDIA, "normal", "media"), (Priority.ALTA, "high", "alta")],
)
def test_create_case_guarda_prioridad_normal_o_high_en_los_hashes(prioridad, en_hashes, en_la_cola):
    redis = fakeredis.FakeStrictRedis(decode_responses=True)
    cola = RedisTypeQueue(redis, capacity=100)

    resultado = _caso_de_uso(redis, cola).execute("caso3", _fuentes(), prioridad)

    assert resultado["priority"] == en_hashes
    assert redis.hget("case:caso3", "priority") == en_hashes
    for sid in resultado["subtask_ids"]:
        hash_subtarea = redis.hgetall(f"subtask:{sid}")
        assert hash_subtarea["priority"] == en_hashes
        mensaje = json.loads(redis.lpop(f"queue:{hash_subtarea['task_type']}"))
        assert mensaje["priority"] == en_la_cola
        assert json.loads(hash_subtarea["payload"]) == mensaje
