from enum import IntEnum


class Priority(IntEnum):
    BAJA = 0
    MEDIA = 1
    ALTA = 2
    CRITICA = 3

    @classmethod
    def from_name(cls, name: str) -> "Priority":
        try:
            return cls[name.upper()]
        except KeyError:
            raise ValueError(f"prioridad desconocida: {name}") from None
