import math
from dataclasses import dataclass


@dataclass(frozen=True)
class Corrida:
    config: str
    repeticion: int
    segundos: float
    audio_segundos: float
    memoria_pico_mb: float


@dataclass(frozen=True)
class ResumenConfig:
    config: str
    latencia_media_s: float
    latencia_p95_s: float
    throughput_x_realtime: float
    memoria_pico_mb: float
    repeticiones: int


def resumir(corridas: list[Corrida]) -> list[ResumenConfig]:
    if not corridas:
        raise ValueError("se necesita al menos una corrida")
    grupos: dict[str, list[Corrida]] = {}
    for corrida in corridas:
        if corrida.segundos <= 0 or corrida.audio_segundos <= 0:
            raise ValueError(f"corrida inválida en {corrida.config}: tiempos deben ser positivos")
        grupos.setdefault(corrida.config, []).append(corrida)
    return [_resumir_grupo(config, grupo) for config, grupo in grupos.items()]


def _resumir_grupo(config: str, grupo: list[Corrida]) -> ResumenConfig:
    tiempos = sorted(c.segundos for c in grupo)
    total = sum(tiempos)
    return ResumenConfig(
        config=config,
        latencia_media_s=total / len(tiempos),
        latencia_p95_s=tiempos[math.ceil(0.95 * len(tiempos)) - 1],
        throughput_x_realtime=sum(c.audio_segundos for c in grupo) / total,
        memoria_pico_mb=max(c.memoria_pico_mb for c in grupo),
        repeticiones=len(grupo),
    )
