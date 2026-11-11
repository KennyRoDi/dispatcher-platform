from __future__ import annotations

from collections.abc import Callable, Mapping

import redis

from src.domain.backpressure import QueueLimit
from src.domain.subtask import QueueFull

INTENTOS = 5


def transaccion_acotada(cliente: redis.Redis, demanda: Mapping[str, int], limite: QueueLimit,
                        preparar: Callable[[redis.client.Pipeline], None]) -> None:
    """Ejecuta `preparar` en MULTI/EXEC solo si cada cola de `demanda` admite sus entrantes.

    `WATCH` aborta el `EXEC` si otro cliente cambia una cola entre el `LLEN` y el `EXEC`, así que el
    límite no se supera aunque haya productores concurrentes. Tras `INTENTOS` cambios seguidos se rechaza.
    """
    colas = sorted(demanda)
    with cliente.pipeline(transaction=True) as pipe:
        if limite.desactivado:
            preparar(pipe)
            pipe.execute()
            return
        for _ in range(INTENTOS):
            try:
                pipe.watch(*colas)
                lleno = next((c for c in colas if not limite.admite(pipe.llen(c), demanda[c])), None)
                if lleno is not None:
                    raise QueueFull(lleno)
                pipe.multi()
                preparar(pipe)
                pipe.execute()
                return
            except redis.WatchError:
                continue
            finally:
                pipe.reset()
    raise QueueFull(", ".join(colas))
