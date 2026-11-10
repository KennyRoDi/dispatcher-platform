from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol

from src.domain.chat_message import ChatMessage
from src.domain.finding import EvidenceRef, Finding
from src.domain.severity import SeverityRules, umbral_valido
from src.domain.text_analysis import MessageAnalysis, lotes, palabras_clave, sentimiento_del_lote, tema

Indexado = tuple[int, ChatMessage]


class TextModels(Protocol):
    def analyze_messages(self, texts: Sequence[str]) -> list[MessageAnalysis]: ...


class PositionFormat(Protocol):
    def rango(self, lote: Sequence[Indexado]) -> str: ...
    def lista(self, marcados: Sequence[Indexado]) -> str: ...
    def detalle(self, marcados: Sequence[Indexado]) -> str: ...


class MessagePositions:
    def rango(self, lote: Sequence[Indexado]) -> str:
        primero, ultimo = lote[0][0], lote[-1][0]
        return f"mensajes {primero}" if primero == ultimo else f"mensajes {primero}-{ultimo}"

    def lista(self, marcados: Sequence[Indexado]) -> str:
        return "mensajes " + ",".join(str(indice) for indice, _ in marcados)

    def detalle(self, marcados: Sequence[Indexado]) -> str:
        return "; ".join(f"{indice} {m.timestamp_utc.isoformat()} {m.source_ref}" for indice, m in marcados)


@dataclass(frozen=True)
class TextSettings:
    reglas: SeverityRules
    lexico: Mapping[str, Sequence[str]]
    tamano_lote: int = 50
    n_palabras_clave: int = 5
    umbral_ofensa: float = 0.5

    def __post_init__(self) -> None:
        object.__setattr__(self, "umbral_ofensa", umbral_valido(self.umbral_ofensa, "umbral_ofensa"))


def analyze_conversation(
    mensajes: Iterable[ChatMessage],
    sha256: str,
    models: TextModels,
    ajustes: TextSettings,
    posiciones: PositionFormat = MessagePositions(),
) -> list[Finding]:
    indexados = list(enumerate(mensajes))
    hallazgos: list[Finding] = []
    for lote in lotes(indexados, ajustes.tamano_lote):
        analisis = models.analyze_messages([mensaje.text for _, mensaje in lote])
        if len(analisis) != len(lote):
            raise ValueError(f"se esperaban {len(lote)} análisis, llegaron {len(analisis)}")
        hallazgos.extend(_LoteAnalizado(lote, analisis, sha256, ajustes, posiciones).hallazgos())
    return hallazgos


@dataclass(frozen=True)
class _LoteAnalizado:
    lote: Sequence[Indexado]
    analisis: Sequence[MessageAnalysis]
    sha256: str
    ajustes: TextSettings
    posiciones: PositionFormat

    def hallazgos(self) -> list[Finding]:
        lemas = [lema for analisis in self.analisis for lema in analisis.lemmas]
        nombre_tema, confianza_tema = tema(lemas, self.ajustes.lexico)
        etiqueta, confianza_sentimiento = sentimiento_del_lote(self.analisis)
        claves = palabras_clave(lemas, self.ajustes.n_palabras_clave)
        rango = self.posiciones.rango(self.lote)
        return [
            self._finding("palabras_clave", 1.0, ", ".join(claves), rango),
            self._finding("tema", confianza_tema, nombre_tema, rango),
            self._finding("sentimiento", confianza_sentimiento, etiqueta, rango),
            self._ofensa(rango),
        ]

    def _ofensa(self, rango: str) -> Finding:
        pares = list(zip(self.lote, self.analisis, strict=True))
        amenazas = [indexado for indexado, analisis in pares if analisis.threat_patterns]
        if amenazas:
            return self._marcados("amenaza", 1.0, amenazas)
        umbral = self.ajustes.umbral_ofensa
        ofensas = [(indexado, a.offense_score) for indexado, a in pares if a.offense_score >= umbral]
        if ofensas:
            marcados = [indexado for indexado, _ in ofensas]
            confianza = max(puntaje for _, puntaje in ofensas)
            return self._marcados("ofensivo", confianza, marcados)
        return self._finding("sin_ofensa", 1.0 - max(a.offense_score for a in self.analisis), "", rango)

    def _marcados(self, categoria: str, confianza: float, marcados: Sequence[Indexado]) -> Finding:
        return self._finding(categoria, confianza, self.posiciones.detalle(marcados), self.posiciones.lista(marcados))

    def _finding(self, categoria: str, confianza: float, detalle: str, posicion: str) -> Finding:
        severidad = self.ajustes.reglas.severity_for(categoria, confianza)
        return Finding(categoria, severidad, confianza, EvidenceRef(self.sha256, posicion), detalle)

