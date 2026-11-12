from enum import IntEnum

_BONOS_MS = {
    "BAJA": 0.0,
    "MEDIA": 100.0,
    "ALTA": 200.0,
    "CRITICA": 400.0,
}


class Priority(IntEnum):
    BAJA = 0
    MEDIA = 1
    ALTA = 2
    CRITICA = 3

    @classmethod
    def from_contract(cls, text: str) -> "Priority":
        try:
            return _PRIORIDAD_POR_PALABRA[text]
        except KeyError:
            raise ValueError(f"prioridad de contrato desconocida: {text!r}") from None

    def to_contract(self) -> str:
        for palabra, prioridad in _PRIORIDAD_POR_PALABRA.items():
            if prioridad is self:
                return palabra
        raise ValueError(f"la prioridad {self.name} no tiene palabra de contrato")

    @classmethod
    def from_name(cls, name: str) -> "Priority":
        try:
            return cls[name.upper()]
        except KeyError:
            raise ValueError(f"prioridad desconocida: {name}") from None

    def bonus_ms(self) -> float:
        """Bono de espera en ms: tiempo antes de que la prioridad suba un nivel (F-20, aging)."""
        return _BONOS_MS[self.name]

    def next_priority(self) -> "Priority":
        """Prioridad siguiente (máximo: CRITICA)."""
        if self is Priority.CRITICA:
            return Priority.CRITICA
        return Priority(self.value + 1)


_PRIORIDAD_POR_PALABRA = {"normal": Priority.MEDIA, "high": Priority.ALTA}
