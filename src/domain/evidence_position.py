import re
from dataclasses import dataclass
from datetime import datetime, timezone

from src.domain.finding import Finding

# re.ASCII y topes de dígitos: \d de Unicode acepta «٣» y un índice de miles de dígitos hace fallar int().
_ENTERO = r"\d{1,9}"
_INDICES = rf"{_ENTERO}(?:,{_ENTERO})*"
_TRAMO = rf"{_ENTERO}(?:\.{_ENTERO})?-{_ENTERO}(?:\.{_ENTERO})?s"
_MENSAJES = re.compile(rf"mensajes ({_INDICES})", re.ASCII)
_SEGMENTO = re.compile(rf"segmento ({_ENTERO}) t=({_TRAMO})", re.ASCII)
_SEGMENTOS = re.compile(rf"segmentos ({_INDICES}) t=({_TRAMO}(?:,{_TRAMO})*)", re.ASCII)
_CAJA = re.compile(rf"caja ({_ENTERO}),({_ENTERO}),({_ENTERO}),({_ENTERO})", re.ASCII)
_SEGUNDOS = rf"{_ENTERO}(?:\.{_ENTERO})?"
_FOTOGRAMA = re.compile(rf"fotograma t=({_SEGUNDOS})s (caja .+)", re.ASCII)
_LOTE = re.compile(r"(?:mensajes \d+-\d+|segmentos \d+-\d+ t=.+)", re.ASCII)
_ENTRADA_DE_DETALLE = re.compile(rf"({_ENTERO}) (\S+) (.*)", re.ASCII)


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
class FrameLocator:
    t_s: float
    box: BoxLocator


@dataclass(frozen=True)
class UnknownLocator:
    raw: str


Locator = MessageLocator | SegmentLocator | BoxLocator | FrameLocator | UnknownLocator


def parse_position(finding: Finding) -> tuple[Locator, ...]:
    posicion = finding.evidence.position
    if _LOTE.fullmatch(posicion):
        return ()
    locadores = _mensajes(posicion, finding.detail) or _segmentos(posicion) or _caja(posicion) or _fotograma(posicion)
    return locadores or (UnknownLocator(posicion),)


def _mensajes(posicion: str, detalle: str) -> tuple[MessageLocator, ...]:
    coincidencia = _MENSAJES.fullmatch(posicion)
    if not coincidencia:
        return ()
    marcas = _marcas_del_detalle(detalle)
    return tuple(MessageLocator(indice, *marcas.get(indice, (None, None))) for indice in _enteros(coincidencia[1]))


def _segmentos(posicion: str) -> tuple[SegmentLocator, ...]:
    if coincidencia := _SEGMENTO.fullmatch(posicion):
        indices, tramos = [int(coincidencia[1])], [coincidencia[2]]
    elif coincidencia := _SEGMENTOS.fullmatch(posicion):
        indices, tramos = _enteros(coincidencia[1]), coincidencia[2].split(",")
    else:
        return ()
    # Un tramo por índice, y ninguno invertido: si no, la posición no es de un analizador.
    if len(indices) != len(tramos):
        return ()
    locadores = tuple(_segmento(indice, tramo) for indice, tramo in zip(indices, tramos))
    return locadores if all(loc.start_s <= loc.end_s for loc in locadores) else ()


def _caja(posicion: str) -> tuple[BoxLocator, ...]:
    coincidencia = _CAJA.fullmatch(posicion)
    if not coincidencia:
        return ()
    x1, y1, x2, y2 = (int(valor) for valor in coincidencia.groups())
    return (BoxLocator(x1, y1, x2, y2),) if x1 <= x2 and y1 <= y2 else ()


def _fotograma(posicion: str) -> tuple[FrameLocator, ...]:
    coincidencia = _FOTOGRAMA.fullmatch(posicion)
    caja = _caja(coincidencia[2]) if coincidencia else ()
    return (FrameLocator(float(coincidencia[1]), caja[0]),) if caja else ()


def frame_position(t_s: float, box_position: str) -> str:
    segundos = f"{t_s:.3f}".rstrip("0").rstrip(".")
    return f"fotograma t={segundos}s {box_position}"


def _enteros(texto: str) -> list[int]:
    return [int(valor) for valor in texto.split(",")]


def _segmento(indice: int, tramo: str) -> SegmentLocator:
    inicio, fin = tramo.removesuffix("s").split("-")
    return SegmentLocator(indice, float(inicio), float(fin))


def _marcas_del_detalle(detalle: str) -> dict[int, tuple[datetime, str]]:
    marcas: dict[int, tuple[datetime, str]] = {}
    ambiguos: set[int] = set()
    for entrada in detalle.split("; "):
        coincidencia = _ENTRADA_DE_DETALLE.fullmatch(entrada)
        if not coincidencia:
            continue
        indice = int(coincidencia[1])
        # El source_ref lo controla quien exportó el chat: un índice repetido podría falsear la marca real.
        if indice in marcas or indice in ambiguos:
            marcas.pop(indice, None)
            ambiguos.add(indice)
            continue
        instante = _instante_utc(coincidencia[2])
        if instante is not None:
            marcas[indice] = (instante, coincidencia[3])
    return marcas


def _instante_utc(texto: str) -> datetime | None:
    try:
        instante = datetime.fromisoformat(texto)
        return instante.astimezone(timezone.utc) if instante.tzinfo is not None else None
    except (ValueError, OverflowError):
        return None
