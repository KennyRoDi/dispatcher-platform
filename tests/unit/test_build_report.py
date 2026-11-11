import json
from datetime import datetime, timedelta, timezone

import pytest

from src.application.build_report import CaseNotFound, build_report
from src.application.ports import CaseCatalog, FindingStore
from src.application.report_json import report_to_dict
from src.domain.consolidated_report import CaseInfo, CaseSource, ConsolidatedReport
from src.domain.evidence_position import BoxLocator, MessageLocator, SegmentLocator, UnknownLocator
from src.domain.finding import EvidenceRef, Finding, Severity
from tests.contratos import comprobar_case_catalog, comprobar_finding_store
from tests.dobles import FakeCaseCatalog, FakeClock, FakeFindingStore, FakeObjectStore

SHA_T = "a" * 64
SHA_A = "b" * 64
SHA_I = "c" * 64
INICIO = datetime(2026, 11, 3, 8, 0, tzinfo=timezone.utc)
AHORA = datetime(2026, 11, 3, 10, 0, tzinfo=timezone.utc)
CLAVES = [
    "case_id", "status", "finalizado", "generado_en", "hallazgos",
    "categorias", "linea_temporal", "sin_marca_absoluta", "incidencias",
]


def fuente(sha, tipo, estado="completed", error_type=None):
    return CaseSource(sha, f"{sha}.bin", tipo, estado, error_type)


def caso(fuentes, estado="completed"):
    return CaseInfo("c1", estado, INICIO, INICIO + timedelta(minutes=30), tuple(fuentes))


def hallazgo(categoria, severidad, sha, posicion, detalle=""):
    return Finding(categoria, severidad, 0.9, EvidenceRef(sha, posicion), detalle)


def escenario(hallazgos, info, objetos=(SHA_T, SHA_A, SHA_I)):
    hallazgos_ = FakeFindingStore()
    hallazgos_.add("c1", hallazgos)
    almacen = FakeObjectStore()
    for sha in objetos:
        almacen.objetos[sha] = b"x"
    return hallazgos_, FakeCaseCatalog([info] if info else []), almacen, FakeClock(AHORA)


def construir(hallazgos, info, objetos=(SHA_T, SHA_A, SHA_I), case_id="c1"):
    almacen_h, catalogo, almacen, reloj = escenario(hallazgos, info, objetos)
    return build_report(case_id, almacen_h, catalogo, almacen, reloj)


def heterogeneo():
    marca = "2026-11-03T09:00:00+00:00"
    return [
        hallazgo("amenaza", Severity.ALTA, SHA_T, "mensajes 3", f"3 {marca} wa-3"),
        hallazgo("tema", Severity.BAJA, SHA_T, "mensajes 0-49"),
        hallazgo("transcripcion", Severity.MEDIA, SHA_A, "segmento 2 t=1.00-4.50s", "hola"),
        hallazgo("objeto", Severity.MEDIA, SHA_I, "caja 1,2,30,40"),
    ]


def info_heterogeneo():
    return caso([fuente(SHA_T, "texto"), fuente(SHA_A, "audio"), fuente(SHA_I, "imagen")])


def test_doble_y_puerto_case_catalog_cumplen_el_contrato():
    comprobar_case_catalog(lambda info: FakeCaseCatalog([info]))
    assert isinstance(FakeCaseCatalog(), CaseCatalog)
    assert isinstance(FakeFindingStore(), FindingStore)
    comprobar_finding_store(FakeFindingStore())


def test_reporte_tiene_cuatro_secciones_aun_vacias():
    reporte = construir([], caso([]))
    assert isinstance(reporte, ConsolidatedReport)
    assert reporte.case_id == "c1"
    assert (reporte.findings, reporte.categories, reporte.incidents) == ((), (), ())
    assert (reporte.timeline.dated, reporte.timeline.undated) == ((), ())
    assert reporte.generated_at == AHORA


def test_evidencia_resuelve_a_fuente_y_posicion():
    reporte = construir(heterogeneo(), info_heterogeneo())
    amenaza, lote, audio, imagen = reporte.findings
    fragmento = amenaza.fragments[0]
    assert fragmento.source.sha256 == SHA_T and fragmento.source.kind == "texto"
    assert isinstance(fragmento.locator, MessageLocator)
    assert fragmento.timestamp_utc == datetime(2026, 11, 3, 9, 0, tzinfo=timezone.utc)
    assert fragmento.in_store is True
    assert lote.fragments == ()
    assert audio.fragments[0].locator == SegmentLocator(2, 1.0, 4.5)
    assert audio.fragments[0].span_s == (1.0, 4.5) and audio.fragments[0].timestamp_utc is None
    assert imagen.fragments[0].locator == BoxLocator(1, 2, 30, 40)
    assert imagen.fragments[0].timestamp_utc is None


def test_linea_temporal_separa_eventos_con_y_sin_hora():
    reporte = construir(heterogeneo(), info_heterogeneo())
    assert [e.category for e in reporte.timeline.dated] == ["amenaza"]
    assert sorted(e.category for e in reporte.timeline.undated) == ["objeto", "transcripcion"]


def test_categorias_cuentan_y_toman_severidad_maxima():
    reporte = construir(heterogeneo(), info_heterogeneo())
    por_categoria = {c.category: (c.count, c.max_severity) for c in reporte.categories}
    assert por_categoria["amenaza"] == (1, Severity.ALTA)
    assert por_categoria["tema"] == (1, Severity.BAJA)


def test_evidencia_sin_fuente_en_catalogo_sale_como_incidencia():
    reporte = construir(heterogeneo(), caso([fuente(SHA_T, "texto")]))
    tipos = [i.kind for i in reporte.incidents]
    assert "evidencia_sin_fuente" in tipos
    assert any(f.source is None for r in reporte.findings for f in r.fragments)


def test_objeto_ausente_del_almacen_sale_como_incidencia():
    reporte = construir(heterogeneo(), info_heterogeneo(), objetos=(SHA_T, SHA_A))
    assert "objeto_inexistente" in [i.kind for i in reporte.incidents]
    assert reporte.findings[3].fragments[0].in_store is False


def test_incidencias_incluyen_alta_y_subtarea_fallida():
    info = caso([fuente(SHA_T, "texto"), fuente(SHA_A, "audio", "failed", "TimeoutError")])
    tipos = [i.kind for i in construir(heterogeneo(), info).incidents]
    assert "severidad_alta" in tipos and "subtarea_fallida" in tipos


def test_posicion_desconocida_no_lanza_y_es_incidencia():
    reporte = construir([hallazgo("nueva", Severity.BAJA, SHA_T, "pagina 4")], caso([fuente(SHA_T, "texto")]))
    assert reporte.findings[0].fragments[0].locator == UnknownLocator("pagina 4")
    assert "posicion_desconocida" in [i.kind for i in reporte.incidents]


def test_fuente_se_une_por_file_path_igual_al_sha256():
    info = caso([CaseSource("", SHA_T, "texto", "completed")])
    reporte = construir([hallazgo("amenaza", Severity.BAJA, SHA_T, "mensajes 1")], info)
    assert reporte.findings[0].fragments[0].source.file_path == SHA_T


def test_caso_inexistente_lanza_case_not_found():
    with pytest.raises(CaseNotFound):
        construir([], None, case_id="nada")


@pytest.mark.parametrize("estado, finalizado", [("completed", True), ("processing", False)])
def test_finalizado_segun_estado_del_caso(estado, finalizado):
    assert construir([], caso([], estado)).finished is finalizado


def test_hallazgos_de_otro_caso_no_entran():
    almacen_h, catalogo, almacen, reloj = escenario(heterogeneo(), info_heterogeneo())
    almacen_h.add("c2", [hallazgo("amenaza", Severity.BAJA, SHA_T, "mensajes 9")])
    assert len(build_report("c1", almacen_h, catalogo, almacen, reloj).findings) == 4


def test_reporte_serializa_a_json_con_claves_acordadas():
    datos = report_to_dict(construir(heterogeneo(), info_heterogeneo()))
    assert list(datos) == CLAVES
    assert datos["case_id"] == "c1" and datos["finalizado"] is True
    assert datos["generado_en"] == AHORA.isoformat()
    assert len(datos["hallazgos"]) == 4
    json.dumps(datos)


def test_fragmento_serializado_lleva_fuente_localizador_y_marca():
    datos = report_to_dict(construir(heterogeneo(), info_heterogeneo()))
    por_categoria = {h["categoria"]: h for h in datos["hallazgos"]}
    texto = por_categoria["amenaza"]["evidencia"][0]
    assert list(texto) == ["fuente", "localizador", "timestamp_utc", "tramo_s", "extracto"]
    assert texto["fuente"] == {"sha256": SHA_T, "file_path": f"{SHA_T}.bin", "tipo": "texto"}
    assert texto["timestamp_utc"] == "2026-11-03T09:00:00+00:00"
    audio = por_categoria["transcripcion"]["evidencia"][0]
    assert audio["timestamp_utc"] is None and audio["tramo_s"] == [1.0, 4.5]
    assert por_categoria["tema"]["evidencia"] == []


def test_reporte_vacio_serializa_secciones_vacias():
    datos = report_to_dict(construir([], caso([])))
    assert datos["hallazgos"] == [] and datos["categorias"] == [] and datos["incidencias"] == []
    assert datos["sin_marca_absoluta"] == []


def test_caso_completo_texto_imagen_audio():
    reporte = construir(heterogeneo(), info_heterogeneo())
    datos = report_to_dict(reporte)
    assert {c["categoria"] for c in datos["categorias"]} == {"amenaza", "tema", "transcripcion", "objeto"}
    assert len(datos["linea_temporal"]) == 1 and len(datos["sin_marca_absoluta"]) == 2
    assert any(i["tipo"] == "severidad_alta" for i in datos["incidencias"])
