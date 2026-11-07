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
    def from_dict(cls, datos: Mapping[str, Any]) -> "SeverityRules":
        return cls({regla["categoria"]: _regla(regla) for regla in datos.get("severidad", [])})

    def severity_for(self, categoria: str, confianza: float) -> Severity:
        regla = self.por_categoria.get(categoria)
        if regla is None or confianza < regla.umbral:
            return Severity.BAJA
        return regla.nivel


def _regla(datos: Mapping[str, Any]) -> SeverityRule:
    try:
        nivel = Severity(datos["nivel"])
    except ValueError:
        raise ValueError(f"nivel de severidad desconocido: {datos['nivel']}") from None
    return SeverityRule(float(datos["umbral"]), nivel)
