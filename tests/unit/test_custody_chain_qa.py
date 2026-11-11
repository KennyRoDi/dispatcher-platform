import json
import os
import unicodedata

import pytest

from src.domain.custody_chain import GENESIS_HASH, Anchor, make_anchor, seal, verify_chain
from tests.unit.test_custody_chain import alterar, ancla_de, campos, construir, lineas


@pytest.fixture
def llave() -> bytes:
    return os.urandom(32)


def _reponer(linea: str, **cambios) -> str:
    datos = json.loads(linea)
    datos.update(cambios)
    return json.dumps(datos, sort_keys=True, separators=(",", ":"))


# ---- Hallazgos: cada uno falla hoy y queda como xfail estricto ----


@pytest.mark.xfail(strict=True, reason="QA-1: JSON muy anidado da RecursionError en vez de una violacion 'entrada'")
def test_json_muy_anidado_se_reporta_como_entrada(llave):
    entradas = construir(llave, 3)
    texto = lineas(entradas)
    texto[1] = "[" * 100_000

    resultado = verify_chain(texto, llave, ancla_de(llave, entradas))

    assert (resultado[0].position, resultado[0].kind) == (2, "entrada")


@pytest.mark.xfail(strict=True, reason="QA-2: sustituto aislado (\\ud800) en un campo da UnicodeEncodeError en verify")
@pytest.mark.parametrize("campo", ["actor", "prev_hash", "entry_hash", "operation"])
def test_sustituto_aislado_en_la_linea_se_reporta_sin_excepcion(llave, campo):
    entradas = construir(llave, 3)
    texto = lineas(entradas)
    texto[1] = alterar(texto[1], campo, "\ud800")

    resultado = verify_chain(texto, llave, ancla_de(llave, entradas))

    assert resultado[0].position == 2


@pytest.mark.xfail(strict=True, reason="QA-3: seal acepta valores no str y el log queda imposible de verificar")
@pytest.mark.parametrize("valor", [None, 7])
def test_seal_rechaza_campos_que_verify_no_aceptaria(llave, valor):
    datos = {**campos(0), "actor": valor}

    with pytest.raises((TypeError, ValueError)):
        seal(llave, GENESIS_HASH, 0, datos)


@pytest.mark.xfail(strict=True, reason="QA-4: ensure_ascii=False deja U+2028/U+0085 sin escapar y splitlines() parte la linea")
@pytest.mark.parametrize("separador", [" ", " ", "\x85", "\x0b", "\x0c", "\x1c"])
def test_la_linea_no_se_parte_con_splitlines(llave, separador):
    entrada = seal(llave, GENESIS_HASH, 0, {**campos(0), "actor": f"a{separador}b"})

    assert len(entrada.line().splitlines()) == 1


@pytest.mark.xfail(strict=True, reason="QA-5: claves duplicadas en el JSON se aceptan (gana la ultima); otro lector vera otro actor")
def test_clave_duplicada_en_la_linea_se_rechaza(llave):
    entradas = construir(llave, 2)
    texto = lineas(entradas)
    texto[0] = texto[0].replace('{"actor"', '{"actor":"falso","actor"', 1)
    assert json.loads(texto[0])["actor"] == "worker-0"

    assert verify_chain(texto, llave, ancla_de(llave, entradas))


@pytest.mark.xfail(strict=True, reason="QA-6: llave vacia o corta se acepta en el dominio (solo el adaptador exigira 32 bytes)")
@pytest.mark.parametrize("llave_debil", [b"", b"x"])
def test_llave_vacia_o_corta_se_rechaza(llave_debil):
    with pytest.raises(ValueError):
        seal(llave_debil, GENESIS_HASH, 0, campos(0))


@pytest.mark.xfail(strict=True, reason="QA-7: ancla con seq negativo (con sello valido) indexa desde el final y pasa")
def test_ancla_con_seq_negativo_no_pasa(llave):
    entradas = construir(llave, 4)
    ancla = make_anchor(llave, -1, entradas[-1].entry_hash)

    assert verify_chain(lineas(entradas), llave, ancla)


@pytest.mark.xfail(strict=True, reason="QA-8: se acepta un ancla atrasada cualquier numero de entradas; el SPEC tolera solo una")
def test_ancla_atrasada_mas_de_una_entrada_no_pasa(llave):
    entradas = construir(llave, 6)
    ancla = make_anchor(llave, entradas[3].seq, entradas[3].entry_hash)

    assert verify_chain(lineas(entradas), llave, ancla)


@pytest.mark.xfail(strict=True, reason="QA-9: ancla con mac no str da AttributeError en vez de una violacion 'ancla'")
def test_ancla_malformada_se_reporta_sin_excepcion(llave):
    entradas = construir(llave, 3)

    resultado = verify_chain(lineas(entradas), llave, Anchor(2, entradas[-1].entry_hash, None))

    assert resultado[0].kind == "ancla"


# ---- Intentos que NO rompen la cadena (regresion) ----


def test_reescritura_completa_con_otra_llave_falla_en_la_primera(llave):
    ajena = os.urandom(32)
    entradas = construir(ajena, 5)

    resultado = verify_chain(lineas(entradas), llave, ancla_de(ajena, entradas))

    assert [(v.position, v.kind) for v in resultado] == [(1, "sello")]


def test_ancla_de_otra_cadena_con_la_llave_correcta_no_pasa(llave):
    una = construir(llave, 4)
    otra = _cadena_con_actor(llave, 4, "otro")

    resultado = verify_chain(lineas(una), llave, ancla_de(llave, otra))

    assert resultado[0].kind == "ancla"


def _cadena_con_actor(llave, cantidad, actor):
    entradas, previo = [], GENESIS_HASH
    for i in range(cantidad):
        entradas.append(seal(llave, previo, i, {**campos(i), "actor": actor}))
        previo = entradas[-1].entry_hash
    return entradas


@pytest.mark.parametrize("quitar", [1, 2, 3])
def test_truncar_con_ancla_fresca_se_detecta(llave, quitar):
    entradas = construir(llave, 5)

    resultado = verify_chain(lineas(entradas[:-quitar]), llave, ancla_de(llave, entradas))

    assert (resultado[0].kind, resultado[0].position) == ("truncado", 5)


def test_truncar_y_borrar_ancla_se_detecta_salvo_log_vacio(llave):
    entradas = construir(llave, 3)

    assert verify_chain(lineas(entradas[:2]), llave, None)[0].kind == "ancla"
    assert verify_chain([], llave, None) == []


@pytest.mark.parametrize("seq", [-1, 0, 2, True, False, 1.0, 1.5, float("nan"), float("inf"), 10**30, "enorme", "1", None])
def test_seq_invalido_o_repetido_se_detecta_en_su_posicion(llave, seq):
    entradas = construir(llave, 3)
    texto = lineas(entradas)
    texto[1] = _reponer(texto[1], seq=seq) if seq != "enorme" else '{"seq":' + "9" * 5000 + "}"

    assert verify_chain(texto, llave, ancla_de(llave, entradas))[0].position == 2


@pytest.mark.parametrize("cambio", [{"extra": "x"}, {"seq": None}])
def test_claves_extra_o_tipos_erroneos_se_rechazan(llave, cambio):
    entradas = construir(llave, 2)
    texto = lineas(entradas)
    texto[0] = _reponer(texto[0], **cambio)

    resultado = verify_chain(texto, llave, ancla_de(llave, entradas))

    assert resultado[0].position == 1


@pytest.mark.parametrize("campo", ["actor", "operation", "ts", "evidence_sha256", "result_sha256", "prev_hash", "entry_hash"])
def test_campo_faltante_o_con_tipo_erroneo_se_rechaza(llave, campo):
    entradas = construir(llave, 2)
    for valor in (None, 1, 1.5, True, ["x"], {"a": 1}):
        texto = lineas(entradas)
        texto[0] = _reponer(texto[0], **{campo: valor})
        assert verify_chain(texto, llave, ancla_de(llave, entradas))[0].position == 1
    datos = json.loads(lineas(entradas)[0])
    del datos[campo]
    faltante = json.dumps(datos, sort_keys=True, separators=(",", ":"))
    assert verify_chain([faltante, lineas(entradas)[1]], llave, ancla_de(llave, entradas))[0].position == 1


@pytest.mark.parametrize("prev", ["", "0", "0" * 63, "0" * 65, "0" * 128, "A" * 64, " " + "0" * 63])
def test_prev_hash_de_forma_rara_se_rechaza(llave, prev):
    entradas = construir(llave, 2)
    texto = lineas(entradas)
    texto[0] = _reponer(texto[0], prev_hash=prev)

    assert verify_chain(texto, llave, ancla_de(llave, entradas))[0].position == 1


def test_entry_hash_en_mayusculas_no_pasa(llave):
    entradas = construir(llave, 2)
    texto = lineas(entradas)
    texto[1] = _reponer(texto[1], entry_hash=entradas[1].entry_hash.upper())

    assert verify_chain(texto, llave, ancla_de(llave, entradas))[0].position == 2


def test_nfc_y_nfd_no_son_intercambiables(llave):
    nfc = unicodedata.normalize("NFC", "José")
    nfd = unicodedata.normalize("NFD", "José")
    assert nfc != nfd
    entradas = [seal(llave, GENESIS_HASH, 0, {**campos(0), "actor": nfc})]
    texto = lineas(entradas)
    assert verify_chain(texto, llave, ancla_de(llave, entradas)) == []

    texto[0] = _reponer(texto[0], actor=nfd)

    assert verify_chain(texto, llave, ancla_de(llave, entradas))[0].kind == "sello"


def test_caracteres_de_control_y_saltos_se_escapan_y_verifican(llave):
    actor = "a\nb\rc\x00d\te\x1f "
    entrada = seal(llave, GENESIS_HASH, 0, {**campos(0), "actor": actor})

    assert "\n" not in entrada.line() and "\r" not in entrada.line()
    assert json.loads(entrada.line())["actor"] == actor
    assert verify_chain([entrada.line()], llave, ancla_de(llave, [entrada])) == []


def test_mover_bytes_entre_campos_cambia_el_sello(llave):
    entradas = [seal(llave, GENESIS_HASH, 0, {**campos(0), "operation": "ab", "actor": "cd"})]
    texto = lineas(entradas)
    for operacion, actor in [("abc", "d"), ("a", "bcd"), ("abcd", ""), ("", "abcd")]:
        movida = _reponer(texto[0], operation=operacion, actor=actor)
        assert verify_chain([movida], llave, ancla_de(llave, entradas))[0].kind == "sello"


def test_claves_en_otro_orden_o_con_espacios_siguen_siendo_la_misma_entrada(llave):
    entradas = construir(llave, 2)
    texto = lineas(entradas)
    desordenada = json.dumps(json.loads(texto[0]), indent=2)

    assert verify_chain([desordenada + "\r\n", texto[1] + "\n"], llave, ancla_de(llave, entradas)) == []


def test_bom_en_la_linea_se_rechaza(llave):
    entradas = construir(llave, 2)
    texto = lineas(entradas)
    texto[0] = "﻿" + texto[0]

    assert verify_chain(texto, llave, ancla_de(llave, entradas))[0].position == 1


@pytest.mark.parametrize("vacia", ["", " ", "\n", "null", "[]", "{}", '"x"', "7", "{"])
def test_lineas_vacias_o_de_otro_tipo_son_entrada_invalida(llave, vacia):
    entradas = construir(llave, 2)

    assert verify_chain([vacia, *lineas(entradas)[1:]], llave, ancla_de(llave, entradas))[0].kind == "entrada"


def test_el_ancla_y_la_entrada_no_comparten_mensaje_hmac(llave):
    entradas = construir(llave, 2)
    ancla = make_anchor(llave, 1, entradas[1].entry_hash)

    assert ancla.mac not in {e.entry_hash for e in entradas}


def test_cadena_enorme_se_verifica_sin_acumular_mas_que_los_hashes(llave):
    entradas = construir(llave, 20_000)

    assert verify_chain(lineas(entradas), llave, ancla_de(llave, entradas)) == []
