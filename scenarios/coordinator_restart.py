"""Escenario F-35: reinicio del coordinador con casos en curso.

El coordinador no tiene estado propio (AD-21): todo vive en Redis. Se simula
el reinicio conectando un cliente de Redis nuevo (o, en una corrida real,
reiniciando el proceso del coordinador) contra el mismo Redis, y se compara
el estado antes/despues. No reimplementa src/coordinator/main.py ni sus rutas.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path


def evaluar(creadas, contadas_antes, contadas_despues):
    problemas = []
    ids_antes = set(contadas_antes)
    ids_despues = set(contadas_despues)
    perdidas = ids_antes - ids_despues
    duplicadas = ids_despues - ids_antes

    if perdidas:
        problemas.append(f"sub-tareas perdidas tras el reinicio: {sorted(perdidas)}")
    if duplicadas:
        problemas.append(f"sub-tareas nuevas o duplicadas tras el reinicio: {sorted(duplicadas)}")
    if len(contadas_despues) != creadas:
        problemas.append(
            f"se crearon {creadas} sub-tareas pero después del reinicio hay {len(contadas_despues)}"
        )
    return {"cumple": not problemas, "problemas": problemas}


def tiempo_de_arranque(inicio, listo):
    diferencia = listo - inicio
    if diferencia < 0:
        raise ValueError(f"'listo' ({listo}) no puede ser anterior a 'inicio' ({inicio})")
    return diferencia


def correr_con_app_real(redis_url="redis://localhost:6379/0"):
    """Crea casos, "reinicia" el coordinador (nueva conexion a Redis) y compara."""
    from fastapi.testclient import TestClient

    import src.coordinator.main as main
    from src.coordinator import conexion

    try:
        import redis as redis_lib

        redis_client = redis_lib.Redis.from_url(redis_url, decode_responses=True)
        redis_client.ping()
        fuente = "redis real"
    except Exception:
        import fakeredis

        servidor = fakeredis.FakeServer()
        redis_client = fakeredis.FakeStrictRedis(server=servidor, decode_responses=True)
        fuente = "fakeredis (no se pudo conectar a redis real)"

    from src.coordinator.seguridad import autorizar

    main.app.dependency_overrides[autorizar] = lambda: None

    conexion.redis_client = redis_client
    cliente1 = TestClient(main.app)

    creado = cliente1.post("/cases", json={
        "subtasks": [
            {"task_type": "auto", "file_path": "videos/f35-a.mp4"},
            {"task_type": "auto", "file_path": "videos/f35-b.mp4"},
        ],
    }).json()
    case_id = creado["case_id"]
    detalle_antes = cliente1.get(f"/cases/{case_id}").json()
    contadas_antes = {s["subtask_id"]: s["status"] for s in detalle_antes["subtasks"]}

    # "Reinicio": conexion nueva a Redis. Con fakeredis, mismo FakeServer (misma base);
    # con Redis real, una conexion nueva ve exactamente los mismos datos persistidos.
    inicio = time.perf_counter()
    if fuente.startswith("fakeredis"):
        import fakeredis

        conexion.redis_client = fakeredis.FakeStrictRedis(server=servidor, decode_responses=True)
    else:
        import redis as redis_lib

        conexion.redis_client = redis_lib.Redis.from_url(redis_url, decode_responses=True)
    cliente2 = TestClient(main.app)
    respuesta_lista = cliente2.get("/stats")
    listo = time.perf_counter()
    respuesta_lista.raise_for_status()

    detalle_despues = cliente2.get(f"/cases/{case_id}").json()
    contadas_despues = {s["subtask_id"]: s["status"] for s in detalle_despues["subtasks"]}

    return {
        "creadas": len(contadas_antes),
        "contadas_antes": contadas_antes,
        "contadas_despues": contadas_despues,
        "tiempo_arranque_s": tiempo_de_arranque(inicio, listo),
        "fuente_redis": fuente,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Mide la retoma del coordinador tras un reinicio (F-35).")
    parser.add_argument("--redis-url", default="redis://localhost:6379/0")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)

    resultado = correr_con_app_real(args.redis_url)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8")
    print(args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
