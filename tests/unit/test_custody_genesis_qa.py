import hashlib
import json
import multiprocessing
import os
import subprocess
import sys
import textwrap

import pytest

pytest.importorskip("fcntl", reason="requiere POSIX: fcntl y os.geteuid")

from src.adapters.jsonl_custody_log import CustodyCorrupted, JsonlCustodyLog
from src.domain.custody_chain import GENESIS_HASH, Anchor, make_anchor, verify_chain
from tests.dobles import FakeClock


def sha(texto: str) -> str:
    return hashlib.sha256(texto.encode()).hexdigest()


def ruta_ancla(ruta):
    return ruta.with_name(ruta.name + ".head")


def leer_disco(ruta):
    datos = ruta.read_bytes().decode("utf-8")
    lineas = datos[:-1].split("\n") if datos else []
    ancla = None
    if ruta_ancla(ruta).exists():
        ancla = Anchor(**json.loads(ruta_ancla(ruta).read_text(encoding="utf-8")))
    return lineas, ancla


def abrir(ruta, llave):
    return JsonlCustodyLog(ruta, llave, FakeClock())


def registrar(log, cantidad, desde=0):
    for i in range(desde, desde + cantidad):
        log.record(sha(f"e{i}"), "ingreso", sha(f"e{i}"), "coordinador")


@pytest.fixture
def llave():
    return os.urandom(32)


@pytest.fixture
def ruta(tmp_path):
    return tmp_path / "custodia.jsonl"


@pytest.mark.xfail(strict=True, reason="QA F-29 p2 (baja, SUP-31 ampliado): el ancla génesis es constante por llave; "
                   "una copia de la primera ancla oculta el truncado de cualquier log a 0 o 1 entrada")
@pytest.mark.parametrize("conservar", [0, 1])
def test_un_log_largo_truncado_con_el_ancla_genesis_guardada_se_detecta(llave, ruta, conservar):
    registrar(abrir(ruta, llave), 5)
    genesis_guardada = make_anchor(llave, 0, GENESIS_HASH)
    lineas, _ = leer_disco(ruta)
    assert verify_chain(lineas[:conservar], llave, genesis_guardada) != []


@pytest.mark.xfail(strict=True, reason="QA F-29 p2 (baja): con el log ausente y el ancla ilegible o con sello falso, "
                   "el mensaje dice «hay un ancla con entradas»")
@pytest.mark.parametrize("contenido", [b"basura", None])
def test_log_ausente_con_ancla_invalida_no_dice_que_hay_entradas(llave, ruta, contenido):
    if contenido is None:
        contenido = json.dumps({"seq": 0, "entry_hash": GENESIS_HASH, "mac": "0" * 64}).encode()
    ruta_ancla(ruta).write_bytes(contenido)
    with pytest.raises(CustodyCorrupted) as error:
        registrar(abrir(ruta, llave), 1)
    assert "con entradas" not in str(error.value)


@pytest.mark.parametrize("conservar", [0, 1])
def test_ancla_genesis_con_log_de_dos_o_mas_oculta_solo_hasta_una_entrada(llave, ruta, conservar):
    registrar(abrir(ruta, llave), 3)
    lineas, _ = leer_disco(ruta)
    genesis = make_anchor(llave, 0, GENESIS_HASH)
    assert verify_chain(lineas[:conservar], llave, genesis) == []
    assert [v.kind for v in verify_chain(lineas[:2], llave, genesis)] == ["ancla"]


def test_ancla_genesis_forjada_sin_la_llave_se_rechaza(llave, ruta):
    registrar(abrir(ruta, llave), 3)
    lineas, _ = leer_disco(ruta)
    ajena = make_anchor(os.urandom(32), 0, GENESIS_HASH)
    sin_sello = Anchor(0, GENESIS_HASH, "0" * 64)
    for ancla in (ajena, sin_sello):
        assert [v.kind for v in verify_chain(lineas[:1], llave, ancla)] == ["ancla"]
        assert [v.kind for v in verify_chain([], llave, ancla)] == ["ancla"]


def test_log_vacio_preexistente_sin_ancla_se_adopta_y_queda_verificable(llave, ruta):
    ruta.write_bytes(b"")
    registrar(abrir(ruta, llave), 2)
    lineas, ancla = leer_disco(ruta)
    assert len(lineas) == 2 and verify_chain(lineas, llave, ancla) == []


def test_borrar_log_y_ancla_juntos_reinicia_sin_aviso_limite_conocido(llave, ruta):
    registrar(abrir(ruta, llave), 3)
    ruta.unlink()
    ruta_ancla(ruta).unlink()
    registrar(abrir(ruta, llave), 1)
    lineas, ancla = leer_disco(ruta)
    assert len(lineas) == 1 and verify_chain(lineas, llave, ancla) == []


def test_borrar_solo_el_log_o_solo_el_ancla_se_detecta(llave, ruta):
    registrar(abrir(ruta, llave), 3)
    respaldo = ruta.read_bytes()
    ruta.unlink()
    with pytest.raises(CustodyCorrupted):
        registrar(abrir(ruta, llave), 1)
    ruta.write_bytes(respaldo)
    ruta_ancla(ruta).unlink()
    with pytest.raises(CustodyCorrupted):
        registrar(abrir(ruta, llave), 1)


def _escritor(ruta, llave, indice, barrera, errores):
    barrera.wait()
    try:
        registrar(abrir(ruta, llave), 1, desde=indice)
    except BaseException as error:
        errores.put(repr(error))


@pytest.mark.parametrize("modo", ["procesos", "hilos"])
def test_ocho_escritores_creando_el_log_a_la_vez_no_fallan(tmp_path, modo):
    import queue
    import threading

    for corrida in range(15):
        ruta = tmp_path / f"c{corrida}.jsonl"
        llave = os.urandom(32)
        if modo == "procesos":
            barrera, errores = multiprocessing.Barrier(8), multiprocessing.Queue()
            trabajos = [multiprocessing.Process(target=_escritor, args=(ruta, llave, i, barrera, errores)) for i in range(8)]
        else:
            barrera, errores = threading.Barrier(8), queue.Queue()
            trabajos = [threading.Thread(target=_escritor, args=(ruta, llave, i, barrera, errores)) for i in range(8)]
        for trabajo in trabajos:
            trabajo.start()
        for trabajo in trabajos:
            trabajo.join()
        assert errores.empty()
        lineas, ancla = leer_disco(ruta)
        assert len(lineas) == 8 and verify_chain(lineas, llave, ancla) == []


CAIDA = textwrap.dedent("""
    import hashlib, os, sys
    import src.adapters.jsonl_custody_log as modulo
    from src.adapters.jsonl_custody_log import JsonlCustodyLog
    from tests.dobles import FakeClock
    donde, ruta, llave = sys.argv[1], sys.argv[2], bytes.fromhex(sys.argv[3])
    if donde == "antes_de_genesis":
        JsonlCustodyLog._catch_up_anchor = lambda self, last: os._exit(9)
    elif donde == "antes_del_primer_anexo":
        modulo._append = lambda *args: os._exit(9)
    elif donde == "antes_del_ancla_del_anexo":
        JsonlCustodyLog._write_anchor = lambda self, anchor: os._exit(9)
    elif donde == "durante_el_rename_de_genesis":
        os.replace = lambda origen, destino: os._exit(9)
    h = hashlib.sha256(b"a").hexdigest()
    JsonlCustodyLog(ruta, llave, FakeClock()).record(h, "ingreso", h, "x")
""")


@pytest.mark.parametrize("donde", ["antes_de_genesis", "antes_del_primer_anexo", "antes_del_ancla_del_anexo",
                                   "durante_el_rename_de_genesis"])
def test_una_caida_al_crear_el_log_se_recupera_sin_bloquear(llave, ruta, donde):
    resultado = subprocess.run([sys.executable, "-c", CAIDA, donde, str(ruta), llave.hex()],
                               env={**os.environ, "PYTHONPATH": os.getcwd()})
    assert resultado.returncode == 9
    lineas, ancla = leer_disco(ruta)
    assert verify_chain(lineas, llave, ancla) == []
    registrar(abrir(ruta, llave), 2, desde=10)
    lineas, ancla = leer_disco(ruta)
    assert verify_chain(lineas, llave, ancla) == []
    assert len(lineas) == 2 + (donde == "antes_del_ancla_del_anexo")
