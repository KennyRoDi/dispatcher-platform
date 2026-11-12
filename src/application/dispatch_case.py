import logging

from src.application.ports import Clock, WorkQueue
from src.domain.decomposition import CaseSource, decompose, queue_for
from src.domain.priority import Priority
from src.domain.subtask import QueueFull, Subtask

logger = logging.getLogger(__name__)


class DispatchCase:
    def __init__(self, queue: WorkQueue, clock: Clock) -> None:
        self._queue = queue
        self._clock = clock

    def execute(
        self, case_id: str, sources: list[CaseSource], priority: Priority
    ) -> list[tuple[str, Subtask]]:
        routed = [
            (queue_for(subtask.kind), subtask)
            for subtask in decompose(case_id, sources, priority, self._clock.now())
        ]
        self._require_capacity({queue for queue, _ in routed})
        for queue, subtask in routed:
            self._queue.enqueue(queue, subtask)
            logger.info(
                "routing case=%s subtask=%s kind=%s source=%s queue=%s",
                case_id, subtask.id, subtask.kind.value, subtask.source_sha256, queue,
            )
        return routed

    def _require_capacity(self, queues: set[str]) -> None:
        for queue in sorted(queues):
            if not self._queue.has_capacity(queue):
                raise QueueFull(queue)
