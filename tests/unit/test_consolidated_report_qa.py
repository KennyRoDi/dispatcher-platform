import itertools
from datetime import datetime, timedelta, timezone

import pytest

from src.domain.consolidated_report import (
    CaseInfo,
    CaseSource,
    Fragment,
    ReportedFinding,
    build_timeline,
    category_summary,
    find_incidents,
)
from src.domain.evidence_position import BoxLocator, MessageLocator, SegmentLocator, UnknownLocator, parse_position
from src.domain.finding import EvidenceRef, Finding, Severity

SHA_A = "a" * 64
SHA_B = "b" * 64
T0 = datetime(2026, 11, 3, 8, 0, tzinfo=timezone.utc)
CASO = CaseInfo("caso", "completed", None, None, ())


def hallazgo(posicion, detalle="", categoria="amenaza", severidad=Severity.MEDIA, sha=SHA_A):
    return Finding(categoria, severidad, 0.9, EvidenceRef(sha, posicion), detalle)


def fragmento(locador=None, marca=None, sha=SHA_A):
    return Fragment(sha, None, locador or MessageLocator(1, marca, None), marca)


def reportado(categoria, severidad, fragmentos, sha=SHA_A, posicion="mensajes 1"):
    return ReportedFinding(hallazgo(posicion, "", categoria, severidad, sha), tuple(fragmentos))


def categorias_en_orden(timeline_parte, permutaciones):
    return {tuple(e.category for e in timeline_parte(list(p))) for p in permutaciones}


# --- Defectos: lectura de posiciones (evidence_position) ---


@pytest.mark.xfail(
    strict=True,
    reason="`partes[0].isdigit()` acepta '²' y `int('²')` lanza ValueError; un source_ref con '; ² ...' tumba parse_position (debe ignorar la entrada)",
)
def test_un_source_ref_con_digito_superindice_no_rompe_la_lectura():
    detalle = "0 2026-01-01T00:00:00+00:00 ref; ² 2026-01-01T00:00:00+00:00 x"
    assert parse_position(hallazgo("mensajes 0", detalle))[0].index == 0


@pytest.mark.xfail(
    strict=True,
    reason="una marca como 0001-01-01T00:00:00+05:00 hace que astimezone(utc) lance OverflowError, que no se atrapa (solo ValueError)",
)
def test_una_marca_fuera_de_rango_al_pasar_a_utc_no_rompe_la_lectura():
    (locador,) = parse_position(hallazgo("mensajes 0", "0 0001-01-01T00:00:00+05:00 ref"))
    assert locador.timestamp_utc is None


@pytest.mark.xfail(
    strict=True,
    reason="un indice de mas de 4300 digitos hace que int() lance ValueError; debe ser UnknownLocator (la posicion no es de un formato valido)",
)
def test_un_indice_enorme_es_posicion_desconocida_y_no_lanza():
    posicion = "mensajes " + "9" * 5000
    assert parse_position(hallazgo(posicion)) == (UnknownLocator(posicion),)


@pytest.mark.xfail(
    strict=True,
    reason="`\\d` de re acepta digitos Unicode (Arabic-Indic): 'mensajes ٣' se lee como indice 3 en vez de ser desconocida",
)
def test_digitos_no_ascii_no_son_un_indice():
    assert parse_position(hallazgo("mensajes ٣")) == (UnknownLocator("mensajes ٣"),)


@pytest.mark.xfail(
    strict=True,
    reason="un tramo de 400 digitos da float('inf'): SegmentLocator(start_s=inf, end_s=inf) en vez de posicion desconocida",
)
def test_un_tramo_no_finito_es_posicion_desconocida():
    posicion = "segmento 1 t=" + "9" * 400 + "-" + "9" * 400 + "s"
    assert parse_position(hallazgo(posicion)) == (UnknownLocator(posicion),)


@pytest.mark.xfail(
    strict=True,
    reason="un tramo invertido (inicio > fin) se acepta; ningun analizador lo emite y rompe el orden por inicio",
)
def test_un_tramo_invertido_es_posicion_desconocida():
    assert parse_position(hallazgo("segmento 1 t=5.00-1.00s")) == (UnknownLocator("segmento 1 t=5.00-1.00s"),)


@pytest.mark.xfail(
    strict=True,
    reason="una caja con x1>x2 o y1>y2 se acepta; image_detection exige x1<=x2 e y1<=y2, asi que no es un formato real",
)
def test_una_caja_invertida_es_posicion_desconocida():
    assert parse_position(hallazgo("caja 50,50,10,10")) == (UnknownLocator("caja 50,50,10,10"),)


@pytest.mark.xfail(
    strict=True,
    reason="un source_ref con '; 0 <marca falsa> x' en un mensaje posterior sobrescribe (gana el ultimo) la marca real del indice 0; un indice repetido en detail es ambiguo y debe quedar sin marca",
)
def test_un_source_ref_no_puede_falsear_la_marca_de_otro_mensaje():
    detalle = "0 2026-01-01T00:00:00+00:00 r0; 1 2026-01-01T00:00:01+00:00 r1; 0 1999-01-01T00:00:00+00:00 falsa"
    primero = parse_position(hallazgo("mensajes 0,1", detalle))[0]
    assert primero.timestamp_utc != datetime(1999, 1, 1, tzinfo=timezone.utc)


# --- Defectos: reporte (consolidated_report) ---


@pytest.mark.xfail(
    strict=True,
    reason="Fragment acepta timestamp_utc sin zona y build_timeline lanza TypeError al comparar naive con aware; debe rechazarse al crear el Fragment (ValueError) o tolerarse",
)
def test_una_marca_sin_zona_no_rompe_la_linea_temporal():
    try:
        sin_zona = fragmento(marca=datetime(2026, 1, 1))
    except ValueError:
        return
    con_zona = fragmento(marca=T0)
    build_timeline([reportado("x", Severity.BAJA, [sin_zona, con_zona])])


@pytest.mark.xfail(
    strict=True,
    reason="Fragment.timestamp_utc acepta una zona +05:00 y la conserva: el campo se llama UTC y el JSON saldria con otro offset; debe normalizarse o rechazarse",
)
def test_una_marca_con_otra_zona_se_normaliza_o_se_rechaza():
    otra_zona = datetime(2026, 1, 1, tzinfo=timezone(timedelta(hours=5)))
    try:
        evento = build_timeline([reportado("x", Severity.BAJA, [fragmento(marca=otra_zona)])]).dated[0]
    except ValueError:
        return
    assert evento.fragment.timestamp_utc.utcoffset() == timedelta(0)


@pytest.mark.xfail(
    strict=True,
    reason="dos hallazgos distintos en el mismo mensaje (misma marca, sha e indice) empatan en la clave y el orden depende del orden de entrada; SPEC exige orden determinista",
)
def test_dos_categorias_en_el_mismo_mensaje_ordenan_igual_sin_importar_la_entrada():
    a = reportado("amenaza", Severity.BAJA, [fragmento(marca=T0)])
    b = reportado("ofensa", Severity.ALTA, [fragmento(marca=T0)])
    assert len(categorias_en_orden(lambda r: build_timeline(r).dated, itertools.permutations([a, b]))) == 1


@pytest.mark.xfail(
    strict=True,
    reason="mismo caso para eventos sin marca (audio): clave (ruta, inicio, sha, indice) empata entre categorias y el orden depende de la entrada",
)
def test_dos_categorias_en_el_mismo_segmento_ordenan_igual_sin_importar_la_entrada():
    segmento = SegmentLocator(1, 1.0, 2.0)
    a = reportado("amenaza", Severity.BAJA, [fragmento(segmento)])
    b = reportado("ofensa", Severity.ALTA, [fragmento(segmento)])
    assert len(categorias_en_orden(lambda r: build_timeline(r).undated, itertools.permutations([a, b]))) == 1


@pytest.mark.xfail(
    strict=True,
    reason="un inicio NaN en SegmentLocator rompe el orden total de sorted: el resultado cambia segun la permutacion de entrada",
)
def test_un_inicio_nan_no_vuelve_indeterminista_el_orden():
    nan = float("nan")
    reportados = [
        reportado("x", Severity.BAJA, [fragmento(SegmentLocator(0, nan if i == 1 else float(i), 9.0), sha=str(i) * 64)])
        for i in range(4)
    ]
    ordenes = {
        tuple(e.fragment.sha256[0] for e in build_timeline(list(p)).undated)
        for p in itertools.permutations(reportados)
    }
    assert len(ordenes) == 1


@pytest.mark.xfail(
    strict=True,
    reason="find_incidents deduplica con un set y el detalle de severidad_alta no lleva la posicion: dos hallazgos ALTA distintos de la misma categoria y objeto producen una sola incidencia",
)
def test_dos_hallazgos_alta_distintos_dan_dos_incidencias():
    r1 = reportado("amenaza", Severity.ALTA, [], posicion="mensajes 1")
    r2 = reportado("amenaza", Severity.ALTA, [], posicion="mensajes 2")
    assert len(find_incidents([r1, r2], CASO)) == 2


# --- Lo que no se pudo romper ---


def test_las_funciones_no_mutan_sus_entradas():
    reportados = [reportado("x", Severity.ALTA, [fragmento(marca=T0)])]
    copia = list(reportados)
    build_timeline(reportados)
    find_incidents(reportados, CASO)
    assert reportados == copia


def test_marcas_con_distinta_zona_se_ordenan_por_instante():
    tarde_en_utc = datetime(2026, 1, 1, 10, tzinfo=timezone.utc)
    temprano_en_otra_zona = datetime(2026, 1, 1, 12, tzinfo=timezone(timedelta(hours=3)))
    eventos = build_timeline(
        [reportado("x", Severity.BAJA, [fragmento(marca=tarde_en_utc, sha=SHA_A), fragmento(marca=temprano_en_otra_zona, sha=SHA_B)])]
    ).dated
    assert [e.fragment.sha256 for e in eventos] == [SHA_B, SHA_A]


def test_el_orden_es_estable_con_claves_distintas_en_cualquier_permutacion():
    reportados = [reportado("x", Severity.BAJA, [fragmento(MessageLocator(i, T0, None), T0, sha=SHA_A)]) for i in range(4)]
    ordenes = {tuple(e.fragment.locator.index for e in build_timeline(list(p)).dated) for p in itertools.permutations(reportados)}
    assert ordenes == {(0, 1, 2, 3)}


def test_listas_vacias_dan_resultados_vacios():
    assert category_summary([]) == ()
    assert find_incidents([], CASO) == ()
    assert build_timeline([]).dated == () and build_timeline([]).undated == ()


def test_localizadores_de_distinto_tipo_en_un_mismo_objeto_se_ordenan_sin_error():
    locadores = [BoxLocator(1, 2, 3, 4), UnknownLocator("z"), MessageLocator(1, None, None), SegmentLocator(0, 0.0, 1.0)]
    build_timeline([reportado("x", Severity.BAJA, [fragmento(loc) for loc in locadores])])


def test_una_subtarea_fallida_sin_tipo_de_error_se_lista():
    caso = CaseInfo("c", "failed", None, None, (CaseSource(SHA_A, "a.mp3", "audio", "failed", ""),))
    (incidencia,) = find_incidents([], caso)
    assert "sin tipo de error" in incidencia.detail


def test_las_posiciones_con_salto_de_linea_o_basura_final_son_desconocidas():
    assert parse_position(hallazgo("mensajes 1\n")) == (UnknownLocator("mensajes 1\n"),)


def test_una_marca_sin_zona_en_el_detalle_se_descarta_sin_lanzar():
    (locador,) = parse_position(hallazgo("mensajes 0", "0 2026-01-01T00:00:00 ref"))
    assert locador.timestamp_utc is None
