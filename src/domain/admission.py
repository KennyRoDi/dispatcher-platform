from collections.abc import Iterable, Mapping


def _validate_bytes(value: int, name: str, minimum: int) -> None:
    if type(value) is not int or value < minimum:
        raise ValueError(f"{name} debe ser un entero de al menos {minimum} bytes")


def admits(*, current: int, max: int, footprint: int, margin: int) -> bool:
    _validate_bytes(current, "current", 0)
    _validate_bytes(max, "max", 1)
    _validate_bytes(footprint, "footprint", 1)
    _validate_bytes(margin, "margin", 0)
    return max - current >= footprint + margin


class FootprintTable:
    def __init__(self, footprints: Mapping[str, int]) -> None:
        for operation, footprint in footprints.items():
            _validate_bytes(footprint, f"footprint de {operation}", 1)
        self._footprints = dict(footprints)

    def minimum(self, operations: Iterable[str]) -> int:
        values = []
        for operation in operations:
            if operation not in self._footprints:
                raise ValueError(f"falta la huella de {operation}")
            values.append(self._footprints[operation])
        if not values:
            raise ValueError("se requiere al menos una operación")
        return min(values)
