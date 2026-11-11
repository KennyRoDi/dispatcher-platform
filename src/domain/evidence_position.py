import re
from dataclasses import dataclass
from datetime import datetime, timezone

from src.domain.finding import Finding

_INDICES = r"\d+(?:,\d+)*"
_TRAMO = r"\d+(?:\.\d+)?-\d+(?:\.\d+)?s"
_MENSAJES = re.compile(rf"mensajes ({_INDICES})")
_SEGMENTO = re.compile(rf"segmento (\d+) t=({_TRAMO})")
_SEGMENTOS = re.compile(rf"segmentos ({_INDICES}) t=({_TRAMO}(?:,{_TRAMO})*)")
_CAJA = re.compile(r"caja (\d+),(\d+),(\d+),(\d+)")
_LOTE = re.compile(r"(?:mensajes \d+-\d+|segmentos \d+-\d+ t=.+)")


@dataclass(frozen=True)
class MessageLocator:
    index: int
    timestamp_utc: datetime | None
    source_ref: str | None


@dataclass(frozen=True)
class SegmentLocator:
    index: int
    start_s: float
    end_s: float


@dataclass(frozen=True)
class BoxLocator:
    x1: int
    y1: int
    x2: int
    y2: int


@dataclass(frozen=True)
class UnknownLocator:
    raw: str


Locator = MessageLocator | SegmentLocator | BoxLocator | UnknownLocator


def parse_position(finding: Finding) -> tuple[Locator, ...]:
    posicion = finding.evidence.position
    if _LOTE.fullmatch(posicion):
        return ()
    if coincidencia := _MENSAJES.fullmatch(posicion):
        return _mensajes(_enteros(coincidencia[1]), finding.detail)
    if coincidencia := _SEGMENTO.fullmatch(posicion):
        return (_segmento(int(coincidencia[1]), coincidencia[2]),)
    if coincidencia := _SEGMENTOS.fullmatch(posicion):
        indices, tramos = _enteros(coincidencia[1]), coincidencia[2].split(",")
        # Un tramo por índice: si no cuadran, la posición no es de este formato.
        if len(indices) == len(tramos):
            return tuple(_segmento(indice, tramo) for indice, tramo in zip(indices, tramos))
    if coincidencia := _CAJA.fullmatch(posicion):
        return (BoxLocator(*map(int, coincidencia.groups())),)
    return (UnknownLocator(posicion),)


def _enteros(texto: str) -> list[int]:
    return [int(valor) for valor in texto.split(",")]


def _segmento(indice: int, tramo: str) -> SegmentLocator:
    inicio, fin = tramo.removesuffix("s").split("-")
    return SegmentLocator(indice, float(inicio), float(fin))


def _mensajes(indices: list[int], detalle: str) -> tuple[MessageLocator, ...]:
    marcas = _marcas_del_detalle(detalle)
    return tuple(MessageLocator(indice, *marcas.get(indice, (None, None))) for indice in indices)


def _marcas_del_detalle(detalle: str) -> dict[int, tuple[datetime, str]]:
    marcas: dict[int, tuple[datetime, str]] = {}
    for entrada in detalle.split("; "):
        partes = entrada.split(" ", 2)
        if len(partes) == 3 and partes[0].isdigit():
            try:
                instante = datetime.fromisoformat(partes[1])
            except ValueError:
                continue
            if instante.tzinfo is not None:
                marcas[int(partes[0])] = (instante.astimezone(timezone.utc), partes[2])
    return marcas
