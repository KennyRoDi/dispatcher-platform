import os
import signal
import sys
from datetime import timedelta
from importlib import import_module

import pytest

from tests.dobles import FakeClock

SIGKILL = getattr(signal, "SIGKILL", 9)
posix = pytest.mark.skipif(sys.platform == "win32", reason="requiere señales POSIX; en Windows usar WSL2")


def supervisor_de(runner, clock, sleep, gracia=10.0):
    modulo = import_module("src.application.process_supervisor")
    return modulo.ProcessSupervisor(runner=runner, clock=clock, sleep=sleep, grace_seconds=gracia)


class RunnerFalso:
    def __init__(self, ignora_sigterm=False, ya_termino=False):
        self.eventos = []
        self.ignora_sigterm = ignora_sigterm
        self.ya_termino = ya_termino
        self._vivo = True

    def start(self, argv):
        self.eventos.append(("start", tuple(argv)))
        return 4242

    def signal_group(self, pid, sig):
        self.eventos.append(("signal", pid, sig))
        if self.ya_termino:
            raise ProcessLookupError
        if sig == SIGKILL or not self.ignora_sigterm:
            self._vivo = False

    def reap(self, pid, block=False):
        if block or not self._vivo:
            self.eventos.append(("reap", pid, block))
            self._vivo = False
            return True
        return False


@pytest.fixture
def reloj():
    return FakeClock()


@pytest.fixture
def dormir(reloj):
    return lambda segundos: reloj.advance(timedelta(seconds=segundos))


def senales(runner):
    return [e[2] for e in runner.eventos if e[0] == "signal"]


def test_hijo_que_obedece_recibe_solo_sigterm_y_se_recolecta(reloj, dormir, tmp_path):
    runner = RunnerFalso()
    sup = supervisor_de(runner, reloj, dormir)
    pid = sup.start(["sleep", "60"], scratch=tmp_path / "t1")

    sup.cancel(pid)

    assert senales(runner) == [signal.SIGTERM]
    assert ("reap", pid, False) in runner.eventos


def test_hijo_que_ignora_sigterm_recibe_sigkill_tras_la_gracia(reloj, dormir, tmp_path):
    runner = RunnerFalso(ignora_sigterm=True)
    sup = supervisor_de(runner, reloj, dormir, gracia=5.0)
    inicio = reloj.now()
    pid = sup.start(["sleep", "60"], scratch=tmp_path / "t1")

    sup.cancel(pid)

    assert senales(runner) == [signal.SIGTERM, SIGKILL]
    assert reloj.now() - inicio >= timedelta(seconds=5)
    assert runner.eventos[-1] == ("reap", pid, True)


def test_sigkill_no_se_envia_antes_de_agotar_la_gracia(reloj, tmp_path):
    runner = RunnerFalso(ignora_sigterm=True)
    pasos = []

    def dormir(segundos):
        pasos.append(senales(runner)[:])
        reloj.advance(timedelta(seconds=segundos))

    sup = supervisor_de(runner, reloj, dormir, gracia=5.0)
    sup.cancel(sup.start(["sleep", "60"], scratch=tmp_path / "t1"))

    assert pasos and all(p == [signal.SIGTERM] for p in pasos)


def test_hijo_que_ya_termino_no_falla_al_cancelar(reloj, dormir, tmp_path):
    runner = RunnerFalso(ya_termino=True)
    sup = supervisor_de(runner, reloj, dormir)

    sup.cancel(sup.start(["sleep", "60"], scratch=tmp_path / "t1"))

    assert ("reap", 4242, True) in runner.eventos


def test_cancelar_borra_el_temporal_aunque_falle_la_senal(reloj, dormir, tmp_path):
    scratch = tmp_path / "t1"
    runner = RunnerFalso()
    runner.signal_group = lambda pid, sig: (_ for _ in ()).throw(PermissionError())
    sup = supervisor_de(runner, reloj, dormir)
    pid = sup.start(["sleep", "60"], scratch=scratch)
    (scratch / "parcial.bin").write_bytes(b"x")

    with pytest.raises(PermissionError):
        sup.cancel(pid)

    assert not scratch.exists()


def test_start_crea_el_directorio_de_trabajo(reloj, dormir, tmp_path):
    scratch = tmp_path / "t1"

    supervisor_de(RunnerFalso(), reloj, dormir).start(["sleep", "60"], scratch=scratch)

    assert scratch.is_dir()


def proceso_existe(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


def real(gracia):
    import time
    from datetime import datetime, timezone

    class Reloj:
        def now(self):
            return datetime.now(timezone.utc)

    adaptador = import_module("src.adapters.posix_process_runner").PosixProcessRunner()
    return supervisor_de(adaptador, Reloj(), time.sleep, gracia=gracia)


@posix
def test_cancelar_envia_sigterm_y_luego_sigkill(tmp_path):
    sup = real(gracia=0.3)
    pid = sup.start(["sh", "-c", "trap '' TERM; sleep 60"], scratch=tmp_path / "t1")

    sup.cancel(pid)

    assert not proceso_existe(pid)


@posix
def test_temporal_se_borra_tras_sigkill(tmp_path):
    scratch = tmp_path / "t1"
    sup = real(gracia=0.3)
    pid = sup.start(["sh", "-c", "trap '' TERM; sleep 60"], scratch=scratch)
    (scratch / "parcial.bin").write_bytes(b"x")

    sup.cancel(pid)

    assert not scratch.exists()


@posix
def test_no_quedan_zombies(tmp_path):
    sup = real(gracia=0.3)
    pid = sup.start(["sh", "-c", "sleep 60 & sleep 60"], scratch=tmp_path / "t1")

    sup.cancel(pid)

    with pytest.raises(ChildProcessError):
        os.waitpid(pid, os.WNOHANG)


@posix
def test_cancelar_mata_tambien_a_los_nietos_del_grupo(tmp_path):
    marca = tmp_path / "nieto.pid"
    sup = real(gracia=0.3)
    pid = sup.start(["sh", "-c", f"sleep 60 & echo $! > {marca}; wait"], scratch=tmp_path / "t1")
    import time

    for _ in range(50):
        if marca.exists() and marca.read_text().strip():
            break
        time.sleep(0.05)
    nieto = int(marca.read_text())

    sup.cancel(pid)

    time.sleep(0.1)
    assert not proceso_existe(nieto)
