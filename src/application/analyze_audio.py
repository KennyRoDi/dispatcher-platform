from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from src.application.analyze_text import Indexado, TextModels, TextSettings, analyze_conversation
from src.domain.finding import EvidenceRef, Finding, Severity
from src.domain.transcription import TranscriptSegment, segmentos_como_mensajes, tramo

CATEGORIA_TRANSCRIPCION = "transcripcion"


class Transcriber(Protocol):
    def transcribe(self, path: Path) -> list[TranscriptSegment]: ...


@dataclass(frozen=True)
class SegmentPositions:
    segmentos: Sequence[TranscriptSegment]

    def rango(self, lote: Sequence[Indexado]) -> str:
        primero, ultimo = lote[0][0], lote[-1][0]
        indices = str(primero) if primero == ultimo else f"{primero}-{ultimo}"
        return f"segmentos {indices} t={tramo(self.segmentos[primero].inicio, self.segmentos[ultimo].fin)}"

    def lista(self, marcados: Sequence[Indexado]) -> str:
        indices = ",".join(str(indice) for indice, _ in marcados)
        tramos = ",".join(self._tramo(indice) for indice, _ in marcados)
        return f"segmentos {indices} t={tramos}"

    def detalle(self, marcados: Sequence[Indexado]) -> str:
        return "; ".join(f"{indice} t={self._tramo(indice)}" for indice, _ in marcados)

    def _tramo(self, indice: int) -> str:
        segmento = self.segmentos[indice]
        return tramo(segmento.inicio, segmento.fin)


def analyze_audio(
    segmentos: Iterable[TranscriptSegment], sha256: str, models: TextModels, ajustes: TextSettings
) -> list[Finding]:
    con_voz = [segmento for segmento in segmentos if segmento.texto]
    if not con_voz:
        return []
    transcripciones = [_transcripcion(indice, segmento, sha256) for indice, segmento in enumerate(con_voz)]
    analisis = analyze_conversation(
        segmentos_como_mensajes(con_voz), sha256, models, ajustes, posiciones=SegmentPositions(con_voz)
    )
    return transcripciones + analisis


def _transcripcion(indice: int, segmento: TranscriptSegment, sha256: str) -> Finding:
    posicion = EvidenceRef(sha256, f"segmento {indice} {segmento.intervalo}")
    return Finding(CATEGORIA_TRANSCRIPCION, Severity.BAJA, segmento.confianza, posicion, segmento.texto)
