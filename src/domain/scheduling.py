"""Dominio de planificación: prioridades y algoritmos de scheduling.

F-20: Prioridades con aging.
"""
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, Dict
import time

from src.domain.priority import Priority

__all__ = ["Priority", "SchedulingPolicy", "CaseEntry", "SchedulerState"]


class SchedulingPolicy(Enum):
    """Política de planificación: FIFO vs Aging."""

    FIFO = "fifo"
    AGING = "aging"

    @classmethod
    def desde_configuracion(cls, valor: str) -> "SchedulingPolicy":
        """Mapea un valor de configuración (ej. variable de entorno) a la política."""
        try:
            return cls(valor.lower())
        except ValueError as exc:
            opciones = ", ".join(p.value for p in cls)
            raise ValueError(f"política de scheduling desconocida: {valor!r} (opciones: {opciones})") from exc


@dataclass
class CaseEntry:
    """Un caso encolado."""

    case_id: str
    priority: Priority
    entered_at: float
    current_priority: Priority = field(default_factory=lambda: Priority.BAJA)
    aging_bonus_ms: float = 100.0  # Factor de escala para bonos

    def score(self, now: float) -> float:
        """Puntaje para ZSET: t_entrada - bono(prioridad_efectiva).

        Menor score sale primero (en Redis ZRANGE ASC).
        El bono crece: BAJA=0, MEDIA=100, ALTA=200, CRITICA=400.
        Ejemplo: caso BAJA entra en t=0, score = 0 - 0 = 0
                caso CRITICA entra en t=200, score = 200 - 400 = -200
        Orden: -200 (critica) < 0 (baja) → critica sale primero.
        """
        effective_priority = self._effective_priority_at(now)
        bonus = effective_priority.bonus_ms() * (self.aging_bonus_ms / 100.0)
        return self.entered_at - bonus

    def _effective_priority_at(self, now: float) -> Priority:
        """Prioridad efectiva según espera (aging).

        Si caso BAJA espera más de aging_bonus_ms (su bono = 0 + siguiente bono * factor),
        sube a MEDIA. Si espera más, sube a ALTA. Etc.
        """
        elapsed = now - self.entered_at
        prio = self.priority

        # Calcular cuántos escalones de bono se cumplieron
        while prio != Priority.CRITICA:
            next_prio = prio.next_priority()
            next_bonus = next_prio.bonus_ms() * (self.aging_bonus_ms / 100.0)

            # Si la espera supera el bono del siguiente nivel, sube
            if elapsed > next_bonus:
                prio = next_prio
            else:
                break

        return prio


class SchedulerState:
    """Estado del scheduler en memoria."""

    def __init__(self, policy: SchedulingPolicy, aging_bonus_ms: float = 100.0):
        self.policy = policy
        self.aging_bonus_ms = aging_bonus_ms
        self.cases: Dict[str, CaseEntry] = {}

    def enqueue(self, case_id: str, priority: Priority, entered_at: float) -> None:
        """Enquecar un caso."""
        if not case_id or not case_id.strip():
            raise ValueError("case_id no puede estar vacío")

        if not isinstance(priority, Priority):
            raise TypeError(f"priority debe ser Priority, no {type(priority)}")

        self.cases[case_id] = CaseEntry(
            case_id=case_id,
            priority=priority,
            entered_at=entered_at,
            current_priority=priority,
            aging_bonus_ms=self.aging_bonus_ms,
        )

    def next(self) -> Optional[str]:
        """Dequecar el siguiente caso según la política."""
        if not self.cases:
            return None

        now = time.time()

        if self.policy == SchedulingPolicy.FIFO:
            # FIFO puro: entrada más antigua
            case = min(self.cases.values(), key=lambda c: c.entered_at)
        else:  # AGING
            # Puntaje más bajo sale primero (score = t_entrada - bono)
            case = min(self.cases.values(), key=lambda c: c.score(now))

        del self.cases[case.case_id]
        return case.case_id

    def effective_priority(self, case_id: str) -> Priority:
        """Prioridad efectiva de un caso en este momento."""
        if case_id not in self.cases:
            raise KeyError(f"case_id {case_id} no encontrado")

        case = self.cases[case_id]
        now = time.time()
        return case._effective_priority_at(now)

    def __len__(self) -> int:
        return len(self.cases)
