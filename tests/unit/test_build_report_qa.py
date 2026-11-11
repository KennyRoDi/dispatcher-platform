import copy
import json
from datetime import datetime, timedelta, timezone

import pytest

from src.application.build_report import CaseNotFound, build_report
from src.application.report_json import report_to_dict
from src.domain.consolidated_report import CaseInfo, CaseSource
from src.domain.finding import EvidenceRef, Finding, Severity
from tests.dobles import FakeCaseCatalog, FakeClock, FakeFindingStore, FakeObjectStore

SHA_T = "a" * 64
SHA_A = "b" * 64
SHA_I = "c" * 64
INICIO = datetime(2026, 11, 3, 8, 0, tzinfo=timezone.utc)
AHORA = datetime(2026, 11, 3, 10, 0, tzinfo=timezone.utc)


def fuente(sha, tipo="texto", estado="completed", ruta=None):
    return CaseSource(sha, ruta if ruta is not None else f"{sha}.bin", tipo, estado)


def caso(fuentes, estado="completed", case_id="c1"):
    return CaseInfo(case_id, estado, INICIO, INICIO + timedelta(minutes=30), tuple(fuentes))


def hallazgo(categoria, severidad, sha, posicion, detalle=""):
    return Finding(categoria, severidad, 0.9, EvidenceRef(sha, posicion), detalle)


def armar(hallazgos, info, objetos=(SHA_T, SHA_A, SHA_I), reloj=None, almacen=None):
    hallazgos_ = FakeFindingStore()
    hallazgos_.add("c1", hallazgos)
    almacen = almacen or FakeObjectStore()
    for sha in objetos:
        almacen.objetos[sha] = b"x"
    catalogo = FakeCaseCatalog([info] if info else [])
    return hallazgos_, catalogo, almacen, reloj or FakeClock(AHORA)


def construir(hallazgos, info, **kw):
    return build_report("c1", *armar(hallazgos, info, **kw))


def a_json(reporte):
    return json.dumps(report_to_dict(reporte), allow_nan=False, ensure_ascii=False)


# --- Defectos ---


def test_extracto_de_amenaza_en_audio_no_repite_el_detalle_entero_en_cada_segmento():
    detalle = "1 t=0.00-1.00s; 4 t=3.00-4.00s"
    h = hallazgo("amenaza", Severity.ALTA, SHA_A, "segmentos 1,4 t=0.00-1.00s,3.00-4.00s", detalle)
    fragmentos = construir([h], caso([fuente(SHA_A, "audio")])).findings[0].fragments
    assert len(fragmentos) == 2
    assert all(f.excerpt != detalle for f in fragmentos)


def test_extracto_enorme_se_limita():
    h = hallazgo("transcripcion", Severity.BAJA, SHA_A, "segmento 0 t=0.00-1.00s", "palabra " * 700_000)
    fragmento = construir([h], caso([fuente(SHA_A, "audio")])).findings[0].fragments[0]
    assert len(fragmento.excerpt) <= 10_000


def test_generado_en_sale_en_utc_aunque_el_reloj_use_otra_zona():
    reloj = FakeClock(datetime(2026, 11, 3, 12, 0, tzinfo=timezone(timedelta(hours=2))))
    datos = report_to_dict(construir([], caso([]), reloj=reloj))
    assert datos["generado_en"] == "2026-11-03T10:00:00+00:00"


def test_sha_vacio_no_se_une_a_una_fuente_sin_sha():
    info = caso([CaseSource("", "otro-archivo.txt", "texto", "completed")])
    reporte = construir([hallazgo("amenaza", Severity.BAJA, "", "mensajes 1")], info)
    assert reporte.findings[0].fragments[0].source is None


def test_surrogate_suelto_no_impide_codificar_el_json_en_utf8():
    h = hallazgo("transcripcion", Severity.BAJA, SHA_A, "segmento 0 t=0.00-1.00s", "hola \ud800 mundo")
    a_json(construir([h], caso([fuente(SHA_A, "audio")]))).encode("utf-8")


def test_almacen_que_falla_no_impide_reportar_hallazgos_de_lote():
    class AlmacenCaido(FakeObjectStore):
        def exists(self, sha256):
            raise ConnectionError("MinIO caido")

    h = hallazgo("tema", Severity.BAJA, SHA_T, "mensajes 0-49")
    reporte = construir([h], caso([fuente(SHA_T)]), almacen=AlmacenCaido())
    assert len(reporte.findings) == 1


def test_exists_se_consulta_una_vez_por_sha_y_solo_si_hay_fragmentos():
    class Contador(FakeObjectStore):
        llamadas = []

        def exists(self, sha256):
            self.llamadas.append(sha256)
            return super().exists(sha256)

    almacen = Contador()
    hs = [hallazgo("amenaza", Severity.BAJA, SHA_T, f"mensajes {i}") for i in range(5)]
    hs.append(hallazgo("tema", Severity.BAJA, SHA_T, "mensajes 0-49"))
    construir(hs, caso([fuente(SHA_T)]), almacen=almacen)
    assert len(almacen.llamadas) == 1


# --- Intentos que no rompen el codigo (pasan) ---


def test_caso_inexistente_lanza_case_not_found_con_hallazgos_huerfanos():
    almacen_h, catalogo, almacen, reloj = armar([hallazgo("amenaza", Severity.BAJA, SHA_T, "mensajes 1")], None)
    with pytest.raises(CaseNotFound):
        build_report("c1", almacen_h, catalogo, almacen, reloj)


def test_caso_sin_hallazgos_ni_fuentes_serializa_json_valido():
    datos = json.loads(a_json(construir([], caso([]))))
    assert datos["hallazgos"] == [] and datos["incidencias"] == []


def test_caso_sin_hallazgos_con_subtarea_fallida_la_reporta():
    info = caso([CaseSource(SHA_T, "x.bin", "texto", "failed", "TimeoutError")])
    reporte = construir([], info)
    assert [i.kind for i in reporte.incidents] == ["subtarea_fallida"]


def test_hallazgo_de_sha_sin_fuente_ni_objeto_solo_marca_sin_fuente():
    reporte = construir([hallazgo("amenaza", Severity.BAJA, SHA_I, "mensajes 1")], caso([fuente(SHA_T)]), objetos=())
    assert [i.kind for i in reporte.incidents] == ["evidencia_sin_fuente"]
    assert reporte.findings[0].fragments[0].source is None


def test_coincidencia_por_sha_gana_sobre_la_de_file_path():
    por_sha = CaseSource(SHA_T, "real.bin", "texto", "completed")
    por_ruta = CaseSource("", SHA_T, "audio", "completed")
    for orden in ((por_sha, por_ruta), (por_ruta, por_sha)):
        reporte = construir([hallazgo("amenaza", Severity.BAJA, SHA_T, "mensajes 1")], caso(orden))
        assert reporte.findings[0].fragments[0].source is por_sha


def test_caso_no_finalizado_se_reporta_sin_error_y_con_marca_falsa():
    for estado in ("processing", "pending", "estado-nuevo", ""):
        datos = report_to_dict(construir([], caso([], estado)))
        assert datos["finalizado"] is False and datos["status"] == estado


def test_hallazgos_de_otro_caso_no_entran_con_ids_parecidos():
    almacen_h, catalogo, almacen, reloj = armar([hallazgo("amenaza", Severity.BAJA, SHA_T, "mensajes 1")], caso([fuente(SHA_T)]))
    almacen_h.add("c10", [hallazgo("amenaza", Severity.ALTA, SHA_T, "mensajes 2")])
    almacen_h.add("C1", [hallazgo("amenaza", Severity.ALTA, SHA_T, "mensajes 3")])
    reporte = build_report("c1", almacen_h, catalogo, almacen, reloj)
    assert len(reporte.findings) == 1 and reporte.incidents == ()


def test_json_valido_con_nan_prohibido_y_claves_ordenables():
    h = [
        hallazgo("transcripcion", Severity.BAJA, SHA_A, "segmento 0 t=0.00-99999999.99s", "x"),
        hallazgo("amenaza", Severity.ALTA, SHA_T, "mensajes 1,2", "1 2026-11-03T09:00:00+00:00 r1; 2 2026-11-03T09:01:00-06:00 r2"),
        hallazgo("objeto", Severity.MEDIA, SHA_I, "caja 0,0,0,0"),
    ]
    reporte = construir(h, caso([fuente(SHA_T), fuente(SHA_A, "audio"), fuente(SHA_I, "imagen")]))
    texto = json.dumps(report_to_dict(reporte), allow_nan=False, sort_keys=True)
    assert json.loads(texto)["hallazgos"][1]["evidencia"][1]["timestamp_utc"] == "2026-11-03T15:01:00+00:00"


@pytest.mark.parametrize("posicion", ["segmento 0 t=NaN-1s", "segmento 0 t=inf-infs", "caja nan,0,1,1", "mensajes NaN"])
def test_posiciones_con_nan_o_inf_no_llegan_al_json_como_numeros(posicion):
    reporte = construir([hallazgo("x", Severity.BAJA, SHA_T, posicion)], caso([fuente(SHA_T)]))
    json.dumps(report_to_dict(reporte), allow_nan=False)
    assert "posicion_desconocida" in [i.kind for i in reporte.incidents]


def test_extractos_no_ascii_viajan_intactos_en_utf8():
    texto = "áéí ñ 日本語 🙂 «amenaza»\n\ttab \"comillas\" \\ barra"
    h = hallazgo("transcripcion", Severity.BAJA, SHA_A, "segmento 0 t=0.00-1.00s", texto)
    crudo = a_json(construir([h], caso([fuente(SHA_A, "audio")]))).encode("utf-8")
    assert json.loads(crudo.decode("utf-8"))["hallazgos"][0]["evidencia"][0]["extracto"] == texto


def test_la_marca_con_otra_zona_se_serializa_en_utc():
    h = hallazgo("amenaza", Severity.ALTA, SHA_T, "mensajes 1", "1 2026-11-03T20:00:00+05:00 r")
    datos = report_to_dict(construir([h], caso([fuente(SHA_T)])))
    assert datos["linea_temporal"][0]["timestamp_utc"] == "2026-11-03T15:00:00+00:00"


def test_hallazgos_duplicados_se_cuentan_pero_sus_incidencias_no_se_repiten():
    h = hallazgo("amenaza", Severity.ALTA, SHA_T, "mensajes 1")
    reporte = construir([h, h, h], caso([fuente(SHA_T)]))
    assert reporte.categories[0].count == 3
    assert len(reporte.incidents) == 1


def test_entradas_no_se_mutan():
    hs = [hallazgo("amenaza", Severity.ALTA, SHA_T, "mensajes 1", "1 2026-11-03T09:00:00+00:00 r")]
    info = caso([fuente(SHA_T)])
    almacen_h, catalogo, almacen, reloj = armar(hs, info)
    antes = (copy.deepcopy(almacen_h.hallazgos), copy.deepcopy(catalogo.casos), dict(almacen.objetos))
    build_report("c1", almacen_h, catalogo, almacen, reloj)
    assert (almacen_h.hallazgos, catalogo.casos, almacen.objetos) == antes


def test_determinista_y_secciones_independientes_del_orden_de_llegada():
    marca = "2026-11-03T09:00:00+00:00"
    hs = [
        hallazgo("amenaza", Severity.ALTA, SHA_T, "mensajes 3", f"3 {marca} a"),
        hallazgo("amenaza", Severity.ALTA, SHA_T, "mensajes 1", f"1 {marca} b"),
        hallazgo("transcripcion", Severity.BAJA, SHA_A, "segmento 1 t=2.00-3.00s", "z"),
        hallazgo("transcripcion", Severity.BAJA, SHA_A, "segmento 0 t=0.00-1.00s", "y"),
        hallazgo("objeto", Severity.MEDIA, SHA_I, "caja 5,5,9,9"),
    ]
    info = caso([fuente(SHA_T), fuente(SHA_A, "audio"), fuente(SHA_I, "imagen", "failed")])
    primero = report_to_dict(construir(hs, info))
    assert report_to_dict(construir(hs, info)) == primero
    vuelta = report_to_dict(construir(list(reversed(hs)), info))
    for seccion in ("categorias", "linea_temporal", "sin_marca_absoluta", "incidencias"):
        assert vuelta[seccion] == primero[seccion]


def test_el_reporte_no_filtra_rutas_locales_si_el_catalogo_da_ids_de_contenido():
    h = [hallazgo("amenaza", Severity.ALTA, SHA_T, "mensajes 1"), hallazgo("objeto", Severity.BAJA, SHA_I, "caja 1,1,2,2")]
    info = caso([fuente(SHA_T), fuente(SHA_I, "imagen", "failed")])
    texto = a_json(construir(h, info))
    for rastro in ("/home", "/tmp", "/var", "C:\\", "/scratch", "/data"):
        assert rastro not in texto
