from pathlib import Path

import pytest

from src.application.analyze_video import AnalyzeVideo
from src.domain.evidence_position import BoxLocator, FrameLocator, parse_position
from src.domain.finding import EvidenceRef, Finding, Severity
from src.domain.frame_sampling import Frame
from src.workers.multimedia_processor import CorruptInputError, ProcessingError

SHA_VIDEO = "v" * 64
SHA_FOTOGRAMA = "f" * 64


class ExtractorFalso:
    def __init__(self, tiempos=(0.0, 5.0, 10.0), error=None):
        self.tiempos, self.error, self.directorios = tiempos, error, []

    def extract(self, path, out_dir):
        self.directorios.append(out_dir)
        if self.error:
            raise self.error
        frames = []
        for indice, t_s in enumerate(self.tiempos):
            frame = out_dir / f"frame_{indice}.jpg"
            frame.write_bytes(b"jpg")
            frames.append(Frame(frame, t_s))
        return frames


class AnalizadorDeImagenFalso:
    def __init__(self, por_fotograma=None, falla_en=None, al_analizar=lambda: None):
        self.por_fotograma = por_fotograma or {}
        self.falla_en, self.al_analizar, self.vistos = falla_en, al_analizar, []

    def analyze(self, path):
        self.vistos.append(path)
        self.al_analizar()
        if path.name == self.falla_en:
            raise RuntimeError("modelo caido")
        return self.por_fotograma.get(path.name, [])


def hallazgo(posicion="caja 1,2,30,40"):
    return Finding("arma", Severity.ALTA, 0.9, EvidenceRef(SHA_FOTOGRAMA, posicion), "pistola ×1")


@pytest.fixture
def video(tmp_path):
    ruta = tmp_path / "fuente.mp4"
    ruta.write_bytes(b"video")
    return ruta


def construir(extractor, analizador, **kwargs):
    return AnalyzeVideo(extractor, analizador, lambda ruta: SHA_VIDEO, **kwargs)


def test_video_analiza_cada_fotograma_y_une_los_hallazgos_con_posicion_de_tiempo(video):
    analizador = AnalizadorDeImagenFalso({"frame_0.jpg": [hallazgo("caja 1,2,3,4")], "frame_2.jpg": [hallazgo()]})

    hallazgos = construir(ExtractorFalso(), analizador).analyze(video)

    assert [h.evidence.position for h in hallazgos] == ["fotograma t=0s caja 1,2,3,4", "fotograma t=10s caja 1,2,30,40"]
    assert len(analizador.vistos) == 3
    assert parse_position(hallazgos[1]) == (FrameLocator(10.0, BoxLocator(1, 2, 30, 40)),)
    conservado = (hallazgos[1].category, hallazgos[1].severity, hallazgos[1].confidence, hallazgos[1].detail)
    assert conservado == ("arma", Severity.ALTA, 0.9, "pistola ×1")


def test_hallazgos_de_fotograma_apuntan_al_sha_del_video_original(video):
    analizador = AnalizadorDeImagenFalso({"frame_1.jpg": [hallazgo()]})

    hallazgos = construir(ExtractorFalso(), analizador).analyze(video)

    assert [h.evidence.object_sha256 for h in hallazgos] == [SHA_VIDEO]


def test_video_sin_hallazgos_en_los_fotogramas_devuelve_lista_vacia(video):
    assert construir(ExtractorFalso(), AnalizadorDeImagenFalso()).analyze(video) == []


def test_video_sin_fotogramas_es_fallo_permanente(video):
    with pytest.raises(ValueError, match="ningún fotograma"):
        construir(ExtractorFalso(tiempos=()), AnalizadorDeImagenFalso()).analyze(video)


def test_video_ilegible_es_fallo_permanente(video):
    extractor = ExtractorFalso(error=CorruptInputError("fuente.mp4: ffprobe no pudo leer el archivo"))

    with pytest.raises(ProcessingError):
        construir(extractor, AnalizadorDeImagenFalso()).analyze(video)


@pytest.mark.parametrize("falla", [False, True])
def test_fotogramas_se_borran_aunque_falle_el_analisis(video, falla):
    extractor = ExtractorFalso()
    analisis = construir(extractor, AnalizadorDeImagenFalso(falla_en="frame_1.jpg" if falla else None))

    if falla:
        with pytest.raises(RuntimeError):
            analisis.analyze(video)
    else:
        analisis.analyze(video)

    assert not extractor.directorios[0].exists()
    assert [p.name for p in video.parent.iterdir()] == ["fuente.mp4"]


def test_fotogramas_se_borran_si_la_extraccion_falla(video):
    extractor = ExtractorFalso(error=ProcessingError("x"))

    with pytest.raises(ProcessingError):
        construir(extractor, AnalizadorDeImagenFalso()).analyze(video)

    assert not extractor.directorios[0].exists()


def test_cancelacion_entre_fotogramas_detiene_el_analisis(video):
    cancelado = []
    analizador = AnalizadorDeImagenFalso({"frame_0.jpg": [hallazgo()]}, al_analizar=lambda: cancelado.append(True))

    hallazgos = construir(ExtractorFalso(), analizador, is_cancelled=lambda: bool(cancelado)).analyze(video)

    assert [Path(p).name for p in analizador.vistos] == ["frame_0.jpg"]
    assert len(hallazgos) == 1
