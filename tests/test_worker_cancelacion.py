import threading
import time

import fakeredis

from fakes import FakeStorage

from src.workers.worker_node import Worker
from test_worker_node import make_settings, seed_subtask


class SupervisorFalso:
    def __init__(self):
        self.cancelados = []
        self.arrancados = {}

    def start(self, argv, scratch):
        scratch.mkdir(parents=True, exist_ok=True)
        pid = 1000 + len(self.arrancados)
        self.arrancados[pid] = scratch
        return pid

    def cancel(self, pid):
        self.cancelados.append(pid)


class ProcesadorBloqueado:
    """Arranca un subproceso vía supervisor y espera hasta que lo cancelen."""

    def __init__(self, supervisor, cancelado):
        self.supervisor = supervisor
        self.cancelado = cancelado
        self.en_ejecucion = threading.Event()

    def process(self, operation, src, out_dir, supervisor=None, **kwargs):
        pid = supervisor.start(["sleep", "60"], scratch=self.supervisor_scratch(out_dir))
        self.en_ejecucion.set()
        self.cancelado.wait(5)
        raise RuntimeError(f"cancelado {pid}")

    @staticmethod
    def supervisor_scratch(out_dir):
        from pathlib import Path

        return Path(out_dir).parent / "proc"


def esperar(condicion, segundos=3):
    limite = time.monotonic() + segundos
    while time.monotonic() < limite:
        if condicion():
            return True
        time.sleep(0.02)
    return False


def test_aviso_de_cancelacion_detiene_el_subproceso_de_la_subtarea(tmp_path):
    redis_client = fakeredis.FakeRedis(decode_responses=True)
    storage = FakeStorage()
    supervisor = SupervisorFalso()
    cancelado = threading.Event()
    procesador = ProcesadorBloqueado(supervisor, cancelado)
    seed_subtask(redis_client, storage, "s1", case_id="c1")
    worker = Worker(
        make_settings(tmp_path), redis_client=redis_client, storage=storage,
        processor=procesador, heartbeat_enabled=False, supervisor=supervisor,
    )
    worker.start()
    try:
        assert procesador.en_ejecucion.wait(3)

        redis_client.publish("cancel:c1", "c1")

        assert esperar(lambda: supervisor.cancelados == [1000])
    finally:
        cancelado.set()
        worker.stop(timeout=2)


def test_aviso_de_otro_caso_no_toca_el_subproceso(tmp_path):
    redis_client = fakeredis.FakeRedis(decode_responses=True)
    storage = FakeStorage()
    supervisor = SupervisorFalso()
    cancelado = threading.Event()
    procesador = ProcesadorBloqueado(supervisor, cancelado)
    seed_subtask(redis_client, storage, "s1", case_id="c1")
    worker = Worker(
        make_settings(tmp_path), redis_client=redis_client, storage=storage,
        processor=procesador, heartbeat_enabled=False, supervisor=supervisor,
    )
    worker.start()
    try:
        assert procesador.en_ejecucion.wait(3)

        redis_client.publish("cancel:otro", "otro")
        time.sleep(0.2)

        assert supervisor.cancelados == []
    finally:
        cancelado.set()
        worker.stop(timeout=2)


def test_al_arrancar_se_borran_los_temporales_huerfanos(tmp_path):
    huerfano = tmp_path / "s-viejo"
    (huerfano / "in").mkdir(parents=True)
    (huerfano / "in" / "parcial.bin").write_bytes(b"x")
    worker = Worker(
        make_settings(tmp_path), redis_client=fakeredis.FakeRedis(decode_responses=True),
        storage=FakeStorage(), processor=object(), heartbeat_enabled=False,
        supervisor=SupervisorFalso(),
    )

    worker.start()
    worker.stop(timeout=2)

    assert not huerfano.exists()
    assert tmp_path.exists()


def test_el_temporal_de_la_subtarea_se_borra_aunque_se_cancele(tmp_path):
    redis_client = fakeredis.FakeRedis(decode_responses=True)
    storage = FakeStorage()
    supervisor = SupervisorFalso()
    cancelado = threading.Event()
    cancelado.set()
    seed_subtask(redis_client, storage, "s1", case_id="c1")
    worker = Worker(
        make_settings(tmp_path), redis_client=redis_client, storage=storage,
        processor=ProcesadorBloqueado(supervisor, cancelado), heartbeat_enabled=False,
        supervisor=supervisor,
    )

    worker.handle_subtask("s1")

    assert not (tmp_path / "s1").exists()
