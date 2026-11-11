from dataclasses import dataclass
from importlib import import_module
from pathlib import Path

import pytest

from src.domain.transcription import TranscriptSegment


ENTRADA = Path("nota-sintetica.ogg")
SEGMENTOS = [TranscriptSegment(0.25, 1.75, "texto sintético", 0.875)]


@dataclass
class ProcesoSimulado:
    numero: int
    target: object
    args: tuple
    terminado: bool = False


class ProcesosSimulados:
    def __init__(self, error_al_iniciar=None):
        self.contexto = "supervisor"
        self.eventos = []
        self.hijos = []
        self.error_al_iniciar = error_al_iniciar

    def start(self, target, args, *, method):
        numero = len(self.hijos)
        self.eventos.append(("iniciar", numero, method))
        if numero == self.error_al_iniciar:
            raise OSError("no se pudo iniciar el hijo")
        hijo = ProcesoSimulado(numero, target, args)
        self.hijos.append(hijo)
        return hijo

    def result(self, hijo):
        self.eventos.append(("resultado", hijo.numero))
        self.contexto = f"hijo-{hijo.numero}"
        try:
            return hijo.target(*hijo.args)
        finally:
            hijo.terminado = True
            self.contexto = "supervisor"

    def terminate(self, hijo):
        self.eventos.append(("terminar", hijo.numero))
        hijo.terminado = True

    def join(self, hijo):
        self.eventos.append(("recolectar", hijo.numero))


class TranscriptorSimulado:
    def __init__(self, procesos, identidad, error=None):
        self.procesos = procesos
        self.identidad = identidad
        self.error = error

    def transcribe(self, ruta):
        self.procesos.eventos.append(
            ("transcribir", self.procesos.contexto, self.identidad, ruta)
        )
        if self.error is not None:
            raise self.error
        return list(SEGMENTOS)


class FabricaSimulada:
    def __init__(self, procesos, error_al_cargar=None, error_al_inferir=None):
        self.procesos = procesos
        self.modelos = []
        self.error_al_cargar = error_al_cargar
        self.error_al_inferir = error_al_inferir

    def __call__(self):
        identidad = len(self.modelos)
        self.procesos.eventos.append(("cargar", self.procesos.contexto, identidad))
        if self.error_al_cargar is not None:
            raise self.error_al_cargar
        modelo = TranscriptorSimulado(self.procesos, identidad, self.error_al_inferir)
        self.modelos.append(modelo)
        return modelo


def cargador(estrategia, procesos, fabrica, cantidad=2):
    config = import_module("src.domain.model_loading").LoadingConfig(
        strategy=estrategia, processes=cantidad
    )
    return import_module("src.infrastructure.model_loader").ModelLoader(
        config=config, factory=fabrica, runtime=procesos
    )


@pytest.mark.parametrize("cantidad", [1, 2])
def test_por_proceso_carga_una_instancia_en_cada_hijo(cantidad):
    procesos = ProcesosSimulados()
    fabrica = FabricaSimulada(procesos)

    resultados = cargador("por_proceso", procesos, fabrica, cantidad).run(ENTRADA)

    assert resultados == [SEGMENTOS] * cantidad
    assert [e for e in procesos.eventos if e[0] == "cargar"] == [
        ("cargar", f"hijo-{i}", i) for i in range(cantidad)
    ]
    assert [e for e in procesos.eventos if e[0] == "transcribir"] == [
        ("transcribir", f"hijo-{i}", i, ENTRADA) for i in range(cantidad)
    ]


@pytest.mark.parametrize("cantidad", [1, 2])
def test_fork_compartido_precarga_una_vez_y_los_hijos_usan_la_misma_instancia(cantidad):
    procesos = ProcesosSimulados()
    fabrica = FabricaSimulada(procesos)

    resultados = cargador("fork_compartido", procesos, fabrica, cantidad).run(ENTRADA)

    assert resultados == [SEGMENTOS] * cantidad
    assert procesos.eventos[0] == ("cargar", "supervisor", 0)
    assert [e for e in procesos.eventos if e[0] == "cargar"] == [
        ("cargar", "supervisor", 0)
    ]
    assert [e for e in procesos.eventos if e[0] == "transcribir"] == [
        ("transcribir", f"hijo-{i}", 0, ENTRADA) for i in range(cantidad)
    ]


@pytest.mark.parametrize("estrategia", ["por_proceso", "fork_compartido"])
def test_inicia_todos_los_hijos_con_fork_explicito_y_recolecta_cada_uno(estrategia):
    procesos = ProcesosSimulados()
    fabrica = FabricaSimulada(procesos)

    cargador(estrategia, procesos, fabrica).run(ENTRADA)

    eventos = procesos.eventos
    assert [e for e in eventos if e[0] == "iniciar"] == [
        ("iniciar", 0, "fork"), ("iniciar", 1, "fork")
    ]
    assert eventos.index(("iniciar", 1, "fork")) < eventos.index(("resultado", 0))
    assert [e for e in eventos if e[0] == "recolectar"] == [
        ("recolectar", 0), ("recolectar", 1)
    ]
    assert not [e for e in eventos if e[0] == "terminar"]


@pytest.mark.parametrize("estrategia", ["por_proceso", "fork_compartido"])
def test_error_de_inferencia_se_propaga_y_no_deja_hijos_sin_recolectar(estrategia):
    procesos = ProcesosSimulados()
    error = RuntimeError("falló la inferencia")
    fabrica = FabricaSimulada(procesos, error_al_inferir=error)

    with pytest.raises(RuntimeError) as capturado:
        cargador(estrategia, procesos, fabrica).run(ENTRADA)

    assert capturado.value is error
    assert ("terminar", 1) in procesos.eventos
    assert [e for e in procesos.eventos if e[0] == "recolectar"] == [
        ("recolectar", 0), ("recolectar", 1)
    ]


def test_fallo_de_precarga_se_propaga_sin_iniciar_hijos():
    procesos = ProcesosSimulados()
    error = MemoryError("no cabe el modelo")
    fabrica = FabricaSimulada(procesos, error_al_cargar=error)

    with pytest.raises(MemoryError) as capturado:
        cargador("fork_compartido", procesos, fabrica).run(ENTRADA)

    assert capturado.value is error
    assert procesos.hijos == []
    assert procesos.eventos == [("cargar", "supervisor", 0)]


def test_fallo_de_carga_en_hijo_se_propaga_y_recolecta_todos():
    procesos = ProcesosSimulados()
    error = MemoryError("no cabe el modelo")
    fabrica = FabricaSimulada(procesos, error_al_cargar=error)

    with pytest.raises(MemoryError) as capturado:
        cargador("por_proceso", procesos, fabrica).run(ENTRADA)

    assert capturado.value is error
    assert ("terminar", 1) in procesos.eventos
    assert [e for e in procesos.eventos if e[0] == "recolectar"] == [
        ("recolectar", 0), ("recolectar", 1)
    ]


@pytest.mark.parametrize("estrategia", ["por_proceso", "fork_compartido"])
def test_inicio_parcial_fallido_termina_y_recolecta_hijos_ya_iniciados(estrategia):
    procesos = ProcesosSimulados(error_al_iniciar=1)
    fabrica = FabricaSimulada(procesos)

    with pytest.raises(OSError, match="no se pudo iniciar el hijo"):
        cargador(estrategia, procesos, fabrica).run(ENTRADA)

    assert ("terminar", 0) in procesos.eventos
    assert [e for e in procesos.eventos if e[0] == "recolectar"] == [("recolectar", 0)]
    assert not [e for e in procesos.eventos if e[0] == "transcribir"]
