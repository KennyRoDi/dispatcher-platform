from datetime import datetime, timezone

import pytest

from src.domain.decomposition import CaseSource, SourceKind, classify_source, decompose
from src.domain.priority import Priority
from src.domain.subtask import ContentKind

AHORA = datetime(2026, 11, 3, 12, 0, tzinfo=timezone.utc)
AUDIO = CaseSource("c" * 64, "nota.mp3", SourceKind.AUDIO)
VIDEO = CaseSource("d" * 64, "clip.mp4", SourceKind.VIDEO)


def _descomponer(fuentes, caso="C-1"):
    return decompose(caso, fuentes, Priority.ALTA, AHORA)


@pytest.mark.parametrize(
    "nombre, tipo",
    [
        ("carpeta/sub/nota.mp3", SourceKind.AUDIO),
        ("C:\\datos\\NOTA.WAV", SourceKind.AUDIO),
        ("mi nota de voz.MP3", SourceKind.AUDIO),
        ("..mp3", SourceKind.AUDIO),
        ("informe.pdf.mp3", SourceKind.AUDIO),
        ("clip.mp3.mp4", SourceKind.VIDEO),
    ],
)
def test_classify_source_usa_solo_la_extension_final(nombre, tipo):
    assert classify_source(nombre) is tipo


@pytest.mark.parametrize(
    "nombre", ["", ".mp3", "carpeta.mp3/archivo", "nota.mp3 ", "nota.mp3.", "nota.mp3\n", "nota.mp3.pdf"]
)
def test_classify_source_rechaza_nombres_sin_extension_valida(nombre):
    with pytest.raises(ValueError):
        classify_source(nombre)


def test_classify_source_con_none_falla_con_error_de_tipo():
    with pytest.raises((TypeError, ValueError)):
        classify_source(None)


def test_decompose_acepta_tupla_y_generador_de_fuentes():
    assert len(_descomponer((AUDIO, VIDEO))) == 3
    assert len(_descomponer(f for f in [AUDIO, VIDEO])) == 3


def test_decompose_no_muta_su_entrada_ni_comparte_estado_entre_llamadas():
    fuentes = [AUDIO, VIDEO, AUDIO]
    copia = list(fuentes)

    primera = _descomponer(fuentes)
    segunda = _descomponer([AUDIO])

    assert fuentes == copia
    assert len(primera) == 3 and len(segunda) == 1
    assert primera is not segunda


def test_mismo_sha256_con_distinto_tipo_de_fuente_conserva_ids_distintos():
    mismo_sha = CaseSource(AUDIO.sha256, "otro.mp4", SourceKind.VIDEO)

    subtareas = _descomponer([AUDIO, mismo_sha])

    assert [s.id for s in subtareas] == [
        f"C-1:{AUDIO.sha256}:audio",
        f"C-1:{AUDIO.sha256}:image",
    ]


def test_dos_fuentes_del_mismo_tipo_y_sha256_dejan_la_primera():
    primera = CaseSource("e" * 64, "a.txt", SourceKind.TEXT)
    segunda = CaseSource("e" * 64, "b.csv", SourceKind.TEXT)

    subtareas = _descomponer([primera, segunda])

    assert [s.kind for s in subtareas] == [ContentKind.TEXT]


def test_misma_fuente_en_dos_casos_da_ids_distintos():
    assert _descomponer([AUDIO], "C-1")[0].id != _descomponer([AUDIO], "C-2")[0].id
