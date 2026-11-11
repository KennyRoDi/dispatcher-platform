import os

import pytest

from src.application.ports import KeyUnavailable
from src.application.verify_custody import verify_custody
from src.domain.custody_chain import GENESIS_HASH, seal, make_anchor
from tests.ayudas_custodia import (
    CONTENIDO_A,
    CONTENIDO_B,
    RESULTADO_A,
    RESULTADO_A2,
    PASOS,
    almacen_completo,
    alterar_actor,
    cadena_sellada,
    sha,
)
from tests.dobles import FakeKeyProvider


@pytest.fixture
def llave():
    return os.urandom(32)


def hallazgos(informe):
    return [(v.position, v.kind) for v in informe.violations]


def verificar(llave, lineas, ancla, almacen=None, proveedor=None):
    return verify_custody(lineas, ancla, proveedor or FakeKeyProvider(llave), almacen)


def test_cadena_sana_con_evidencia_pasa(llave):
    lineas, ancla = cadena_sellada(llave)
    informe = verificar(llave, lineas, ancla, almacen_completo())
    assert informe.ok is True
    assert informe.violations == []


def test_log_vacio_pasa(llave):
    assert verificar(llave, [], None, almacen_completo()).ok is True


def test_sin_almacen_no_se_comprueba_la_evidencia(llave):
    lineas, ancla = cadena_sellada(llave)
    assert verificar(llave, lineas, ancla, None).ok is True


def test_una_violacion_deja_ok_en_falso(llave):
    lineas, ancla = cadena_sellada(llave)
    lineas[1] = alterar_actor(lineas[1])
    informe = verificar(llave, lineas, ancla, almacen_completo())
    assert informe.ok is False
    assert informe.violations


def test_alterar_una_entrada_reporta_su_posicion(llave):
    lineas, ancla = cadena_sellada(llave)
    lineas[1] = alterar_actor(lineas[1])
    assert hallazgos(verificar(llave, lineas, ancla, almacen_completo()))[0] == (2, "sello")


def test_borrar_una_linea_reporta_el_enlace_roto(llave):
    lineas, ancla = cadena_sellada(llave)
    del lineas[1]
    assert hallazgos(verificar(llave, lineas, ancla, almacen_completo()))[0] == (2, "enlace")


def test_truncar_el_log_se_detecta_con_la_posicion_del_ancla(llave):
    lineas, ancla = cadena_sellada(llave)
    informe = verificar(llave, lineas[:2], ancla, almacen_completo())
    assert hallazgos(informe) == [(ancla.seq + 1, "truncado")]


def test_ancla_ausente_con_entradas_es_violacion(llave):
    lineas, _ = cadena_sellada(llave)
    assert hallazgos(verificar(llave, lineas, None, almacen_completo())) == [(len(lineas), "ancla")]


def test_recalcular_la_cadena_sin_la_llave_no_pasa(llave):
    atacante = os.urandom(32)
    lineas, ancla = cadena_sellada(atacante)
    assert hallazgos(verificar(llave, lineas, ancla, almacen_completo()))[0] == (1, "sello")


def test_evidencia_ingresada_alterada_reporta_su_entrada_y_el_hash_esperado(llave):
    lineas, ancla = cadena_sellada(llave)
    almacen = almacen_completo()
    almacen.objetos[sha(CONTENIDO_A)] = b"contenido manipulado"
    informe = verificar(llave, lineas, ancla, almacen)
    assert hallazgos(informe) == [(1, "evidencia")]
    assert sha(CONTENIDO_A) in informe.violations[0].detail


def test_resultado_de_transformacion_alterado_reporta_la_entrada_de_la_transformacion(llave):
    lineas, ancla = cadena_sellada(llave)
    almacen = almacen_completo()
    almacen.objetos[sha(RESULTADO_A2)] = b"resumen manipulado"
    informe = verificar(llave, lineas, ancla, almacen)
    assert hallazgos(informe) == [(3, "evidencia")]
    assert sha(RESULTADO_A2) in informe.violations[0].detail


def test_evidencia_ausente_se_detecta(llave):
    lineas, ancla = cadena_sellada(llave)
    almacen = almacen_completo()
    del almacen.objetos[sha(CONTENIDO_B)]
    assert hallazgos(verificar(llave, lineas, ancla, almacen)) == [(4, "evidencia")]


def test_un_resultado_intermedio_no_guardado_se_omite(llave):
    lineas, ancla = cadena_sellada(llave)
    almacen = almacen_completo()
    del almacen.objetos[sha(RESULTADO_A)]
    assert verificar(llave, lineas, ancla, almacen).ok is True


def test_se_reportan_todas_las_evidencias_alteradas(llave):
    lineas, ancla = cadena_sellada(llave)
    almacen = almacen_completo()
    almacen.objetos[sha(CONTENIDO_A)] = b"x"
    almacen.objetos[sha(CONTENIDO_B)] = b"y"
    assert hallazgos(verificar(llave, lineas, ancla, almacen)) == [(1, "evidencia"), (4, "evidencia")]


def test_la_evidencia_se_comprueba_solo_antes_del_eslabon_roto(llave):
    lineas, ancla = cadena_sellada(llave)
    lineas[2] = alterar_actor(lineas[2])
    almacen = almacen_completo()
    almacen.objetos[sha(CONTENIDO_A)] = b"x"
    almacen.objetos[sha(CONTENIDO_B)] = b"y"
    assert set(hallazgos(verificar(llave, lineas, ancla, almacen))) == {(1, "evidencia"), (3, "sello")}


def selladas(llave, pasos):
    previo, entradas = GENESIS_HASH, []
    for seq, (evidencia, operacion, resultado, actor) in enumerate(pasos):
        campos = {
            "ts": "2026-11-03T00:00:00+00:00",
            "evidence_sha256": sha(evidencia),
            "operation": operacion,
            "result_sha256": sha(resultado),
            "actor": actor,
        }
        entradas.append(seal(llave, previo, seq, campos))
        previo = entradas[-1].entry_hash
    ultima = entradas[-1]
    return [e.line() for e in entradas], make_anchor(llave, ultima.seq, ultima.entry_hash)


def test_transformacion_de_evidencia_no_ingresada_viola_el_linaje(llave):
    pasos = [
        (CONTENIDO_A, "ingreso", CONTENIDO_A, "recepcion"),
        (CONTENIDO_B, "transcribir", RESULTADO_A, "worker-1"),
    ]
    lineas, ancla = selladas(llave, pasos)
    assert hallazgos(verificar(llave, lineas, ancla, almacen_completo())) == [(2, "linaje")]


def test_el_linaje_se_comprueba_sin_almacen(llave):
    lineas, ancla = selladas(llave, [(CONTENIDO_B, "transcribir", RESULTADO_A, "worker-1")])
    assert hallazgos(verificar(llave, lineas, ancla, None)) == [(1, "linaje")]


def test_la_transformacion_puede_partir_del_resultado_de_otra_entrada(llave):
    lineas, ancla = cadena_sellada(llave, PASOS)
    assert PASOS[2][0] == RESULTADO_A
    assert verificar(llave, lineas, ancla, None).ok is True


def test_la_transformacion_anterior_al_ingreso_viola_el_linaje(llave):
    pasos = [PASOS[1], PASOS[0]]
    lineas, ancla = selladas(llave, pasos)
    assert hallazgos(verificar(llave, lineas, ancla, None)) == [(1, "linaje")]


def test_falla_cerrado_sin_llave(llave):
    lineas, ancla = cadena_sellada(llave)
    with pytest.raises(KeyUnavailable):
        verificar(llave, lineas, ancla, almacen_completo(), proveedor=FakeKeyProvider())


def test_sin_llave_no_hay_veredicto_ni_con_log_vacio():
    with pytest.raises(KeyUnavailable):
        verify_custody([], None, FakeKeyProvider(), None)
