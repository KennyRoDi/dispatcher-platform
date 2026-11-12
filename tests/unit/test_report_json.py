import json
from datetime import datetime, timedelta, timezone

from src.application.build_report import build_report
from src.application.report_json import report_to_dict
from src.domain.consolidated_report import CaseInfo, CaseSource
from src.domain.finding import EvidenceRef, Finding, Severity
from tests.dobles import FakeCaseCatalog, FakeClock, FakeFindingStore, FakeObjectStore

SHA_VIDEO = "d" * 64
INICIO = datetime(2026, 11, 3, 8, 0, tzinfo=timezone.utc)


def reporte_con(posicion):
    hallazgos = FakeFindingStore()
    hallazgos.add("c1", [Finding("arma", Severity.ALTA, 0.9, EvidenceRef(SHA_VIDEO, posicion))])
    fuente = CaseSource(SHA_VIDEO, "video.mp4", "video", "completed", None)
    caso = CaseInfo("c1", "completed", INICIO, INICIO + timedelta(minutes=5), (fuente,))
    almacen = FakeObjectStore()
    almacen.objetos[SHA_VIDEO] = b"x"
    return build_report("c1", hallazgos, FakeCaseCatalog([caso]), almacen, FakeClock(INICIO))


def test_reporte_serializa_el_localizador_de_fotograma():
    datos = report_to_dict(reporte_con("fotograma t=10s caja 1,2,30,40"))

    evidencia = datos["hallazgos"][0]["evidencia"][0]
    assert evidencia["localizador"] == {"tipo": "fotograma", "t_s": 10.0, "x1": 1, "y1": 2, "x2": 30, "y2": 40}
    assert evidencia["fuente"]["sha256"] == SHA_VIDEO
    json.dumps(datos, allow_nan=False)


def test_fotograma_del_video_no_marca_evidencia_sin_fuente_ni_posicion_desconocida():
    datos = report_to_dict(reporte_con("fotograma t=10s caja 1,2,30,40"))

    assert [i["tipo"] for i in datos["incidencias"]] == ["severidad_alta"]
