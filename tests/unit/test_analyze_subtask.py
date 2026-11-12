import hashlib
from datetime import datetime, timezone

import pytest

from src.application.analyze_subtask import AnalyzeSubtask, ShaDistinto, VideoNoSoportado, directorio_de_trabajo
from src.domain.finding import EvidenceRef, Finding, Severity
from src.domain.priority import Priority
from src.domain.subtask import ContentKind, Subtask
from src.workers.fallos import es_transitorio
from tests.dobles import FakeFindingStore, FakeObjectStore

CONTENIDO = b"contenido de la fuente"
SHA = hashlib.sha256(CONTENIDO).hexdigest()


class AnalizadorQueRegistra:
    def __init__(self, hallazgos=(), error=None):
        self.hallazgos = list(hallazgos)
        self.error = error
        self.rutas = []
        self.contenidos = []

    def analyze(self, path):
        self.rutas.append(path)
        self.contenidos.append(path.read_bytes())
        if self.error is not None:
            raise self.error
        return list(self.hallazgos)


def hallazgo():
    return Finding("amenaza", Severity.ALTA, 0.9, EvidenceRef(SHA, "mensaje 1"))


def subtarea(kind=ContentKind.TEXT, sha=SHA):
    return Subtask(
        id=f"caso1:{sha}:{kind.value}", case_id="caso1", kind=kind, source_sha256=sha,
        priority=Priority.MEDIA, enqueued_at=datetime(2026, 11, 3, tzinfo=timezone.utc),
    )


def armar(tmp_path, analizador, contenido=CONTENIDO, cancelado=lambda case_id: False, video=None, kind=ContentKind.TEXT):
    almacen = FakeObjectStore()
    almacen.objetos[SHA] = contenido
    hallazgos = FakeFindingStore()
    caso = AnalyzeSubtask(almacen, {kind: analizador}, hallazgos, tmp_path, cancelado, video_analyzer=video)
    return caso, hallazgos


def test_analyze_subtask_descarga_verifica_sha_y_analiza(tmp_path):
    analizador = AnalizadorQueRegistra([hallazgo()])
    caso, hallazgos = armar(tmp_path, analizador)

    assert caso.execute(subtarea(), "chat.txt") is True

    assert analizador.contenidos == [CONTENIDO]
    assert analizador.rutas[0].name == "fuente.txt"
    assert hallazgos.list("caso1") == [hallazgo()]
    assert ("caso1", subtarea().id) in hallazgos.subtareas


def test_analyze_subtask_sha_distinto_es_fallo_permanente(tmp_path):
    analizador = AnalizadorQueRegistra([hallazgo()])
    caso, hallazgos = armar(tmp_path, analizador, contenido=b"otro contenido")

    with pytest.raises(ShaDistinto) as error:
        caso.execute(subtarea(), "chat.txt")

    assert es_transitorio(error.value) is False
    assert analizador.rutas == []
    assert hallazgos.list("caso1") == []


def test_analyze_subtask_objeto_inexistente_es_fallo_permanente(tmp_path):
    analizador = AnalizadorQueRegistra()
    caso, _ = armar(tmp_path, analizador)

    with pytest.raises(KeyError) as error:
        caso.execute(subtarea(sha="f" * 64), "chat.txt")

    assert es_transitorio(error.value) is False
    assert analizador.rutas == []


@pytest.mark.parametrize("error", [None, ValueError("ilegible")])
def test_analyze_subtask_borra_el_temporal_aunque_falle(tmp_path, error):
    caso, _ = armar(tmp_path, AnalizadorQueRegistra([hallazgo()], error=error))

    if error is None:
        caso.execute(subtarea(), "chat.txt")
    else:
        with pytest.raises(ValueError):
            caso.execute(subtarea(), "chat.txt")

    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("nombre, extension", [
    ("../../etc/passwd.txt", ".txt"),
    (r"..\..\windows\chat.JSON", ".json"),
    ("carpeta/otra/foto.png", ".png"),
    ("sin_extension", ""),
    ("raro.t:x", ""),
])
def test_analyze_subtask_usa_solo_la_extension_del_nombre_de_la_fuente(tmp_path, nombre, extension):
    analizador = AnalizadorQueRegistra()
    caso, _ = armar(tmp_path, analizador)

    caso.execute(subtarea(), nombre)

    ruta = analizador.rutas[0]
    assert ruta.name == f"fuente{extension}"
    assert ruta.parent.parent == tmp_path
    assert ":" not in ruta.parent.name


def test_analyze_subtask_caso_cancelado_no_escribe_hallazgos(tmp_path):
    caso, hallazgos = armar(tmp_path, AnalizadorQueRegistra([hallazgo()]), cancelado=lambda case_id: case_id == "caso1")

    assert caso.execute(subtarea(), "chat.txt") is False

    assert hallazgos.list("caso1") == []
    assert list(tmp_path.iterdir()) == []


def test_directorio_de_trabajo_no_escapa_de_work_dir(tmp_path):
    for identificador in ("c:" + SHA + ":text", "../x:..:text", r"a/b\c:d:audio", ".."):
        directorio = directorio_de_trabajo(tmp_path, identificador)
        assert directorio.parent == tmp_path
        assert ":" not in directorio.name and directorio.name not in ("", ".", "..")


def test_imagen_con_extension_de_video_delega_en_el_analizador_de_video(tmp_path):
    de_imagen = AnalizadorQueRegistra([])
    de_video = AnalizadorQueRegistra([hallazgo()])
    caso, hallazgos = armar(tmp_path, de_imagen, video=de_video, kind=ContentKind.IMAGE)

    assert caso.execute(subtarea(ContentKind.IMAGE), "clip.MP4") is True

    assert de_imagen.rutas == []
    assert de_video.rutas[0].name == "fuente.mp4"
    assert hallazgos.list("caso1") == [hallazgo()]


def test_imagen_con_video_sin_analizador_de_video_es_fallo_permanente(tmp_path):
    caso, _ = armar(tmp_path, AnalizadorQueRegistra(), kind=ContentKind.IMAGE)

    with pytest.raises(VideoNoSoportado) as error:
        caso.execute(subtarea(ContentKind.IMAGE), "clip.mkv")

    assert es_transitorio(error.value) is False


def test_imagen_con_extension_de_imagen_usa_el_analizador_de_imagen(tmp_path):
    de_imagen = AnalizadorQueRegistra([hallazgo()])
    caso, _ = armar(tmp_path, de_imagen, video=AnalizadorQueRegistra(), kind=ContentKind.IMAGE)

    caso.execute(subtarea(ContentKind.IMAGE), "foto.jpg")

    assert de_imagen.rutas[0].name == "fuente.jpg"
