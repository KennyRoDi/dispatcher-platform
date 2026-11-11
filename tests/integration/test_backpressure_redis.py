import os
import shutil
import socket
import subprocess
import threading
import time

import pytest
import redis
from fastapi.testclient import TestClient

import src.coordinator.main as main
from src.coordinator import conexion
from src.coordinator.seguridad import autorizar

pytestmark = pytest.mark.integration

LIMITE = 50
PRODUCTORES = 20
CASOS_POR_PRODUCTOR = 10
COLA = "queue:transcode_video"


def _puerto_libre():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture(scope="module")
def servidor_redis():
    """Redis de `REDIS_URL` o, si no hay, un `redis-server` efímero sin persistencia."""
    url = os.environ.get("REDIS_URL")
    proceso = None
    if not url:
        if shutil.which("redis-server") is None:
            pytest.skip("sin REDIS_URL ni redis-server")
        puerto = _puerto_libre()
        proceso = subprocess.Popen(["redis-server", "--port", str(puerto), "--save", "", "--appendonly", "no"],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        url = f"redis://127.0.0.1:{puerto}/0"
    try:
        cliente = redis.Redis.from_url(url, decode_responses=True)
        for _ in range(50):
            try:
                cliente.ping()
                break
            except redis.ConnectionError:
                time.sleep(0.1)
        else:
            pytest.skip(f"Redis no responde en {url}")
        yield cliente
    finally:
        if proceso:
            proceso.terminate()
            proceso.wait(timeout=10)


@pytest.fixture
def r(servidor_redis, monkeypatch):
    servidor_redis.flushdb()
    monkeypatch.setattr(conexion, "redis_client", servidor_redis)
    monkeypatch.setenv("QUEUE_MAX_DEPTH", str(LIMITE))
    monkeypatch.setenv("QUEUE_RETRY_AFTER", "1")
    main.app.dependency_overrides[autorizar] = lambda: None
    yield servidor_redis
    main.app.dependency_overrides.pop(autorizar, None)
    servidor_redis.flushdb()


def test_productores_concurrentes_nunca_superan_el_limite(r):
    muestras, codigos = [], []
    terminado = threading.Event()
    barrera = threading.Barrier(PRODUCTORES)

    def muestrear():
        while not terminado.is_set():
            muestras.append(r.llen(COLA))

    def producir():
        cliente = TestClient(main.app)
        barrera.wait()
        for _ in range(CASOS_POR_PRODUCTOR):
            respuesta = cliente.post("/cases", json={"subtasks": [{"task_type": "auto", "file_path": "videos/a.mp4"}]})
            codigos.append((respuesta.status_code, respuesta.headers.get("Retry-After")))

    muestreador = threading.Thread(target=muestrear)
    muestreador.start()
    hilos = [threading.Thread(target=producir) for _ in range(PRODUCTORES)]
    for hilo in hilos:
        hilo.start()
    for hilo in hilos:
        hilo.join()
    terminado.set()
    muestreador.join()

    admitidos = [c for c, _ in codigos if c == 201]
    rechazados = [(c, ra) for c, ra in codigos if c != 201]
    assert len(admitidos) == LIMITE
    assert set(rechazados) == {(503, "1")}
    assert max(muestras) <= LIMITE
    assert r.llen(COLA) == LIMITE
    assert r.scard("cases:registry") == LIMITE
