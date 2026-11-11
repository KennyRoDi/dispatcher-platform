import pytest

from tests.unit.test_model_loader import ENTRADA, FabricaSimulada, ProcesosSimulados, cargador


class ProcesosConFalloDeLimpieza(ProcesosSimulados):
    def __init__(self, *, falla_terminate=False, falla_join=False):
        super().__init__()
        self.falla_terminate = falla_terminate
        self.falla_join = falla_join

    def terminate(self, hijo):
        super().terminate(hijo)
        if self.falla_terminate and hijo.numero == 0:
            raise OSError("falló terminate")

    def join(self, hijo):
        super().join(hijo)
        if self.falla_join and hijo.numero == 0:
            raise OSError("falló join")


@pytest.mark.parametrize("estrategia", ["por_proceso", "workers_compartidos"])
@pytest.mark.parametrize("operacion", ["terminate", "join"])
def test_error_de_limpieza_no_oculta_error_primario_ni_abandona_otros_hijos(estrategia, operacion):
    procesos = ProcesosConFalloDeLimpieza(
        falla_terminate=operacion == "terminate", falla_join=operacion == "join"
    )
    error = RuntimeError("falló la inferencia")
    fabrica = FabricaSimulada(procesos, error_al_inferir=error)

    with pytest.raises(RuntimeError) as capturado:
        cargador(estrategia, procesos, fabrica).run(ENTRADA)

    assert capturado.value is error
    assert any(f"falló {operacion}" in nota for nota in error.__notes__)
    count = 1 if estrategia == "workers_compartidos" else 2
    assert [("recolectar", i) for i in range(count)] == [
        e for e in procesos.eventos if e[0] == "recolectar"
    ]
    assert ("terminar", count - 1) in procesos.eventos


@pytest.mark.parametrize("estrategia", ["por_proceso", "workers_compartidos"])
def test_error_de_join_tras_exito_se_informa_y_recolecta_los_demas(estrategia):
    procesos = ProcesosConFalloDeLimpieza(falla_join=True)

    with pytest.raises(OSError, match="falló join"):
        cargador(estrategia, procesos, FabricaSimulada(procesos)).run(ENTRADA)

    count = 1 if estrategia == "workers_compartidos" else 2
    assert [("recolectar", i) for i in range(count)] == [
        e for e in procesos.eventos if e[0] == "recolectar"
    ]
