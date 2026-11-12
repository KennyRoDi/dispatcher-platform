"""Prueba de integracion: el Reaper real detecta un worker sin latido y reencola (F-34).

No reimplementa scripts/reaper.py: lo importa y lo ejecuta tal cual contra
fakeredis (que implementa EXPIRE/TTL con reloj real).
"""
import pytest


class _SettingsFalsas:
    max_attempts = 3
    reaper_max_age = 2100.0


class _ReporterFalso:
    def report(self, payload):
        pass


@pytest.mark.integration
class TestReaperRealDetectaCaida:
    def test_reaper_real_detecta_y_reencola_heartbeat_perdido(self):
        import fakeredis
        from scripts.reaper import Reaper

        redis = fakeredis.FakeStrictRedis(decode_responses=True)
        worker_id = "worker-caido"
        sid = "sub-1"

        # Sub-tarea "assigned" al worker, en su inflight (camino heredado).
        redis.hset(f"subtask:{sid}", mapping={
            "status": "assigned",
            "operation": "transcode_video",
            "attempts": "1",
            "worker_id": worker_id,
        })
        redis.sadd(f"worker:{worker_id}:inflight", sid)
        redis.sadd("workers:registry", worker_id)
        # El worker nunca llego a latir (o ya expiro): no existe worker:{id}.

        reaper = Reaper(_SettingsFalsas(), redis, _ReporterFalso())
        conteos = reaper.run_once()

        assert conteos["requeued"] == 1
        assert conteos["workers_removed"] == 1
        # Reencolada en la cola original del camino heredado.
        assert redis.llen("queue:transcode_video") == 1
        assert redis.lrange("queue:transcode_video", 0, -1) == [sid]
        # Ya no sigue en el inflight del worker caido.
        assert redis.smembers(f"worker:{worker_id}:inflight") == set()
        assert redis.hget(f"subtask:{sid}", "status") == "pending"

    def test_reaper_no_toca_nada_si_el_worker_sigue_vivo(self):
        import fakeredis
        from scripts.reaper import Reaper

        redis = fakeredis.FakeStrictRedis(decode_responses=True)
        worker_id = "worker-vivo"
        sid = "sub-2"

        redis.hset(f"subtask:{sid}", mapping={
            "status": "running",
            "operation": "extract_audio",
            "attempts": "0",
            "assigned_ts": "0",
        })
        redis.sadd(f"worker:{worker_id}:inflight", sid)
        redis.sadd("workers:registry", worker_id)
        redis.hset(f"worker:{worker_id}", mapping={"worker_id": worker_id})  # late vigente

        reaper = Reaper(_SettingsFalsas(), redis, _ReporterFalso(), clock=lambda: 1.0)
        conteos = reaper.run_once()

        assert conteos["requeued"] == 0
        assert redis.llen("queue:extract_audio") == 0
        assert redis.smembers(f"worker:{worker_id}:inflight") == {sid}


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
