from datetime import datetime, timezone

import pytest

from src.domain.decomposition import (
    QUEUE_BY_KIND,
    CaseSource,
    SourceKind,
    classify_source,
    decompose,
    queue_for,
)
from src.domain.priority import Priority
from src.domain.subtask import ContentKind

AHORA = datetime(2026, 11, 3, 12, 0, tzinfo=timezone.utc)
OPERACIONES_FFMPEG = {"transcode_video", "extract_audio", "generate_thumbnail", "convert_audio", "extract_metadata"}

TEXTO = CaseSource("a" * 64, "chat.txt", SourceKind.TEXT)
IMAGEN = CaseSource("b" * 64, "foto.png", SourceKind.IMAGE)
AUDIO = CaseSource("c" * 64, "nota.mp3", SourceKind.AUDIO)
VIDEO = CaseSource("d" * 64, "clip.mp4", SourceKind.VIDEO)


def descomponer(fuentes, caso="C-1"):
    return decompose(caso, fuentes, Priority.ALTA, AHORA)


def test_video_genera_subtareas_de_audio_e_imagen():
    subtareas = descomponer([VIDEO])

    assert sorted(s.kind.value for s in subtareas) == ["audio", "image"]
    assert {s.source_sha256 for s in subtareas} == {VIDEO.sha256}


def test_caso_heterogeneo_da_una_subtarea_por_fuente_y_dos_por_video():
    subtareas = descomponer([TEXTO, IMAGEN, AUDIO, VIDEO])

    assert [(s.source_sha256, s.kind) for s in subtareas] == [
        (TEXTO.sha256, ContentKind.TEXT),
        (IMAGEN.sha256, ContentKind.IMAGE),
        (AUDIO.sha256, ContentKind.AUDIO),
        (VIDEO.sha256, ContentKind.IMAGE),
        (VIDEO.sha256, ContentKind.AUDIO),
    ]
    assert {s.case_id for s in subtareas} == {"C-1"}
    assert {s.priority for s in subtareas} == {Priority.ALTA}
    assert {s.enqueued_at for s in subtareas} == {AHORA}


def test_id_de_subtarea_es_caso_sha256_y_tipo():
    subtareas = descomponer([TEXTO, VIDEO], caso="C-9")

    assert [s.id for s in subtareas] == [
        f"C-9:{TEXTO.sha256}:text",
        f"C-9:{VIDEO.sha256}:image",
        f"C-9:{VIDEO.sha256}:audio",
    ]


def test_descomponer_dos_veces_da_lo_mismo():
    assert descomponer([TEXTO, VIDEO]) == descomponer([TEXTO, VIDEO])


def test_dentro_de_un_video_la_imagen_va_antes_que_el_audio():
    assert [s.kind for s in descomponer([VIDEO])] == [ContentKind.IMAGE, ContentKind.AUDIO]


def test_fuente_repetida_no_duplica_subtarea():
    repetida = CaseSource(VIDEO.sha256, "copia.mp4", SourceKind.VIDEO)

    subtareas = descomponer([VIDEO, repetida, TEXTO, TEXTO])

    assert len(subtareas) == 3
    assert len({s.id for s in subtareas}) == 3


def test_extension_desconocida_se_rechaza():
    with pytest.raises(ValueError, match="informe.pdf"):
        classify_source("informe.pdf")


def test_nombre_sin_extension_se_rechaza():
    with pytest.raises(ValueError, match="LEEME"):
        classify_source("LEEME")


def test_caso_sin_fuentes_da_lista_vacia():
    assert descomponer([]) == []


@pytest.mark.parametrize(
    "extension, tipo",
    [(e, SourceKind.TEXT) for e in (".txt", ".csv", ".json")]
    + [(e, SourceKind.IMAGE) for e in (".jpg", ".jpeg", ".png")]
    + [(e, SourceKind.AUDIO) for e in (".mp3", ".wav", ".flac", ".ogg", ".m4a", ".aac", ".opus", ".wma")]
    + [(e, SourceKind.VIDEO) for e in (".mp4", ".mkv", ".avi", ".mov", ".webm", ".flv", ".wmv", ".m4v")],
)
def test_classify_source_reconoce_cada_extension(extension, tipo):
    assert classify_source(f"archivo{extension}") is tipo


def test_classify_source_no_distingue_mayusculas():
    assert classify_source("FOTO.JPG") is SourceKind.IMAGE
    assert classify_source("Clip.MP4") is SourceKind.VIDEO


def test_classify_source_usa_la_ultima_extension():
    assert classify_source("copia.tar.mp3") is SourceKind.AUDIO


def test_classify_source_incluye_las_extensiones_del_camino_heredado():
    from src.coordinator.router import _AUDIO_EXTS, _VIDEO_EXTS

    assert all(classify_source(f"x{e}") is SourceKind.VIDEO for e in _VIDEO_EXTS)
    assert all(classify_source(f"x{e}") is SourceKind.AUDIO for e in _AUDIO_EXTS)


def test_tipo_enruta_a_su_cola():
    assert {k: queue_for(k) for k in ContentKind} == {
        ContentKind.TEXT: "queue:text",
        ContentKind.IMAGE: "queue:image",
        ContentKind.AUDIO: "queue:audio",
    }
    colas = list(QUEUE_BY_KIND.values())
    assert set(QUEUE_BY_KIND) == set(ContentKind)
    assert len(set(colas)) == len(ContentKind)
    assert not set(colas) & {f"queue:{op}" for op in OPERACIONES_FFMPEG}
