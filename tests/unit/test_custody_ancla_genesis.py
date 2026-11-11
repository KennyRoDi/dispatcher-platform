import hashlib
import json
import os

import pytest

pytest.importorskip("fcntl", reason="requiere POSIX: fcntl y os.geteuid")

from src.adapters.jsonl_custody_log import CustodyCorrupted, JsonlCustodyLog
from src.domain.custody_chain import GENESIS_HASH, Anchor, make_anchor, seal, verify_chain, verify_tail
from tests.dobles import FakeClock


def sha(texto: str) -> str:
    return hashlib.sha256(texto.encode()).hexdigest()


def cadena(llave: bytes, cantidad: int) -> list[str]:
    lineas, previo = [], GENESIS_HASH
    for i in range(cantidad):
        campos = {"ts": "2026-11-10T12:00:00+00:00", "evidence_sha256": sha(f"e{i}"), "operation": "ingreso",
                  "result_sha256": sha(f"e{i}"), "actor": "x"}
        entrada = seal(llave, previo, i, campos)
        lineas.append(entrada.line())
        previo = entrada.entry_hash
    return lineas


@pytest.fixture
def llave():
    return os.urandom(32)


@pytest.fixture
def ruta(tmp_path):
    return tmp_path / "custodia.jsonl"


def ruta_ancla(ruta):
    return ruta.with_name(ruta.name + ".head")


def abrir(ruta, llave):
    return JsonlCustodyLog(ruta, llave, FakeClock())


def registrar(log, cantidad, desde=0):
    for i in range(desde, desde + cantidad):
        log.record(sha(f"e{i}"), "transcribir", sha(f"r{i}"), "coordinador")


@pytest.mark.parametrize("cantidad", [1, 2, 5])
def test_sin_ancla_un_log_con_entradas_siempre_es_violacion(llave, cantidad):
    lineas = cadena(llave, cantidad)
    assert [v.kind for v in verify_chain(lineas, llave, None)] == ["ancla"]
    assert [v.kind for v in verify_tail(llave, lineas[-2:], None)] == ["ancla"]


def test_un_log_largo_truncado_a_su_primera_entrada_sin_ancla_no_pasa(llave):
    primera = cadena(llave, 5)[:1]
    assert verify_chain(primera, llave, None)


def test_el_log_vacio_sin_ancla_pasa(llave):
    assert verify_chain([], llave, None) == []
    assert verify_tail(llave, [], None) == []


def test_el_ancla_genesis_acepta_log_vacio_y_una_entrada_pero_no_mas(llave):
    genesis = make_anchor(llave, 0, GENESIS_HASH)
    lineas = cadena(llave, 3)
    assert verify_chain([], llave, genesis) == []
    assert verify_chain(lineas[:1], llave, genesis) == []
    assert [v.kind for v in verify_chain(lineas[:2], llave, genesis)] == ["ancla"]
    assert verify_tail(llave, lineas[-2:], genesis)


def test_un_ancla_genesis_con_sello_ajeno_no_pasa(llave):
    falsa = Anchor(0, GENESIS_HASH, make_anchor(os.urandom(32), 0, GENESIS_HASH).mac)
    assert verify_chain([], llave, falsa)


def test_el_primer_anexo_deja_un_ancla_genesis_una_entrada_atras_hasta_el_siguiente(ruta, llave, monkeypatch):
    def caer(self, ancla):
        raise OSError("caída simulada")

    with monkeypatch.context() as parche:
        parche.setattr(JsonlCustodyLog, "_write_anchor", caer)
        with pytest.raises(OSError):
            registrar(abrir(ruta, llave), 1)
    ancla = Anchor(**json.loads(ruta_ancla(ruta).read_text()))
    assert ancla == make_anchor(llave, 0, GENESIS_HASH)
    lineas = ruta.read_bytes().decode().splitlines()
    assert verify_chain(lineas, llave, ancla) == []


def test_tras_una_caida_en_el_primer_anexo_el_log_se_recupera_y_el_ancla_avanza(ruta, llave, monkeypatch):
    with monkeypatch.context() as parche:
        parche.setattr(JsonlCustodyLog, "_write_anchor", lambda self, ancla: (_ for _ in ()).throw(OSError("caída")))
        with pytest.raises(OSError):
            registrar(abrir(ruta, llave), 1)
    registrar(abrir(ruta, llave), 2, desde=1)
    lineas = ruta.read_bytes().decode().splitlines()
    ancla = Anchor(**json.loads(ruta_ancla(ruta).read_text()))
    assert len(lineas) == 3 and ancla.seq == 2
    assert verify_chain(lineas, llave, ancla) == []


def test_un_log_largo_truncado_a_una_entrada_con_el_ancla_borrada_impide_anexar(ruta, llave):
    registrar(abrir(ruta, llave), 4)
    primera = ruta.read_bytes().split(b"\n")[0] + b"\n"
    ruta.write_bytes(primera)
    ruta_ancla(ruta).unlink()
    with pytest.raises(CustodyCorrupted):
        registrar(abrir(ruta, llave), 1, desde=4)
    assert ruta.read_bytes() == primera
    assert not ruta_ancla(ruta).exists()


def test_un_log_vacio_existente_sin_ancla_recibe_el_ancla_genesis_al_primer_anexo(ruta, llave):
    ruta.touch()
    registrar(abrir(ruta, llave), 1)
    lineas = ruta.read_bytes().decode().splitlines()
    assert verify_chain(lineas, llave, Anchor(**json.loads(ruta_ancla(ruta).read_text()))) == []
