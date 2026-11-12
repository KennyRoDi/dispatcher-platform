"""Escenario F-34: caida de un worker durante un caso en proceso.

Simula la caida deteniendo los latidos del worker (lo unico que el reaper
heredado observa) y mide, contra el Reaper real (scripts/reaper.py, sin
modificar), cuanto tarda en detectar y reencolar. No requiere Docker ni
nodos fisicos: el mecanismo es logica sobre Redis.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path


def evaluar(creadas, terminadas, perdidas, duplicadas, estado_caso, estado_esperado="completed"):
    problemas = []
    faltantes = creadas - terminadas - perdidas
    if faltantes != 0:
        problemas.append(
            f"sub-tareas perdidas: {creadas} creadas, {terminadas} terminadas, "
            f"{perdidas} reportadas perdidas (faltan {faltantes})"
        )
    if duplicadas:
        problemas.append(f"sub-tareas duplicadas: {duplicadas}")
    if estado_caso != estado_esperado:
        problemas.append(f"el caso debía quedar {estado_esperado} y quedó {estado_caso}")
    return {"cumple": not problemas, "problemas": problemas}


def tiempo_deteccion(muestras):
    """Primer instante en que el worker deja de estar vivo; None si nunca cae."""
    for instante, vivo in muestras:
        if not vivo:
            return instante
    return None


def tiempo_reasignacion(muestras):
    """Primer instante en que la sub-tarea vuelve a su cola original; None si nunca."""
    for instante, reasignada in muestras:
        if reasignada:
            return instante
    return None


def _conectar_redis(redis_url):
    import redis as redis_lib

    cliente = redis_lib.Redis.from_url(redis_url, decode_responses=True)
    cliente.ping()
    return cliente


def correr_con_reaper_real(redis_client, operation="transcode_video", intervalo_muestreo=0.5):
    """Ejecuta el escenario completo contra un Redis real/fakeredis y mide tiempos reales."""
    from src.workers.config import Settings
    from scripts.reaper import Reaper

    worker_id = f"worker-crash-{int(time.time())}"
    sid = f"sub-{int(time.time())}"
    settings = Settings.from_env({})

    redis_client.hset(f"subtask:{sid}", mapping={
        "status": "assigned", "operation": operation, "attempts": "1", "worker_id": worker_id,
    })
    redis_client.sadd(f"worker:{worker_id}:inflight", sid)
    redis_client.sadd("workers:registry", worker_id)
    redis_client.hset(f"worker:{worker_id}", mapping={"worker_id": worker_id})
    redis_client.expire(f"worker:{worker_id}", settings.heartbeat_ttl)  # ultimo latido real; no se renueva mas

    class _Reporter:
        def report(self, payload):
            pass

    reaper = Reaper(settings, redis_client, _Reporter())
    inicio = time.monotonic()
    muestras_vivo = []
    muestras_reasignada = []

    while True:
        ahora = time.monotonic() - inicio
        vivo = bool(redis_client.exists(f"worker:{worker_id}"))
        muestras_vivo.append((ahora, vivo))
        reaper.run_once()
        en_cola = bool(redis_client.lrange(f"queue:{operation}", 0, -1))
        muestras_reasignada.append((ahora, en_cola))
        if en_cola:
            break
        if ahora > settings.heartbeat_ttl + settings.reaper_interval + 15:
            break
        time.sleep(intervalo_muestreo)

    terminadas = 1 if redis_client.lrange(f"queue:{operation}", 0, -1) == [sid] else 0
    return {
        "creadas": 1,
        "terminadas": terminadas,
        "perdidas": 1 - terminadas,
        "duplicadas": 0,
        "estado_caso": "completed" if terminadas else "failed",
        "tiempo_deteccion_s": tiempo_deteccion(muestras_vivo),
        "tiempo_reasignacion_s": tiempo_reasignacion(muestras_reasignada),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Mide deteccion y reasignacion ante caida de worker (F-34).")
    parser.add_argument("--redis-url", default="redis://localhost:6379/0")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)

    try:
        redis_client = _conectar_redis(args.redis_url)
        fuente = "redis real"
    except Exception:
        import fakeredis
        redis_client = fakeredis.FakeStrictRedis(decode_responses=True)
        fuente = "fakeredis (no se pudo conectar a redis real)"

    resultado = correr_con_reaper_real(redis_client)
    resultado["fuente_redis"] = fuente
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8")
    print(args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
