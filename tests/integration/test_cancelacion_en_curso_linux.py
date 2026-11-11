import os
import shutil
import subprocess
import threading
import time
from datetime import datetime, timezone

import pytest

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.name != "posix", reason="requiere procesos POSIX; en Windows usar Docker o WSL2"),
]


class _RelojReal:
    def now(self):
        return datetime.now(timezone.utc)


def _supervisor():
    from src.adapters.posix_process_runner import PosixProcessRunner
    from src.application.process_supervisor import ProcessSupervisor

    return ProcessSupervisor(runner=PosixProcessRunner(), clock=_RelojReal(), sleep=time.sleep, grace_seconds=2.0)


def _tabla():
    pares = []
    for nombre in os.listdir("/proc"):
        if not nombre.isdigit():
            continue
        try:
            with open(f"/proc/{nombre}/stat") as archivo:
                campos = archivo.read().rsplit(")", 1)[1].split()
        except OSError:
            continue
        pares.append((int(nombre), int(campos[1])))
    return pares


def _descendientes(raiz):
    pares = _tabla()
    encontrados, frontera = set(), {raiz}
    while frontera:
        hijos = {p for p, padre in pares if padre in frontera} - encontrados
        encontrados |= hijos
        frontera = hijos
    return sorted(encontrados)


def _vivos(pids):
    existentes = {p for p, _ in _tabla()}
    return [p for p in pids if p in existentes]


def _cmd(pid):
    try:
        with open(f"/proc/{pid}/cmdline", "rb") as archivo:
            return archivo.read().replace(b"\0", b" ").decode(errors="replace")
    except OSError:
        return ""


def test_cancelar_a_mitad_deja_sin_procesos_ni_scratch(tmp_path):
    sup = _supervisor()
    scratch = tmp_path / "caso-1"
    pid = sup.start(["sh", "-c", "sleep 300 & sleep 300 & wait"], scratch=scratch)
    time.sleep(0.3)
    arbol = [pid, *_descendientes(pid)]
    assert len(arbol) >= 3
    sup.cancel(pid)
    assert _vivos(arbol) == []
    assert not scratch.exists()


def test_subtarea_que_ignora_sigterm_muere_tras_la_gracia(tmp_path):
    sup = _supervisor()
    pid = sup.start(["sh", "-c", "trap '' TERM; sleep 300 & wait"], scratch=tmp_path / "caso-2")
    time.sleep(0.3)
    arbol = [pid, *_descendientes(pid)]
    sup.cancel(pid)
    assert _vivos(arbol) == []


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="requiere ffmpeg en el PATH")
def test_process_real_con_ffmpeg_se_cancela_y_no_deja_hijos(tmp_path):
    from src.workers import multimedia_processor as mp

    entrada = tmp_path / "in.mp4"
    subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=size=1280x720:rate=30",
         "-t", "60", "-pix_fmt", "yuv420p", str(entrada)],
        check=True,
    )
    sup = _supervisor()

    def correr():
        try:
            mp.process("transcode", str(entrada), str(tmp_path / "out"),
                       params={"width": 1920, "preset": "veryslow"}, supervisor=sup)
        except Exception:
            pass

    hilo = threading.Thread(target=correr)
    hilo.start()
    time.sleep(1.0)
    pids = [p for p in _descendientes(os.getpid()) if "ffmpeg" in _cmd(p)]
    assert pids, "FFmpeg debe correr bajo el supervisor"
    for pid in pids:
        sup.cancel(pid)
    hilo.join(timeout=30)
    assert not hilo.is_alive()
    assert _vivos(pids) == []
