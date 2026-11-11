import os
import subprocess
from collections.abc import Sequence


class PosixProcessRunner:
    def __init__(self):
        self._procesos: dict[int, subprocess.Popen] = {}

    def start(self, argv: Sequence[str]) -> int:
        proceso = subprocess.Popen(list(argv), start_new_session=True)
        self._procesos[proceso.pid] = proceso
        return proceso.pid

    def signal_group(self, pid: int, sig: int) -> None:
        os.killpg(pid, sig)

    def reap(self, pid: int, block: bool = False) -> bool:
        proceso = self._procesos[pid]
        if block:
            proceso.wait()
            return True
        return proceso.poll() is not None
