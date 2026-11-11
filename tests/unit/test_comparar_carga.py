import pytest

from scripts.measure.comparar_carga import validar_equivalencia
from src.domain.transcription import TranscriptSegment


SEGMENTO = TranscriptSegment(0.25, 1.5, "texto", 0.875)


def test_validar_equivalencia_compara_todos_los_segmentos():
    salidas = {"por_proceso": [[SEGMENTO]], "workers_compartidos": [[SEGMENTO]]}

    assert validar_equivalencia(salidas) == salidas


@pytest.mark.parametrize(
    "salida",
    [
        TranscriptSegment(0.25, 1.5, "texto", 0.5),
        TranscriptSegment(0.25, 1.6, "texto", 0.875),
        TranscriptSegment(0.25, 1.5, "otro", 0.875),
    ],
)
def test_validar_equivalencia_rechaza_diferencia_de_cualquier_campo(salida):
    salidas = {"por_proceso": [[SEGMENTO]], "workers_compartidos": [[salida]]}

    with pytest.raises(ValueError, match="no coinciden"):
        validar_equivalencia(salidas)


def test_validar_equivalencia_rechaza_estrategia_ausente():
    with pytest.raises(ValueError, match="faltan estrategias"):
        validar_equivalencia({"por_proceso": [[SEGMENTO]]})
