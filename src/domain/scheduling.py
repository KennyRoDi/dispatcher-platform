"""Dominio de planificación: prioridades y algoritmos de scheduling.

F-20: Prioridades con aging.
"""
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, Dict
import time


class Priority(Enum):
    """Cuatro niveles de prioridad para casos."""

    BAJA = 0
    MEDIA = 1
    ALTA = 2
    CRITICA = 3

    def bonus_ms(self) -> float:
        """Bono de espera en ms: tiempo antes de que la prioridad sube un nivel."""
        bonos = {
            Priority.BAJA: 0.0,
            Priority.MEDIA: 100.0,
            Priority.ALTA: 200.0,
            Priority.CRITICA: 400.0,
        }
        return bonos[self]

    def next_priority(self) -> "Priority":
        """Prioridad siguiente (máximo: CRITICA)."""
        if self == Priority.CRITICA:
            return Priority.CRITICA
        return Priority(self.value + 1)


class SchedulingPolicy(Enum):
    """Política de planificación: FIFO vs Aging."""

    FIFO = "fifo"
    AGING = "aging"


@dataclass
class CaseEntry:
    """Un caso encolado."""

    case_id: str
    priority: Priority
    entered_at: float
    current_priority: Priority = field(default_factory=lambda: Priority.BAJA)

    def score(self, now: float) -> float:
        """Puntaje para ZSET: t_entrada - bono(prioridad).

        Menor score sale primero (rojo en Redis ZRANGE).
        El bono aumenta con la espera, así que la prioridad efectiva sube.
        """
        elapsed = now - self.entered_at
        effective_priority = self._effective_priority_at(now)
        bonus = effective_priority.bonus_ms()
        return self.entered_at - bonus

    def _effective_priority_at(self, now: float) -> Priority:
        """Prioridad efectiva según espera (aging)."""
        elapsed = now - self.entered_at
        prio = self.priority

        while prio != Priority.CRITICA and elapsed > prio.bonus_ms():
            elapsed -= prio.bonus_ms()
            prio = prio.next_priority()

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
            # Puntaje más bajo sale primero
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
