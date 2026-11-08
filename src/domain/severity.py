import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from src.domain.finding import Severity


@dataclass(frozen=True)
class SeverityRule:
    umbral: float
    nivel: Severity


@dataclass(frozen=True)
class SeverityRules:
    por_categoria: Mapping[str, SeverityRule]

    @classmethod
    def from_dict(cls, datos: Mapping[str, Any], obligatoria: str = "amenaza") -> "SeverityRules":
        reglas = {regla["categoria"]: _regla(regla) for regla in datos.get("severidad", [])}
        if obligatoria not in reglas:
            raise ValueError(f"falta una regla de severidad para la categoría «{obligatoria}» (SUP-07)")
        return cls(reglas)

    def severity_for(self, categoria: str, confianza: float) -> Severity:
        regla = self.por_categoria.get(categoria)
        if regla is None or confianza < regla.umbral:
            return Severity.BAJA
        return regla.nivel


def umbral_valido(valor: Any, nombre: str) -> float:
    # bool es subclase de int: sin excluirlo, `true` en el TOML pasaría como 1.
    es_numero = isinstance(valor, (int, float)) and not isinstance(valor, bool)
    if not es_numero or not math.isfinite(valor) or not 0 <= valor <= 1:
        raise ValueError(f"{nombre} debe ser un número finito entre 0 y 1: {valor!r}")
    return float(valor)


def _regla(datos: Mapping[str, Any]) -> SeverityRule:
    try:
        nivel = Severity(datos["nivel"])
    except ValueError:
        raise ValueError(f"nivel de severidad desconocido: {datos['nivel']}") from None
    return SeverityRule(umbral_valido(datos["umbral"], "umbral"), nivel)
