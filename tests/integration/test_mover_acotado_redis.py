import threading

import pytest

from src.adapters.redis_backpressure import mover_acotado
from src.domain.backpressure import QueueLimit
from tests.integration.test_backpressure_redis import servidor_redis  # noqa: F401

pytestmark = pytest.mark.integration

COLA = "queue:transcode_video"


def test_movedores_concurrentes_nunca_superan_el_limite(servidor_redis):  # noqa: F811
    r = servidor_redis
    r.flushdb()
    limite = QueueLimit(40, 5)
    resultados, muestras = [], []
    terminado = threading.Event()
    barrera = threading.Barrier(16)

    def muestrear():
        while not terminado.is_set():
            muestras.append(r.llen(COLA))

    def mover(hilo):
        barrera.wait()
        for i in range(20):
            resultados.append(mover_acotado(r, COLA, f"{hilo}-{i}", limite))

    muestreador = threading.Thread(target=muestrear)
    muestreador.start()
    hilos = [threading.Thread(target=mover, args=(h,)) for h in range(16)]
    for hilo in hilos:
        hilo.start()
    for hilo in hilos:
        hilo.join()
    terminado.set()
    muestreador.join()
    r.flushdb()

    assert resultados.count(True) == 40
    assert max(muestras) <= 40
