import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from src.domain.finding import Severity

CATEGORIA_OBLIGATORIA = "amenaza"
CAMPOS_DE_REGLA = ("categoria", "umbral", "nivel")


@dataclass(frozen=True)
class SeverityRule:
    umbral: float
    nivel: Severity


@dataclass(frozen=True)
class SeverityRules:
    por_categoria: Mapping[str, SeverityRule]

    @classmethod
    def from_dict(cls, datos: Mapping[str, Any]) -> "SeverityRules":
        lista = datos.get("severidad", [])
        if not isinstance(lista, list):
            raise ValueError(f"severidad debe ser una lista de reglas: {lista!r}")
        reglas: dict[str, SeverityRule] = {}
        for regla in lista:
            categoria = _categoria(regla)
            if categoria in reglas:
                raise ValueError(f"regla de severidad duplicada para la categoría «{categoria}»")
            reglas[categoria] = _regla(regla)
        if CATEGORIA_OBLIGATORIA not in reglas:
            raise ValueError(f"falta una regla de severidad para la categoría «{CATEGORIA_OBLIGATORIA}» (SUP-07)")
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


def _categoria(regla: Any) -> str:
    if not isinstance(regla, Mapping):
        raise ValueError(f"cada regla de severidad debe ser una tabla: {regla!r}")
    faltantes = [campo for campo in CAMPOS_DE_REGLA if campo not in regla]
    if faltantes:
        raise ValueError(f"a la regla de severidad le falta {', '.join(faltantes)}: {dict(regla)!r}")
    # Una clave suelta escrita tras [[severidad]] en el TOML cae dentro de la regla, no en la raíz.
    desconocidos = [campo for campo in regla if campo not in CAMPOS_DE_REGLA]
    if desconocidos:
        raise ValueError(f"campo desconocido en la regla de severidad: {', '.join(map(str, desconocidos))}")
    categoria = regla["categoria"]
    if not isinstance(categoria, str) or not categoria:
        raise ValueError(f"la categoria de una regla debe ser texto no vacío: {categoria!r}")
    return categoria


def _regla(datos: Mapping[str, Any]) -> SeverityRule:
    try:
        nivel = Severity(datos["nivel"])
    except ValueError:
        raise ValueError(f"nivel de severidad desconocido: {datos['nivel']}") from None
    return SeverityRule(umbral_valido(datos["umbral"], "umbral"), nivel)
