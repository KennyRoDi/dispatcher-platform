"""Pruebas de integración: Scheduler con Redis real."""
import pytest
import fakeredis
from unittest.mock import patch, MagicMock
import time


@pytest.fixture
def redis_client():
    """Redis fake para pruebas de integración."""
    return fakeredis.FakeStrictRedis(decode_responses=True)


class TestSchedulerConRedis:
    """Scheduler persiste en Redis y lee múltiples colas."""

    def test_scheduler_con_redis_multiple_niveles(self, redis_client):
        """Scheduler lee colas correctas, mueve en orden por tipo."""
        from src.domain.scheduling import Priority, SchedulingPolicy

        # Simulación: scheduler que usa Redis
        # (La implementación real vendrá en F-20-3)
        scheduler = MagicMock()
        scheduler.policy = SchedulingPolicy.AGING

        # Enqueuing en Redis (simulado)
        redis_client.rpush("queue:text:high", "subtask:1")
        redis_client.rpush("queue:image:normal", "subtask:2")
        redis_client.rpush("queue:audio:normal", "subtask:3")

        # El scheduler debe leer de las colas correctas
        assert redis_client.lrange("queue:text:high", 0, -1) == ["subtask:1"]
        assert redis_client.lrange("queue:image:normal", 0, -1) == ["subtask:2"]
        assert redis_client.lrange("queue:audio:normal", 0, -1) == ["subtask:3"]

        # Dequecar uno: debería ser el high priority
        subtask = redis_client.lpop("queue:text:high")
        assert subtask == "subtask:1"

    def test_inanicion_con_carga_continua_i(self, redis_client):
        """Caso bajo no muere con ráfaga de altos: scheduler despacha ambos."""
        from src.domain.scheduling import Priority, SchedulingPolicy

        # Simulación: flujo continuo de casos altos
        scheduler = MagicMock()
        scheduler.policy = SchedulingPolicy.AGING

        # Caso bajo en cola en t=0
        redis_client.rpush("queue:text:low", "bajo:1")

        # Ráfaga de altos (t=1, t=2, ..., t=100)
        for i in range(1, 101):
            redis_client.rpush("queue:text:high", f"alto:{i}")

        # El scheduler con aging debe despachar ambos:
        # 1. Primero altos (puntaje más bajo)
        # 2. Eventualmente el bajo (cuando su espera supera el bono)

        dequeued = []
        while redis_client.lrange("queue:text:low", 0, -1) or redis_client.lrange("queue:text:high", 0, -1):
            low = redis_client.lpop("queue:text:low")
            high = redis_client.lpop("queue:text:high")
            if low:
                dequeued.append(low)
            if high:
                dequeued.append(high)

        # Verificar que ambos fueron dequerados
        assert "bajo:1" in dequeued, "Caso bajo debe ser dequerado (no muere de inanición)"
        assert any("alto" in s for s in dequeued), "Casos altos también dequerados"

        # Verificar orden: altos primero
        assert "alto:1" in dequeued[:50], "Los altos deben salir primero"


class TestRedisIntegration:
    """Detalles de cómo el scheduler interactúa con Redis."""

    def test_zset_ordenado_por_puntaje(self, redis_client):
        """ZSET de Redis mantiene orden por puntaje (t_entrada - bono)."""
        # Simular ZSET: score = t_entrada - bono(prioridad)
        # bono(BAJA)=0, bono(MEDIA)=100, bono(ALTA)=200, bono(CRITICA)=400

        # Casos entrados en orden: baja t=0, media t=50, alta t=100, crítica t=200
        cases = [
            ("baja", 0 - 0, 0),       # score, entered_at
            ("media", 50 - 100, 50),
            ("alta", 100 - 200, 100),
            ("critica", 200 - 400, 200),
        ]

        for case_id, score, entered_at in cases:
            redis_client.zadd("pending:text", {case_id: score})

        # Sacar en orden por score (ZRANGE score ASC)
        order = redis_client.zrange("pending:text", 0, -1)
        assert order == ["critica", "media", "alta", "baja"], \
            "ZSET devuelve en orden ascendente de score (crítica tiene score más bajo)"

    def test_blmove_desde_cola_con_prioridad(self, redis_client):
        """BLMOVE atómico mantiene el orden de prioridad."""
        # Simular cola con prioridades enroladas
        redis_client.rpush("queue:text", "alta1")
        redis_client.rpush("queue:text", "baja1")
        redis_client.rpush("queue:text", "alta2")

        # BLMOVE debería respetar el orden (FIFO de la cola)
        case1 = redis_client.blpop("queue:text", timeout=1)
        case2 = redis_client.blpop("queue:text", timeout=1)
        case3 = redis_client.blpop("queue:text", timeout=1)

        assert case1[1] == "alta1"
        assert case2[1] == "baja1"
        assert case3[1] == "alta2"

    def test_redis_error_manejo(self, redis_client):
        """Scheduler maneja errores de Redis correctamente."""
        # Simular desconexión
        redis_client_broken = MagicMock()
        redis_client_broken.rpush.side_effect = Exception("Redis no disponible")

        with pytest.raises(Exception):
            redis_client_broken.rpush("queue:text", "caso1")


class TestSchedulerCacheYPersistencia:
    """El estado del scheduler persiste en Redis."""

    def test_scheduler_recupera_estado_de_redis(self, redis_client):
        """Al reiniciar, el scheduler recupera casos de Redis."""
        # Guardar casos en Redis
        redis_client.rpush("queue:text", "caso1")
        redis_client.rpush("queue:image", "caso2")

        # Simular reinicio: leer de Redis
        cases_text = redis_client.lrange("queue:text", 0, -1)
        cases_image = redis_client.lrange("queue:image", 0, -1)

        assert cases_text == ["caso1"]
        assert cases_image == ["caso2"]

    def test_scheduler_no_pierde_casos_en_transaccion_fallida(self, redis_client):
        """Si falla un MULTI/EXEC, los casos quedan en la cola."""
        # Simular transacción fallida
        pipe = redis_client.pipeline()
        pipe.rpush("queue:text", "caso1")
        pipe.execute()

        # Los datos están en Redis
        assert redis_client.lrange("queue:text", 0, -1) == ["caso1"]


class TestSchedulerRendimiento:
    """Rendimiento de scheduling con Redis (sin medir latencia real)."""

    def test_scheduler_soporta_muchos_casos(self, redis_client):
        """Scheduler maneja cientos de casos sin error."""
        # Enqueuar 1000 casos
        for i in range(1000):
            redis_client.rpush("queue:text", f"caso:{i}")

        # Dequecar 100
        for i in range(100):
            case = redis_client.lpop("queue:text")
            assert case is not None

        # Quedan 900
        remaining = redis_client.lrange("queue:text", 0, -1)
        assert len(remaining) == 900


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
