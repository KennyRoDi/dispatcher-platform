from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.domain.finding import EvidenceRef, Finding, Severity
from src.domain.frame_sampling import Frame, FrameSampling
from src.domain.priority import Priority
from src.domain.subtask import ContentKind, Subtask
from src.workers.typed_worker import video_por_subtarea

SHA_VIDEO = "b" * 64


class SupervisorDeSubtarea:
    def __init__(self, case_id):
        self.case_id = case_id
        self.cerrado = False

    def cerrar(self):
        self.cerrado = True


class Registro:
    def __init__(self):
        self.entregados = []

    def para_subtarea(self, case_id):
        self.entregados.append(SupervisorDeSubtarea(case_id))
        return self.entregados[-1]


class Extractor:
    def __init__(self, muestreo, supervisor):
        self.muestreo = muestreo
        self.supervisor = supervisor

    def extract(self, path, out_dir):
        marco = Path(out_dir) / "frame_0001.jpg"
        marco.write_bytes(b"jpg")
        return [Frame(marco, 5.0)]


class AnalizadorDeImagen:
    def analyze(self, path):
        return [Finding("arma", Severity.ALTA, 0.9, EvidenceRef("f" * 64, "caja 1,2,3,4"), "cuchillo")]


def subtarea():
    return Subtask(
        id="caso1:" + SHA_VIDEO + ":image", case_id="caso1", kind=ContentKind.IMAGE, source_sha256=SHA_VIDEO,
        priority=Priority.MEDIA, enqueued_at=datetime(2026, 11, 3, tzinfo=timezone.utc),
    )


def crear(tmp_path, registro, cancelado=lambda case_id: False):
    fabricas = []

    def extractor(muestreo, supervisor):
        fabricas.append(Extractor(muestreo, supervisor))
        return fabricas[-1]

    crear_video = video_por_subtarea(
        {"FRAME_EVERY_S": "2", "FRAME_MAX": "7"}, lambda: registro, AnalizadorDeImagen(), cancelado,
        sha256_of=lambda path: SHA_VIDEO, extractor=extractor,
    )
    return crear_video, fabricas


def test_cada_subtarea_obtiene_su_supervisor_y_lo_cierra_al_terminar(tmp_path):
    registro = Registro()
    crear_video, extractores = crear(tmp_path, registro)
    video = tmp_path / "fuente.mp4"
    video.write_bytes(b"video")

    hallazgos = crear_video(subtarea()).analyze(video)

    assert [s.case_id for s in registro.entregados] == ["caso1"]
    assert extractores[0].supervisor is registro.entregados[0]
    assert registro.entregados[0].cerrado is True
    assert extractores[0].muestreo == FrameSampling(2.0, 7)
    assert [h.evidence.object_sha256 for h in hallazgos] == [SHA_VIDEO]
    assert hallazgos[0].evidence.position == "fotograma t=5s caja 1,2,3,4"
    assert list(tmp_path.iterdir()) == [video]


def test_sin_registro_de_subprocesos_se_extrae_sin_supervisor(tmp_path):
    video = tmp_path / "fuente.mp4"
    video.write_bytes(b"video")
    crear_video, extractores = crear(tmp_path, None)

    crear_video(subtarea()).analyze(video)

    assert extractores[0].supervisor is None


def test_el_supervisor_se_cierra_aunque_falle_la_extraccion(tmp_path):
    registro = Registro()
    crear_video, extractores = crear(tmp_path, registro)
    video = tmp_path / "fuente.mp4"
    video.write_bytes(b"video")
    analizador = crear_video(subtarea())

    def extraer_con_error(path, out_dir):
        raise RuntimeError("ffmpeg murio")

    extractores[0].extract = extraer_con_error
    with pytest.raises(RuntimeError):
        analizador.analyze(video)

    assert registro.entregados[0].cerrado is True
