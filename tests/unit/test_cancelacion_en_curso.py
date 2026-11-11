import inspect
import re
import sys
from datetime import timedelta
from importlib import import_module
from pathlib import Path

import pytest

from src.workers import multimedia_processor as mp
from tests.dobles import FakeClock
from tests.unit.test_process_supervisor import RunnerFalso, supervisor_de

COMPOSE_WORKER = Path(__file__).parents[2] / "deploy" / "docker-compose.worker.yml"


@pytest.fixture
def reloj():
    return FakeClock()


@pytest.fixture
def dormir(reloj):
    return lambda segundos: reloj.advance(timedelta(seconds=segundos))


def test_cancel_dos_veces_no_lanza(reloj, dormir, tmp_path):
    sup = supervisor_de(RunnerFalso(), reloj, dormir)
    pid = sup.start(["sleep", "60"], scratch=tmp_path / "t1")
    sup.cancel(pid)

    sup.cancel(pid)


def test_cancel_pid_desconocido_no_lanza(reloj, dormir):
    sup = supervisor_de(RunnerFalso(), reloj, dormir)

    sup.cancel(999_999)


class SupervisorFalso:
    def __init__(self, polls_vivo=2, codigo=0, progreso=()):
        self.inicios = []
        self.polls_vivo = polls_vivo
        self.codigo = codigo
        self.progreso = list(progreso)
        self._scratch = None
        self._argv = None

    def start(self, argv, scratch):
        self.inicios.append((list(argv), scratch))
        self._argv, self._scratch = list(argv), scratch
        return 7001

    def poll(self, pid):
        if self.polls_vivo > 0:
            self.polls_vivo -= 1
            if self.polls_vivo == 0 and self.progreso:
                archivo = Path(self._argv[self._argv.index("-progress") + 1])
                archivo.parent.mkdir(parents=True, exist_ok=True)
                archivo.write_text("\n".join(self.progreso) + "\n")
            return None
        return self.codigo

    def cancel(self, pid):
        self.codigo = -15
        self.polls_vivo = 0


@pytest.fixture
def sin_espera(monkeypatch):
    monkeypatch.setattr(mp.time, "sleep", lambda _s: None)


@pytest.fixture
def popen_prohibido(monkeypatch):
    def _no(*_a, **_k):
        raise AssertionError("con supervisor no se debe usar subprocess.Popen")

    monkeypatch.setattr(mp.subprocess, "Popen", _no)


def test_process_y_run_aceptan_supervisor():
    assert "supervisor" in inspect.signature(mp.process).parameters
    assert "supervisor" in inspect.signature(mp._run).parameters


def test_run_usa_supervisor_si_se_provee(tmp_path, sin_espera, popen_prohibido):
    sup = SupervisorFalso()

    mp._run(["ffmpeg", "-i", "in.mp4", "out.mp4"], 60, "t", supervisor=sup)

    assert len(sup.inicios) == 1
    argv, scratch = sup.inicios[0]
    assert argv[0] == "ffmpeg"
    assert isinstance(scratch, Path)
    assert "pipe:1" not in argv
    assert argv[argv.index("-progress") + 1].startswith(str(scratch))


def test_run_con_supervisor_reporta_progreso_desde_archivo(sin_espera, popen_prohibido):
    avances = []
    tracker = mp._ProgressTracker(avances.append, 10.0, interval=0)
    sup = SupervisorFalso(progreso=["out_time_us=5000000", "progress=end"])

    mp._run(["ffmpeg", "-i", "in.mp4", "out.mp4"], 60, "t", tracker=tracker, supervisor=sup)

    assert avances and avances[-1] == pytest.approx(50.0)


def test_run_con_supervisor_y_codigo_distinto_de_cero_lanza_error(sin_espera, popen_prohibido):
    sup = SupervisorFalso(codigo=1)

    with pytest.raises(mp.ProcessingError):
        mp._run(["ffmpeg", "-i", "in.mp4", "out.mp4"], 60, "t", supervisor=sup)


def test_run_sin_supervisor_igual_que_antes(monkeypatch):
    class Hijo:
        def __init__(self, cmd, **_k):
            self.cmd = cmd
            self.stdout = __import__("io").BytesIO(b"progress=end\n")

        def wait(self):
            return 0

        def kill(self):
            pass

    usados = []
    monkeypatch.setattr(mp.subprocess, "Popen", lambda cmd, **k: usados.append(cmd) or Hijo(cmd, **k))

    mp._run(["ffmpeg", "-i", "in.mp4", "out.mp4"], 60, "t")

    assert usados and usados[0][1:3] == ["-progress", "pipe:1"]


def test_main_construye_supervisor_en_posix(monkeypatch):
    worker_node = import_module("src.workers.worker_node")
    recibido = {}

    class WorkerFalso:
        def __init__(self, *args, **kwargs):
            recibido.update(kwargs)

        def run_forever(self):
            pass

    class AjustesFalsos:
        worker_queues = ()
        worker_id = "w1"

        @classmethod
        def from_env(cls):
            return cls()

    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(worker_node, "Worker", WorkerFalso)
    monkeypatch.setattr(worker_node, "Settings", AjustesFalsos)
    monkeypatch.setattr(worker_node, "load_admission_config", lambda *_a: (None, 0))
    monkeypatch.setattr(worker_node, "CgroupResourceReader", lambda **_k: object())

    worker_node.main()

    from src.application.process_supervisor import ProcessSupervisor

    assert isinstance(recibido.get("supervisor"), ProcessSupervisor)


def test_gracia_menor_que_stop_grace_period():
    modulo = import_module("src.application.process_supervisor")
    texto = COMPOSE_WORKER.read_text()
    minutos = int(re.search(r"stop_grace_period:\s*(\d+)m", texto).group(1))

    assert modulo.GRACE_SECONDS < minutos * 60
