from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from src.domain.finding import EvidenceRef, Finding
from src.domain.severity import SeverityRules, umbral_valido

Box = tuple[int, int, int, int]


@dataclass(frozen=True)
class Detection:
    label: str
    confidence: float
    box: Box

    def __post_init__(self) -> None:
        if not isinstance(self.label, str) or not self.label:
            raise ValueError(f"la etiqueta debe ser texto no vacío: {self.label!r}")
        umbral_valido(self.confidence, "confidence")
        if not _caja_valida(self.box):
            raise ValueError(f"la caja debe ser x1,y1,x2,y2 en enteros no negativos, con x1<=x2 e y1<=y2: {self.box!r}")


def sensitive_findings(
    detecciones: Iterable[Detection],
    sha256: str,
    mapa: Mapping[str, str],
    umbral_minimo: float,
    reglas: SeverityRules,
) -> list[Finding]:
    por_categoria: dict[str, list[Detection]] = {}
    for deteccion in detecciones:
        if deteccion.label in mapa and deteccion.confidence >= umbral_minimo:
            por_categoria.setdefault(mapa[deteccion.label], []).append(deteccion)
    return [_finding(categoria, grupo, sha256, reglas) for categoria, grupo in sorted(por_categoria.items())]


def _finding(categoria: str, grupo: list[Detection], sha256: str, reglas: SeverityRules) -> Finding:
    # Desempatar por la caja hace que el resultado no dependa del orden en que el modelo entrega las cajas.
    mejor = max(grupo, key=lambda deteccion: (deteccion.confidence, deteccion.box))
    severidad = reglas.severity_for(categoria, mejor.confidence)
    posicion = "caja " + ",".join(str(coordenada) for coordenada in mejor.box)
    return Finding(categoria, severidad, mejor.confidence, EvidenceRef(sha256, posicion), _detalle(grupo))


def _detalle(grupo: list[Detection]) -> str:
    conteo = Counter(deteccion.label for deteccion in grupo)
    return ", ".join(f"{etiqueta} ×{cantidad}" for etiqueta, cantidad in sorted(conteo.items()))


def _caja_valida(caja: object) -> bool:
    if not isinstance(caja, tuple) or len(caja) != 4:
        return False
    # bool es subclase de int: sin excluirlo, True pasaría como la coordenada 1.
    if not all(isinstance(valor, int) and not isinstance(valor, bool) and valor >= 0 for valor in caja):
        return False
    x1, y1, x2, y2 = caja
    return x1 <= x2 and y1 <= y2
