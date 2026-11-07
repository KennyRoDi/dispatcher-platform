from collections import Counter
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from typing import TypeVar

T = TypeVar("T")
SIN_TEMA = "sin_tema"


@dataclass(frozen=True)
class MessageAnalysis:
    lemmas: tuple[str, ...]
    sentiment_label: str
    sentiment_score: float
    offense_score: float
    threat_patterns: tuple[str, ...]


def lotes(elementos: Sequence[T], tamano: int) -> Iterator[Sequence[T]]:
    if tamano <= 0:
        raise ValueError(f"el tamaño de lote debe ser positivo: {tamano}")
    for inicio in range(0, len(elementos), tamano):
        yield elementos[inicio : inicio + tamano]


def palabras_clave(lemas: Sequence[str], n: int) -> list[str]:
    # Counter conserva el orden de inserción en los empates: gana la primera aparición.
    return [lema for lema, _ in Counter(lemas).most_common(n)]


def tema(lemas: Sequence[str], lexico: Mapping[str, Sequence[str]]) -> tuple[str, float]:
    coincidencias = {nombre: _coincidencias(lemas, set(palabras)) for nombre, palabras in lexico.items()}
    mejor = max(coincidencias, key=coincidencias.get, default=None)
    if mejor is None or coincidencias[mejor] == 0:
        return SIN_TEMA, 0.0
    return mejor, coincidencias[mejor] / len(lemas)


def _coincidencias(lemas: Sequence[str], palabras: set[str]) -> int:
    return sum(lema in palabras for lema in lemas)


def sentimiento_del_lote(analisis: Sequence[MessageAnalysis]) -> tuple[str, float]:
    etiqueta, _ = Counter(a.sentiment_label for a in analisis).most_common(1)[0]
    puntajes = [a.sentiment_score for a in analisis if a.sentiment_label == etiqueta]
    return etiqueta, sum(puntajes) / len(puntajes)
