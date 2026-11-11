from datetime import datetime, timedelta, timezone

import pytest

from src.domain.chat_message import ChatMessage
from src.domain.transcription import TranscriptSegment, segmentos_como_mensajes

EPOCA = datetime(1970, 1, 1, tzinfo=timezone.utc)


def test_segmento_valido_conserva_sus_valores():
    segmento = TranscriptSegment(4.2, 7.85, "nos vemos en la plaza", 0.9)

    assert (segmento.inicio, segmento.fin, segmento.texto, segmento.confianza) == (
        4.2,
        7.85,
        "nos vemos en la plaza",
        0.9,
    )


def test_segmento_recorta_el_texto():
    assert TranscriptSegment(0.0, 1.0, "  hola \n", 0.5).texto == "hola"


@pytest.mark.parametrize("inicio, fin", [(-0.1, 1.0), (0.0, -1.0), (-2.0, -1.0)])
def test_segmento_rechaza_tiempos_negativos(inicio, fin):
    with pytest.raises(ValueError):
        TranscriptSegment(inicio, fin, "hola", 0.5)


def test_segmento_rechaza_fin_anterior_al_inicio():
    with pytest.raises(ValueError):
        TranscriptSegment(5.0, 4.99, "hola", 0.5)


def test_segmento_admite_duracion_cero():
    assert TranscriptSegment(3.0, 3.0, "eh", 0.5).fin == 3.0


@pytest.mark.parametrize("confianza", [-0.01, 1.01, float("nan")])
def test_segmento_rechaza_confianza_fuera_de_rango(confianza):
    with pytest.raises(ValueError):
        TranscriptSegment(0.0, 1.0, "hola", confianza)


@pytest.mark.parametrize("confianza", [0.0, 1.0])
def test_segmento_admite_confianza_en_los_extremos(confianza):
    assert TranscriptSegment(0.0, 1.0, "hola", confianza).confianza == confianza


def test_segmentos_como_mensajes_produce_un_mensaje_por_segmento():
    segmentos = [
        TranscriptSegment(0.0, 4.2, "hola", 0.9),
        TranscriptSegment(4.2, 7.85, "si no pagas vas a ver", 0.8),
    ]

    mensajes = segmentos_como_mensajes(segmentos)

    assert mensajes == [
        ChatMessage(EPOCA, "audio", "hola", "t=0.00-4.20s"),
        ChatMessage(EPOCA + timedelta(seconds=4.2), "audio", "si no pagas vas a ver", "t=4.20-7.85s"),
    ]


def test_segmentos_como_mensajes_usa_hora_en_utc():
    (mensaje,) = segmentos_como_mensajes([TranscriptSegment(12.0, 15.1, "texto", 0.7)])

    assert mensaje.timestamp_utc.utcoffset() == timedelta(0)
    assert mensaje.timestamp_utc == datetime(1970, 1, 1, 0, 0, 12, tzinfo=timezone.utc)
    assert mensaje.source_ref == "t=12.00-15.10s"


def test_segmentos_como_mensajes_sin_segmentos_devuelve_lista_vacia():
    assert segmentos_como_mensajes([]) == []


@pytest.mark.parametrize(
    "inicio, fin", [(0.0, float("inf")), (float("inf"), float("inf")), (float("nan"), 1.0), (0.0, float("nan"))]
)
def test_segmento_rechaza_tiempos_no_finitos(inicio, fin):
    with pytest.raises(ValueError):
        TranscriptSegment(inicio, fin, "hola", 0.5)


@pytest.mark.parametrize("inicio, fin", [(True, 2.0), (0.0, True), (False, False)], ids=["inicio", "fin", "ambos"])
def test_segmento_rechaza_bool_como_tiempo(inicio, fin):
    with pytest.raises(ValueError):
        TranscriptSegment(inicio, fin, "hola", 0.5)


@pytest.mark.parametrize("inicio, fin", [(1e12, 1e12 + 1.0), (0.0, 1e15)], ids=["inicio", "fin"])
def test_tiempo_fuera_del_rango_de_fechas_da_value_error(inicio, fin):
    # 1970 más 1e12 s pasa del año 9999 y datetime lanza OverflowError.
    with pytest.raises(ValueError):
        segmentos_como_mensajes([TranscriptSegment(inicio, fin, "hola", 0.5)])
