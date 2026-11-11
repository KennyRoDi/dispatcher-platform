import shutil
import signal
from collections.abc import Callable, Sequence
from datetime import timedelta
from pathlib import Path

from src.application.ports import Clock, ProcessRunner

POLL_SECONDS = 0.1
SIGKILL = getattr(signal, "SIGKILL", 9)


class ProcessSupervisor:
    def __init__(
        self,
        runner: ProcessRunner,
        clock: Clock,
        sleep: Callable[[float], None],
        grace_seconds: float = 10.0,
    ):
        self._runner = runner
        self._clock = clock
        self._sleep = sleep
        self._grace = timedelta(seconds=grace_seconds)
        self._scratch: dict[int, Path] = {}

    def start(self, argv: Sequence[str], scratch: Path) -> int:
        scratch.mkdir(parents=True, exist_ok=True)
        pid = self._runner.start(argv)
        self._scratch[pid] = scratch
        return pid

    def cancel(self, pid: int) -> None:
        try:
            self._terminate(pid)
        finally:
            shutil.rmtree(self._scratch.pop(pid), ignore_errors=True)

    def _terminate(self, pid: int) -> None:
        self._signal(pid, signal.SIGTERM)
        if self._wait_for_exit(pid):
            return
        self._signal(pid, SIGKILL)
        self._runner.reap(pid, block=True)

    def _wait_for_exit(self, pid: int) -> bool:
        limite = self._clock.now() + self._grace
        while True:
            if self._runner.reap(pid, block=False):
                return True
            if self._clock.now() >= limite:
                return False
            self._sleep(POLL_SECONDS)

    def _signal(self, pid: int, sig: int) -> None:
        try:
            self._runner.signal_group(pid, sig)
        except ProcessLookupError:
            pass
