import logging

import pytest

from src.application.dispatch_case import DispatchCase
from src.domain.decomposition import CaseSource, SourceKind
from src.domain.priority import Priority
from src.domain.subtask import QueueFull
from tests.dobles import FakeClock, FakeWorkQueue

TEXTO = CaseSource("a" * 64, "chat.txt", SourceKind.TEXT)
IMAGEN = CaseSource("b" * 64, "foto.png", SourceKind.IMAGE)
AUDIO = CaseSource("c" * 64, "nota.mp3", SourceKind.AUDIO)
VIDEO = CaseSource("d" * 64, "clip.mp4", SourceKind.VIDEO)
COLAS = ("queue:text", "queue:image", "queue:audio")


def _lineas_de_routing(caplog):
    return [r.getMessage() for r in caplog.records if r.getMessage().startswith("routing ")]


@pytest.mark.parametrize("llena", COLAS)
def test_cola_llena_en_cualquier_posicion_no_encola_nada(llena):
    cola = FakeWorkQueue(capacidad=1)
    cola.colas[llena].append("ocupada")

    with pytest.raises(QueueFull) as error:
        DispatchCase(cola, FakeClock()).execute("C-1", [TEXTO, IMAGEN, AUDIO], Priority.MEDIA)

    assert str(error.value) == llena
    assert {n: len(cola.colas[n]) for n in COLAS} == {n: int(n == llena) for n in COLAS}


def test_cola_llena_no_deja_lineas_de_routing(caplog):
    cola = FakeWorkQueue(capacidad=1)
    cola.colas["queue:text"].append("ocupada")

    with caplog.at_level(logging.INFO), pytest.raises(QueueFull):
        DispatchCase(cola, FakeClock()).execute("C-1", [TEXTO, IMAGEN], Priority.MEDIA)

    assert _lineas_de_routing(caplog) == []


def test_dispatch_acepta_tupla_y_generador_de_fuentes():
    cola = FakeWorkQueue()
    caso = DispatchCase(cola, FakeClock())

    assert len(caso.execute("C-1", (TEXTO, VIDEO), Priority.ALTA)) == 3
    assert len(caso.execute("C-2", (f for f in [TEXTO, VIDEO]), Priority.ALTA)) == 3


def test_dispatch_de_caso_sin_fuentes_no_encola_ni_registra(caplog):
    cola = FakeWorkQueue()

    with caplog.at_level(logging.INFO):
        assert DispatchCase(cola, FakeClock()).execute("C-1", [], Priority.ALTA) == []

    assert not any(cola.colas.values())
    assert _lineas_de_routing(caplog) == []


def test_dispatch_con_fuente_repetida_encola_una_sola_vez():
    cola = FakeWorkQueue()

    DispatchCase(cola, FakeClock()).execute("C-1", [TEXTO, TEXTO], Priority.ALTA)

    assert len(cola.colas["queue:text"]) == 1


class ColaQueFallaAlEncolar(FakeWorkQueue):
    def __init__(self, falla_en):
        super().__init__()
        self.falla_en = falla_en
        self.llamadas = 0

    def enqueue(self, queue, subtask):
        self.llamadas += 1
        if self.llamadas == self.falla_en:
            raise ConnectionError("cola caida")
        super().enqueue(queue, subtask)


def test_si_enqueue_falla_a_mitad_solo_se_registra_lo_encolado(caplog):
    cola = ColaQueFallaAlEncolar(falla_en=3)

    with caplog.at_level(logging.INFO), pytest.raises(ConnectionError):
        DispatchCase(cola, FakeClock()).execute("C-1", [TEXTO, IMAGEN, AUDIO], Priority.ALTA)

    assert sum(len(cola.colas[n]) for n in COLAS) == 2
    assert len(_lineas_de_routing(caplog)) == 2


@pytest.mark.xfail(
    strict=True,
    reason=(
        "HALLAZGO QA-1 (media): DispatchCase usa has_capacity booleano por cola y no cuenta cuantas "
        "plazas necesita el caso en cada una. Una cola con una plaza libre y un caso que le manda dos "
        "sub-tareas (audio y video van a queue:audio) encola una y luego lanza QueueFull con el caso "
        "a medias. Reproducir: FakeWorkQueue(capacidad=1); DispatchCase(cola, FakeClock())"
        ".execute('C', [AUDIO, VIDEO], Priority.ALTA) deja 1 elemento en queue:audio y 1 en queue:image. "
        "El SPEC solo declara la no atomicidad entre procesos, no esta."
    ),
)
def test_caso_que_necesita_mas_plazas_que_las_libres_no_encola_nada():
    cola = FakeWorkQueue(capacidad=1)

    with pytest.raises(QueueFull):
        DispatchCase(cola, FakeClock()).execute("C-1", [AUDIO, VIDEO], Priority.ALTA)

    assert {n: len(cola.colas[n]) for n in COLAS} == {n: 0 for n in COLAS}


@pytest.mark.xfail(
    strict=True,
    reason=(
        "HALLAZGO QA-2 (baja): el case_id va sin sanear en el log de routing, asi que un salto de linea "
        "permite inyectar una linea falsa que empieza por 'routing case='. Reproducir: con caplog, "
        "DispatchCase(FakeWorkQueue(), FakeClock()).execute('C-1\\nrouting case=EVIL', [AUDIO], "
        "Priority.ALTA) -> el mensaje del log contiene un salto de linea."
    ),
)
def test_case_id_con_salto_de_linea_no_inyecta_lineas_en_el_log(caplog):
    hostil = "C-1\nrouting case=EVIL subtask=x kind=text source=y queue=queue:text"

    with caplog.at_level(logging.INFO):
        DispatchCase(FakeWorkQueue(), FakeClock()).execute(hostil, [AUDIO], Priority.ALTA)

    assert all("\n" not in linea for linea in _lineas_de_routing(caplog))
