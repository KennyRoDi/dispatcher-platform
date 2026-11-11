from datetime import datetime, timezone

import pytest

from src.application.analyze_audio import SegmentPositions
from src.application.analyze_text import MessagePositions
from src.domain.chat_message import ChatMessage
from src.domain.evidence_position import (
    BoxLocator,
    MessageLocator,
    SegmentLocator,
    UnknownLocator,
    parse_position,
)
from src.domain.finding import EvidenceRef, Finding, Severity
from src.domain.transcription import TranscriptSegment

SHA = "a" * 64
INICIO = datetime(2026, 11, 3, 8, 0, tzinfo=timezone.utc)
OCHO_CINCO = datetime(2026, 11, 3, 8, 5, tzinfo=timezone.utc)


def hallazgo(categoria, posicion, detalle=""):
    return Finding(categoria, Severity.ALTA, 0.9, EvidenceRef(SHA, posicion), detalle)


def test_parse_position_mensajes_con_marca_utc():
    detalle = "3 2026-11-03T08:00:00+00:00 sintetico-1-4; 7 2026-11-03T08:05:00+00:00 sintetico-1-8"
    locadores = parse_position(hallazgo("amenaza", "mensajes 3,7", detalle))
    assert locadores == (
        MessageLocator(3, INICIO, "sintetico-1-4"),
        MessageLocator(7, OCHO_CINCO, "sintetico-1-8"),
    )


def test_parse_position_mensaje_sin_marca_en_el_detalle_deja_la_marca_vacia():
    assert parse_position(hallazgo("ofensivo", "mensajes 3")) == (MessageLocator(3, None, None),)


def test_parse_position_lee_lo_que_emite_message_positions():
    mensajes = [ChatMessage(INICIO, "ana", "hola", "ref-0"), ChatMessage(OCHO_CINCO, "luis", "vas a ver", "ref-1")]
    marcados = list(enumerate(mensajes))
    posiciones = MessagePositions()
    finding = hallazgo("amenaza", posiciones.lista(marcados), posiciones.detalle(marcados))
    assert parse_position(finding) == (MessageLocator(0, INICIO, "ref-0"), MessageLocator(1, OCHO_CINCO, "ref-1"))


def test_parse_position_segmento_con_tramo():
    finding = hallazgo("transcripcion", "segmento 2 t=1.00-4.50s", "hola mundo")
    assert parse_position(finding) == (SegmentLocator(2, 1.0, 4.5),)


def test_parse_position_segmentos_marcados_con_un_tramo_por_indice():
    finding = hallazgo("amenaza", "segmentos 1,4 t=1.00-4.50s,5.00-6.25s", "1 t=1.00-4.50s; 4 t=5.00-6.25s")
    assert parse_position(finding) == (SegmentLocator(1, 1.0, 4.5), SegmentLocator(4, 5.0, 6.25))


def test_parse_position_lee_lo_que_emite_segment_positions():
    segmentos = [TranscriptSegment(0.0, 2.0, "hola", 0.9), TranscriptSegment(2.5, 4.0, "vas a ver", 0.8)]
    posiciones = SegmentPositions(segmentos)
    marcados = list(enumerate(segmentos))
    finding = hallazgo("amenaza", posiciones.lista(marcados), posiciones.detalle(marcados))
    assert parse_position(finding) == (SegmentLocator(0, 0.0, 2.0), SegmentLocator(1, 2.5, 4.0))


def test_parse_position_caja_de_imagen():
    assert parse_position(hallazgo("arma", "caja 10,20,110,220")) == (BoxLocator(10, 20, 110, 220),)


@pytest.mark.parametrize("posicion", ["mensajes 0-49", "mensajes 50-99", "segmentos 0-2 t=0.00-9.00s"])
def test_parse_position_rango_de_lote_no_es_evidencia(posicion):
    assert parse_position(hallazgo("tema", posicion, "conflicto")) == ()


@pytest.mark.parametrize("posicion", ["pagina 3", "caja 1,2,3", "mensajes x", "", "segmento 2"])
def test_parse_position_desconocida_no_lanza(posicion):
    assert parse_position(hallazgo("nueva", posicion)) == (UnknownLocator(posicion),)


def test_los_localizadores_son_inmutables():
    with pytest.raises(AttributeError):
        BoxLocator(1, 2, 3, 4).x1 = 9
