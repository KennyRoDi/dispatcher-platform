from datetime import datetime, timedelta, timezone

import pytest

from src.domain.consolidated_report import (
    TERMINAL_CASE_STATUSES,
    CaseInfo,
    CaseSource,
    CategorySummary,
    ConsolidatedReport,
    Fragment,
    Incident,
    ReportedFinding,
    Timeline,
    TimelineEvent,
    build_timeline,
    category_summary,
    find_incidents,
)
from src.domain.evidence_position import BoxLocator, MessageLocator, SegmentLocator, UnknownLocator
from src.domain.finding import EvidenceRef, Finding, Severity

SHA_A = "a" * 64
SHA_B = "b" * 64
SHA_C = "c" * 64
INICIO = datetime(2026, 11, 3, 8, 0, tzinfo=timezone.utc)


def instante(minutos):
    return INICIO + timedelta(minutes=minutos)


def fuente(sha, tipo="texto", estado="completed", error_type=None, file_path=None):
    return CaseSource(sha, file_path or f"{sha}.bin", tipo, estado, error_type)


def hallazgo(categoria="amenaza", severidad=Severity.MEDIA, sha=SHA_A, posicion="mensajes 1"):
    return Finding(categoria, severidad, 0.9, EvidenceRef(sha, posicion))


def fragmento(sha=SHA_A, locador=None, marca=None, tramo=None, origen="usar", existe=True, extracto=""):
    if origen == "usar":
        origen = fuente(sha)
    return Fragment(
        sha256=sha,
        source=origen,
        locator=locador or MessageLocator(1, marca, None),
        timestamp_utc=marca,
        span_s=tramo,
        excerpt=extracto,
        in_store=existe,
    )


def reportado(finding=None, *fragmentos):
    return ReportedFinding(finding or hallazgo(), tuple(fragmentos))


def caso(fuentes=(), estado="completed"):
    return CaseInfo("caso-1", estado, instante(0), instante(30), tuple(fuentes))


def tipos(incidencias):
    return [incidencia.kind for incidencia in incidencias]


def test_reporte_tiene_cuatro_secciones():
    reporte = ConsolidatedReport("caso-1", "completed", True, instante(60), (), (), Timeline((), ()), ())
    assert reporte.findings == ()
    assert reporte.categories == ()
    assert reporte.timeline.dated == ()
    assert reporte.timeline.undated == ()
    assert reporte.incidents == ()


def test_evidencia_resuelve_a_fuente():
    origen = fuente(SHA_A, "audio", file_path="audio.mp3")
    segmento = fragmento(SHA_A, SegmentLocator(0, 1.0, 4.5), tramo=(1.0, 4.5), origen=origen, extracto="hola")
    assert (segmento.source.sha256, segmento.source.file_path, segmento.source.kind) == (SHA_A, "audio.mp3", "audio")
    assert (segmento.locator, segmento.span_s, segmento.timestamp_utc, segmento.excerpt) == (
        SegmentLocator(0, 1.0, 4.5),
        (1.0, 4.5),
        None,
        "hola",
    )


@pytest.mark.parametrize("estado", sorted(TERMINAL_CASE_STATUSES))
def test_caso_en_estado_terminal_esta_finalizado(estado):
    assert caso(estado=estado).finished is True


@pytest.mark.parametrize("estado", ["queued", "processing", "pending"])
def test_caso_en_curso_no_esta_finalizado(estado):
    assert caso(estado=estado).finished is False


def test_estados_terminales_coinciden_con_el_coordinador():
    assert TERMINAL_CASE_STATUSES == {"completed", "partially_completed", "failed", "cancelled"}


def test_categorias_cuentan_y_toman_severidad_maxima():
    hallazgos = [
        hallazgo("tema", Severity.BAJA),
        hallazgo("amenaza", Severity.MEDIA),
        hallazgo("amenaza", Severity.ALTA),
        hallazgo("amenaza", Severity.BAJA),
        hallazgo("ofensivo", Severity.MEDIA),
        hallazgo("ofensivo", Severity.BAJA),
    ]
    assert category_summary(hallazgos) == (
        CategorySummary("amenaza", 3, Severity.ALTA),
        CategorySummary("ofensivo", 2, Severity.MEDIA),
        CategorySummary("tema", 1, Severity.BAJA),
    )


def test_categorias_sin_hallazgos_es_vacio():
    assert category_summary([]) == ()


def test_categorias_no_dependen_del_orden_de_entrada():
    hallazgos = [hallazgo("b", Severity.BAJA), hallazgo("a", Severity.ALTA), hallazgo("b", Severity.MEDIA)]
    assert category_summary(hallazgos) == category_summary(list(reversed(hallazgos)))


def test_linea_temporal_ordenada():
    tarde = fragmento(SHA_A, MessageLocator(1, instante(10), None), marca=instante(10))
    temprano = fragmento(SHA_A, MessageLocator(2, instante(2), None), marca=instante(2))
    medio = fragmento(SHA_B, MessageLocator(0, instante(5), None), marca=instante(5))
    lineas = build_timeline([reportado(hallazgo("amenaza"), tarde, temprano), reportado(hallazgo("ofensivo"), medio)])
    assert [evento.fragment for evento in lineas.dated] == [temprano, medio, tarde]
    assert [evento.category for evento in lineas.dated] == ["amenaza", "ofensivo", "amenaza"]
    assert lineas.dated[0] == TimelineEvent("amenaza", Severity.MEDIA, temprano)


def test_linea_temporal_desempata_por_sha256_e_indice():
    mismo = instante(5)
    b0 = fragmento(SHA_B, MessageLocator(0, mismo, None), marca=mismo)
    a7 = fragmento(SHA_A, MessageLocator(7, mismo, None), marca=mismo)
    a3 = fragmento(SHA_A, MessageLocator(3, mismo, None), marca=mismo)
    directa = build_timeline([reportado(hallazgo(), b0, a7, a3)])
    inversa = build_timeline([reportado(hallazgo(), a3, a7, b0)])
    assert [evento.fragment for evento in directa.dated] == [a3, a7, b0]
    assert directa == inversa


def test_eventos_sin_hora_absoluta_van_aparte_y_ordenados():
    audio = fuente(SHA_B, "audio", file_path="b.wav")
    imagen = fuente(SHA_C, "imagen", file_path="a.png")
    tarde = fragmento(SHA_B, SegmentLocator(2, 5.0, 6.0), tramo=(5.0, 6.0), origen=audio)
    pronto = fragmento(SHA_B, SegmentLocator(0, 1.0, 2.0), tramo=(1.0, 2.0), origen=audio)
    caja = fragmento(SHA_C, BoxLocator(1, 2, 3, 4), origen=imagen)
    lineas = build_timeline([reportado(hallazgo("amenaza"), tarde, pronto), reportado(hallazgo("arma"), caja)])
    assert lineas.dated == ()
    assert [evento.fragment for evento in lineas.undated] == [caja, pronto, tarde]


def test_un_mensaje_sin_marca_no_recibe_hora_inventada():
    sin_marca = fragmento(SHA_A, MessageLocator(4, None, None))
    lineas = build_timeline([reportado(hallazgo(), sin_marca)])
    assert lineas.dated == ()
    assert [evento.fragment for evento in lineas.undated] == [sin_marca]


def test_hallazgo_sin_fragmentos_no_genera_eventos():
    assert build_timeline([reportado(hallazgo("tema", posicion="mensajes 0-49"))]) == Timeline((), ())


def test_incidencias_incluyen_alta_fallo_y_evidencia_sin_objeto():
    fallida = fuente(SHA_B, "imagen", estado="failed", error_type="DecodeError")
    sana = fuente(SHA_A)
    alta = reportado(hallazgo("amenaza", Severity.ALTA, SHA_A), fragmento(SHA_A, origen=sana))
    sin_fuente = reportado(hallazgo("ofensivo", sha=SHA_C), fragmento(SHA_C, origen=None))
    sin_objeto = reportado(hallazgo("tema", sha=SHA_A), fragmento(SHA_A, origen=sana, existe=False))
    desconocida = reportado(hallazgo("nueva", sha=SHA_A), fragmento(SHA_A, UnknownLocator("pagina 3"), origen=sana))
    incidencias = find_incidents([alta, sin_fuente, sin_objeto, desconocida], caso([sana, fallida]))
    assert sorted(tipos(incidencias)) == sorted(
        ["severidad_alta", "subtarea_fallida", "evidencia_sin_fuente", "objeto_inexistente", "posicion_desconocida"]
    )


def test_incidencia_de_alta_nombra_la_categoria_y_es_una_por_hallazgo():
    dos = reportado(hallazgo("amenaza", Severity.ALTA), fragmento(SHA_A), fragmento(SHA_A))
    incidencias = find_incidents([dos], caso([fuente(SHA_A)]))
    assert incidencias == (Incident("severidad_alta", incidencias[0].detail, SHA_A, "amenaza"),)


def test_incidencia_de_subtarea_fallida_lleva_el_tipo_de_error():
    fallida = fuente(SHA_B, estado="failed", error_type="DecodeError")
    incidencias = find_incidents([], caso([fuente(SHA_A), fallida]))
    assert tipos(incidencias) == ["subtarea_fallida"]
    assert incidencias[0].sha256 == SHA_B
    assert "DecodeError" in incidencias[0].detail


def test_evidencia_sin_fuente_no_se_cuenta_tambien_como_objeto_inexistente():
    sin_fuente = reportado(hallazgo(), fragmento(SHA_C, origen=None, existe=False))
    assert tipos(find_incidents([sin_fuente], caso())) == ["evidencia_sin_fuente"]


def test_caso_limpio_no_tiene_incidencias():
    limpio = reportado(hallazgo("tema", Severity.BAJA), fragmento(SHA_A))
    assert find_incidents([limpio], caso([fuente(SHA_A)])) == ()


def test_incidencias_son_deterministas_sin_importar_el_orden():
    sana = fuente(SHA_A)
    a = reportado(hallazgo("amenaza", Severity.ALTA, SHA_A), fragmento(SHA_A, origen=sana))
    b = reportado(hallazgo("ofensivo", sha=SHA_C), fragmento(SHA_C, origen=None))
    informacion = caso([sana, fuente(SHA_B, estado="failed", error_type="X")])
    assert find_incidents([a, b], informacion) == find_incidents([b, a], informacion)
