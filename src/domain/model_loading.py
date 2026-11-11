from dataclasses import dataclass


@dataclass(frozen=True)
class LoadingConfig:
    strategy: str
    processes: int

    def __post_init__(self) -> None:
        if not isinstance(self.strategy, str) or self.strategy not in (
            "por_proceso", "workers_compartidos"
        ):
            raise ValueError("estrategia de carga inválida")
        if type(self.processes) is not int or self.processes <= 0:
            raise ValueError("processes debe ser un entero positivo")
