from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

PROFUNDIDAD_POR_DEFECTO = 1000
REINTENTO_POR_DEFECTO = 5


@dataclass(frozen=True)
class QueueLimit:
    """Profundidad máxima por cola (AD-12); `max_depth == 0` desactiva el límite para el experimento."""

    max_depth: int
    retry_after: int

    def __post_init__(self) -> None:
        if self.max_depth < 0:
            raise ValueError("QUEUE_MAX_DEPTH no puede ser negativo")
        if self.retry_after < 1:
            raise ValueError("QUEUE_RETRY_AFTER debe ser al menos 1 segundo")

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> "QueueLimit":
        return cls(
            max_depth=_entero(env, "QUEUE_MAX_DEPTH", PROFUNDIDAD_POR_DEFECTO),
            retry_after=_entero(env, "QUEUE_RETRY_AFTER", REINTENTO_POR_DEFECTO),
        )

    @property
    def desactivado(self) -> bool:
        return self.max_depth == 0

    def admite(self, profundidad: int, entrantes: int) -> bool:
        return self.desactivado or profundidad + entrantes <= self.max_depth


def _entero(env: Mapping[str, str], nombre: str, defecto: int) -> int:
    texto = env.get(nombre, "").strip()
    if not texto:
        return defecto
    try:
        return int(texto)
    except ValueError:
        raise ValueError(f"{nombre} debe ser un entero: {texto!r}") from None
