import math
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from src.domain.chat_message import ChatMessage
from src.domain.severity import umbral_valido

REMITENTE_DE_AUDIO = "audio"
# El analizador solo recibe la ruta y no conoce la hora de la nota; la época solo satisface la zona horaria
# que exige ChatMessage. La hora real la combina el reporte (SUP-15).
INICIO_DEL_AUDIO = datetime(1970, 1, 1, tzinfo=timezone.utc)
# Más allá de esto, la época más el tiempo pasa de datetime.max y datetime lanza OverflowError.
TIEMPO_MAXIMO_S = (datetime.max.replace(tzinfo=timezone.utc) - INICIO_DEL_AUDIO).total_seconds() - 1


@dataclass(frozen=True)
class TranscriptSegment:
    inicio: float
    fin: float
    texto: str
    confianza: float

    def __post_init__(self) -> None:
        if not (es_tiempo(self.inicio) and es_tiempo(self.fin) and self.inicio <= self.fin):
            raise ValueError(f"tiempos de segmento inválidos: inicio={self.inicio}, fin={self.fin}")
        object.__setattr__(self, "confianza", umbral_valido(self.confianza, "confianza"))
        object.__setattr__(self, "texto", self.texto.strip())

    @property
    def intervalo(self) -> str:
        return f"t={tramo(self.inicio, self.fin)}"


def es_tiempo(valor: object) -> bool:
    # bool es subclase de int: sin excluirlo, True pasaría como 1 segundo.
    es_numero = isinstance(valor, (int, float)) and not isinstance(valor, bool)
    return es_numero and math.isfinite(valor) and 0 <= valor <= TIEMPO_MAXIMO_S


def tramo(inicio: float, fin: float) -> str:
    return f"{inicio:.2f}-{fin:.2f}s"


def segmentos_como_mensajes(segmentos: Iterable[TranscriptSegment]) -> list[ChatMessage]:
    return [
        ChatMessage(
            INICIO_DEL_AUDIO + timedelta(seconds=segmento.inicio),
            REMITENTE_DE_AUDIO,
            segmento.texto,
            segmento.intervalo,
        )
        for segmento in segmentos
    ]
