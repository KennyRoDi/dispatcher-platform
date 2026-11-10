from collections.abc import Iterable


def _validate_bytes(value: int, name: str, minimum: int) -> None:
    if type(value) is not int or value < minimum:
        raise ValueError(f"{name} debe ser un entero de al menos {minimum} bytes")


def validate_node_budget(
    *, worker_limits: Iterable[int], node_memory: int, reserve: int
) -> None:
    _validate_bytes(node_memory, "node_memory", 1)
    _validate_bytes(reserve, "reserve", 0)
    if worker_limits is None:
        raise ValueError("worker_limits es obligatorio")

    required_memory = reserve
    for limit in worker_limits:
        _validate_bytes(limit, "worker_limit", 1)
        required_memory += limit

    if required_memory > node_memory:
        raise ValueError(
            f"El presupuesto de {required_memory} bytes excede "
            f"los {node_memory} bytes del nodo"
        )
