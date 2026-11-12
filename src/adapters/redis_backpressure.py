from __future__ import annotations

from collections.abc import Callable, Mapping
from itertools import chain

import redis

from src.domain.backpressure import CaseTooLarge, QueueLimit
from src.domain.subtask import QueueFull

# Redis ejecuta el script sin intercalar otros comandos: comprobar LLEN y escribir es atómico y,
# a diferencia de WATCH, no falla porque otro productor o un worker toquen la cola (AD-12).
_ESCRIBIR_SI_CABE = """
local limite = tonumber(ARGV[1])
local i = 3
for _ = 1, tonumber(ARGV[2]) do
  if redis.call('LLEN', ARGV[i]) + tonumber(ARGV[i + 1]) > limite then
    return ARGV[i]
  end
  i = i + 2
end
local comandos = tonumber(ARGV[i])
i = i + 1
for _ = 1, comandos do
  local argc = tonumber(ARGV[i])
  redis.call(unpack(ARGV, i + 1, i + argc))
  i = i + argc + 1
end
return false
"""


class _Comandos:
    """Registra las escrituras de `preparar` para ejecutarlas dentro del script."""

    def __init__(self) -> None:
        self.lista: list[list[str]] = []

    def hset(self, key: str, mapping: Mapping[str, object]) -> None:
        self._agregar("HSET", key, *chain.from_iterable(mapping.items()))

    def sadd(self, key: str, *valores: object) -> None:
        self._agregar("SADD", key, *valores)

    def rpush(self, key: str, *valores: object) -> None:
        self._agregar("RPUSH", key, *valores)

    def _agregar(self, *argumentos: object) -> None:
        self.lista.append([str(argumento) for argumento in argumentos])


def transaccion_acotada(cliente: redis.Redis, demanda: Mapping[str, int], limite: QueueLimit,
                        preparar: Callable[[object], None]) -> None:
    """Ejecuta las escrituras de `preparar` solo si cada cola de `demanda` admite sus entrantes.

    `preparar` recibe un objeto con `hset(key, mapping=...)`, `sadd` y `rpush`. Lanza `QueueFull`
    si alguna cola no admite y `CaseTooLarge` si una cola no admitiría el caso ni vacía.
    """
    if limite.desactivado:
        with cliente.pipeline(transaction=True) as pipe:
            preparar(pipe)
            pipe.execute()
        return
    for cola, entrantes in demanda.items():
        if not limite.cabe_alguna_vez(entrantes):
            raise CaseTooLarge(cola)
    comandos = _Comandos()
    preparar(comandos)
    argumentos: list[object] = [limite.max_depth, len(demanda)]
    for cola in sorted(demanda):
        argumentos += [cola, demanda[cola]]
    argumentos.append(len(comandos.lista))
    for comando in comandos.lista:
        argumentos += [len(comando), *comando]
    llena = cliente.eval(_ESCRIBIR_SI_CABE, 0, *argumentos)
    if llena:
        raise QueueFull(llena)


_MOVER_SI_CABE = """
if redis.call('LLEN', KEYS[1]) >= tonumber(ARGV[1]) then
  return 0
end
redis.call('RPUSH', KEYS[1], ARGV[2])
return 1
"""


def mover_acotado(cliente: redis.Redis, cola: str, payload: str, limite: QueueLimit) -> bool:
    """Encola `payload` solo si `cola` está por debajo del límite (AD-12); el scheduler no mueve si no cabe."""
    if limite.desactivado:
        cliente.rpush(cola, payload)
        return True
    return bool(cliente.eval(_MOVER_SI_CABE, 1, cola, limite.max_depth, payload))
