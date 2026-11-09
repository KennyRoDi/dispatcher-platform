import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from src.domain.finding import Severity

CAMPOS_DE_REGLA = ("categoria", "umbral", "nivel")


@dataclass(frozen=True)
class SeverityRule:
    umbral: float
    nivel: Severity


@dataclass(frozen=True)
class SeverityRules:
    por_categoria: Mapping[str, SeverityRule]

    @classmethod
    def from_dict(cls, datos: Mapping[str, Any], obligatoria: str = "amenaza") -> "SeverityRules":
        reglas: dict[str, SeverityRule] = {}
        for datos_regla in _lista_de_reglas(datos.get("severidad", [])):
            categoria = _campos_de_regla(datos_regla)
            # Una regla repetida reemplazaría a la anterior y podría degradar en silencio una severidad alta.
            if categoria in reglas:
                raise ValueError(f"regla de severidad duplicada para la categoría «{categoria}»")
            reglas[categoria] = _regla(datos_regla)
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


def _lista_de_reglas(valor: Any) -> list[Mapping[str, Any]]:
    if not isinstance(valor, list) or not all(isinstance(regla, Mapping) for regla in valor):
        raise ValueError("severidad debe ser una lista de tablas [[severidad]]")
    return valor


def _campos_de_regla(datos: Mapping[str, Any]) -> str:
    faltantes = [campo for campo in CAMPOS_DE_REGLA if campo not in datos]
    if faltantes:
        raise ValueError(f"regla de severidad sin {', '.join(faltantes)}: {dict(datos)!r}")
    if not isinstance(datos["categoria"], str):
        raise ValueError(f"la categoría de una regla de severidad debe ser texto: {datos['categoria']!r}")
    return datos["categoria"]


def _regla(datos: Mapping[str, Any]) -> SeverityRule:
    try:
        nivel = Severity(datos["nivel"])
    except ValueError:
        raise ValueError(f"nivel de severidad desconocido: {datos['nivel']}") from None
    return SeverityRule(umbral_valido(datos["umbral"], "umbral"), nivel)
