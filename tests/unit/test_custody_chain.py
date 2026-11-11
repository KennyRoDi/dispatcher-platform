import hashlib
import hmac
import json
import os

import pytest

from src.domain import custody_chain
from src.domain.custody_chain import GENESIS_HASH, Anchor, make_anchor, seal, verify_chain

OPERACIONES = ["ingreso", "transcribir", "extraer_texto", "detectar_objetos", "resumir"]


def sha(texto: str) -> str:
    return hashlib.sha256(texto.encode()).hexdigest()


def campos(i: int, operacion: str = "") -> dict:
    return {
        "ts": f"2026-11-10T12:00:{i:02d}+00:00",
        "evidence_sha256": sha(f"evidencia-{i}"),
        "operation": operacion or OPERACIONES[i % len(OPERACIONES)],
        "result_sha256": sha(f"resultado-{i}"),
        "actor": f"worker-{i % 3}",
    }


def construir(llave: bytes, cantidad: int):
    entradas, previo = [], GENESIS_HASH
    for i in range(cantidad):
        entrada = seal(llave, previo, i, campos(i))
        entradas.append(entrada)
        previo = entrada.entry_hash
    return entradas


def lineas(entradas) -> list[str]:
    return [e.line() for e in entradas]


def ancla_de(llave: bytes, entradas) -> Anchor:
    return make_anchor(llave, entradas[-1].seq, entradas[-1].entry_hash)


def alterar(linea: str, campo: str, valor) -> str:
    datos = json.loads(linea)
    datos[campo] = valor
    return json.dumps(datos, sort_keys=True, separators=(",", ":"))


@pytest.fixture
def llave() -> bytes:
    return os.urandom(32)


def test_cada_entrada_enlaza_a_la_anterior(llave):
    entradas = construir(llave, 4)

    assert entradas[0].prev_hash == GENESIS_HASH == "0" * 64
    for anterior, actual in zip(entradas, entradas[1:]):
        assert actual.prev_hash == anterior.entry_hash
    assert [e.seq for e in entradas] == [0, 1, 2, 3]


def test_entry_hash_es_hmac_sha256_del_hash_previo_y_el_contenido_canonico(llave):
    entrada = seal(llave, GENESIS_HASH, 0, campos(0))

    contenido = {"seq": 0, **campos(0)}
    canonico = json.dumps(contenido, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    esperado = hmac.new(llave, GENESIS_HASH.encode() + canonico.encode("utf-8"), hashlib.sha256).hexdigest()
    assert entrada.entry_hash == esperado
    assert entrada.entry_hash != hashlib.sha256(canonico.encode("utf-8")).hexdigest()


def test_serializacion_canonica_no_depende_del_orden_de_los_campos(llave):
    ordenados = campos(1)
    invertidos = dict(reversed(list(ordenados.items())))

    uno = seal(llave, GENESIS_HASH, 1, ordenados)
    otro = seal(llave, GENESIS_HASH, 1, invertidos)

    assert uno.line() == otro.line()
    assert uno.entry_hash == otro.entry_hash


def test_la_linea_es_json_compacto_ordenado_utf8_sin_salto_de_linea(llave):
    datos = {**campos(0), "actor": "analizador-ñandú-é"}
    linea = seal(llave, GENESIS_HASH, 0, datos).line()

    assert "\n" not in linea
    assert ", " not in linea and ": " not in linea
    assert linea == json.dumps(json.loads(linea), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    assert "ñandú" in linea
    linea.encode("utf-8")
    assert set(json.loads(linea)) == {"seq", "ts", "evidence_sha256", "operation", "result_sha256", "actor", "prev_hash", "entry_hash"}


@pytest.mark.parametrize("cantidad", [0, 1, 5])
def test_cadena_sin_alteraciones_pasa(llave, cantidad):
    entradas = construir(llave, cantidad)
    ancla = ancla_de(llave, entradas) if entradas else None

    assert verify_chain(lineas(entradas), llave, ancla) == []


@pytest.mark.parametrize("campo", ["seq", "ts", "evidence_sha256", "operation", "result_sha256", "actor", "prev_hash", "entry_hash"])
@pytest.mark.parametrize("posicion", [1, 3, 5])
def test_alterar_entrada_detecta_posicion(llave, campo, posicion):
    entradas = construir(llave, 5)
    texto = lineas(entradas)
    original = json.loads(texto[posicion - 1])[campo]
    nuevo = original + 1 if campo == "seq" else "alterado" + str(original)[8:]
    texto[posicion - 1] = alterar(texto[posicion - 1], campo, nuevo)

    violaciones = verify_chain(texto, llave, ancla_de(llave, entradas))

    assert violaciones[0].position == posicion
    assert violaciones[0].kind in {"sello", "enlace"}


def test_linea_que_no_es_json_se_reporta_como_entrada(llave):
    entradas = construir(llave, 3)
    texto = lineas(entradas)
    texto[1] = "{no es json"

    violaciones = verify_chain(texto, llave, ancla_de(llave, entradas))

    assert (violaciones[0].position, violaciones[0].kind) == (2, "entrada")


def test_borrar_una_entrada_intermedia_detecta_el_enlace_roto(llave):
    entradas = construir(llave, 5)
    texto = lineas(entradas)
    del texto[2]

    violaciones = verify_chain(texto, llave, ancla_de(llave, entradas))

    assert (violaciones[0].position, violaciones[0].kind) == (3, "enlace")


def test_borrar_la_primera_entrada_se_detecta_en_la_posicion_1(llave):
    entradas = construir(llave, 3)

    violaciones = verify_chain(lineas(entradas)[1:], llave, ancla_de(llave, entradas))

    assert (violaciones[0].position, violaciones[0].kind) == (1, "enlace")


def test_insertar_o_duplicar_una_entrada_se_detecta(llave):
    entradas = construir(llave, 4)
    texto = lineas(entradas)
    texto.insert(2, texto[1])

    violaciones = verify_chain(texto, llave, ancla_de(llave, entradas))

    assert (violaciones[0].position, violaciones[0].kind) == (3, "enlace")


def test_reordenar_entradas_se_detecta_en_la_primera_fuera_de_lugar(llave):
    entradas = construir(llave, 4)
    texto = lineas(entradas)
    texto[1], texto[2] = texto[2], texto[1]

    violaciones = verify_chain(texto, llave, ancla_de(llave, entradas))

    assert (violaciones[0].position, violaciones[0].kind) == (2, "enlace")


@pytest.mark.parametrize("quitar", [1, 2, 4])
def test_truncar_la_cola_se_detecta_con_el_ancla(llave, quitar):
    entradas = construir(llave, 5)
    ancla = ancla_de(llave, entradas)

    violaciones = verify_chain(lineas(entradas)[:-quitar], llave, ancla)

    assert [v.kind for v in violaciones] == ["truncado"]
    assert violaciones[0].position == ancla.seq + 1 == 5


def test_truncar_todo_el_log_con_ancla_presente_es_truncado(llave):
    entradas = construir(llave, 3)

    violaciones = verify_chain([], llave, ancla_de(llave, entradas))

    assert [v.kind for v in violaciones] == ["truncado"]


def test_log_truncado_sin_ancla_se_reporta_ancla_ausente(llave):
    entradas = construir(llave, 4)

    violaciones = verify_chain(lineas(entradas)[:-1], llave, None)

    assert [v.kind for v in violaciones] == ["ancla"]


def test_ancla_atrasada_no_falla_y_adelantada_si(llave):
    entradas = construir(llave, 4)
    atrasada = make_anchor(llave, entradas[2].seq, entradas[2].entry_hash)

    assert verify_chain(lineas(entradas), llave, atrasada) == []
    assert verify_chain(lineas(entradas[:2]), llave, atrasada)[0].kind == "truncado"


def test_ancla_con_sello_invalido_o_de_otra_llave_falla(llave):
    entradas = construir(llave, 3)
    ancla = ancla_de(llave, entradas)
    falsa = Anchor(seq=ancla.seq, entry_hash=ancla.entry_hash, mac=sha("falso"))
    ajena = ancla_de(os.urandom(32), entradas)

    for invalida in (falsa, ajena):
        assert [v.kind for v in verify_chain(lineas(entradas), llave, invalida)] == ["ancla"]


def test_ancla_con_el_mismo_seq_y_otro_hash_falla(llave):
    entradas = construir(llave, 3)
    ancla = make_anchor(llave, entradas[-1].seq, sha("otro eslabon"))

    violaciones = verify_chain(lineas(entradas), llave, ancla)

    assert [v.kind for v in violaciones] == ["ancla"]


def test_recalcular_cadena_con_sha256_sin_llave_no_pasa(llave):
    entradas = construir(llave, 4)
    texto, previo = [], GENESIS_HASH
    for i in range(4):
        contenido = {"seq": i, **campos(i), "operation": "borrado" if i == 1 else campos(i)["operation"]}
        canonico = json.dumps(contenido, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        sello = hashlib.sha256(previo.encode() + canonico.encode("utf-8")).hexdigest()
        texto.append(json.dumps({**contenido, "prev_hash": previo, "entry_hash": sello}, sort_keys=True, separators=(",", ":")))
        previo = sello

    violaciones = verify_chain(texto, llave, ancla_de(llave, entradas))

    assert (violaciones[0].position, violaciones[0].kind) == (1, "sello")


def test_un_hash_sin_llave_si_seria_forjable_y_el_hmac_no(llave):
    # Justifica HMAC (AD-35): con SHA-256 solo, quien altera recalcula los eslabones y nada lo delata.
    def sello_sin_llave(previo: str, contenido: dict) -> str:
        canonico = json.dumps(contenido, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return hashlib.sha256(previo.encode() + canonico.encode("utf-8")).hexdigest()

    contenido = {"seq": 0, **campos(0)}
    original = sello_sin_llave(GENESIS_HASH, contenido)
    forjado = sello_sin_llave(GENESIS_HASH, {**contenido, "actor": "otro"})
    assert original != forjado

    con_llave = seal(llave, GENESIS_HASH, 0, campos(0)).entry_hash
    sin_llave = seal(os.urandom(32), GENESIS_HASH, 0, campos(0)).entry_hash
    assert con_llave != sin_llave != original


def test_llave_distinta_falla_en_la_primera_entrada(llave):
    entradas = construir(llave, 3)

    violaciones = verify_chain(lineas(entradas), os.urandom(32), None)

    assert (violaciones[0].position, violaciones[0].kind) == (1, "sello")


def test_la_comparacion_de_sellos_es_en_tiempo_constante(llave, monkeypatch):
    llamadas = []
    original = hmac.compare_digest

    def espia(a, b):
        llamadas.append((a, b))
        return original(a, b)

    monkeypatch.setattr(hmac, "compare_digest", espia)
    entradas = construir(llave, 3)

    verify_chain(lineas(entradas), llave, ancla_de(llave, entradas))

    assert len(llamadas) >= 3


def test_el_dominio_no_compara_sellos_con_igualdad():
    fuente = custody_chain.__file__
    with open(fuente, encoding="utf-8") as archivo:
        codigo = archivo.read()

    assert "compare_digest" in codigo
    assert "entry_hash ==" not in codigo and "mac ==" not in codigo
