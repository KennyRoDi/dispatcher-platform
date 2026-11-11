import hashlib
import json
import os
import stat

import pytest

pytest.importorskip("fcntl", reason="requiere POSIX: fcntl y os.geteuid")

from src.adapters.file_key_provider import FileKeyProvider
from src.adapters.jsonl_custody_log import JsonlCustodyLog
from src.application.ports import KeyUnavailable
from src.application.verify_custody import verify_custody
from tests.ayudas_custodia import (
    CONTENIDO_A,
    CONTENIDO_B,
    PASOS,
    RESULTADO_A,
    RESULTADO_A2,
    alterar_actor,
    escribir_lineas,
    escribir_llave,
    escribir_objetos,
    lineas_de,
    log_en_disco,
    registrar_pasos,
    sha,
)
from tests.dobles import FakeClock

pytestmark = pytest.mark.integration


class AlmacenDeDirectorio:
    def __init__(self, directorio):
        self._directorio = directorio

    def exists(self, sha256):
        return (self._directorio / sha256).is_file()

    def open(self, sha256):
        return open(self._directorio / sha256, "rb")

    def put(self, sha256, content, size):
        raise NotImplementedError


@pytest.fixture
def llave():
    return os.urandom(32)


@pytest.fixture
def escenario(tmp_path, llave):
    proveedor = FileKeyProvider(escribir_llave(tmp_path / "custodia.custody-key", llave))
    log = tmp_path / "custodia.jsonl"
    ancla = log_en_disco(log, proveedor.kek())
    objetos = escribir_objetos(tmp_path / "objetos", CONTENIDO_A, CONTENIDO_B, RESULTADO_A, RESULTADO_A2)
    return log, ancla, AlmacenDeDirectorio(objetos), objetos, proveedor


def verificar(log, ancla, almacen, proveedor):
    from src.domain.custody_chain import Anchor

    anexo = Anchor(**json.loads(ancla.read_text(encoding="utf-8"))) if ancla.exists() else None
    return verify_custody(lineas_de(log), anexo, proveedor, almacen)


def hallazgos(informe):
    return [(v.position, v.kind) for v in informe.violations]


def test_log_en_disco_sin_alterar_pasa(escenario):
    log, ancla, almacen, _, proveedor = escenario
    assert verificar(log, ancla, almacen, proveedor).ok is True


def test_el_log_y_el_ancla_quedan_con_modo_0600_tras_reabrir_el_adaptador(escenario):
    log, ancla, *_ = escenario
    assert [stat.S_IMODE(ruta.stat().st_mode) for ruta in (log, ancla)] == [0o600, 0o600]


def test_log_en_disco_manipulado_falla_en_la_linea_alterada(escenario):
    log, ancla, almacen, _, proveedor = escenario
    lineas = lineas_de(log)
    lineas[2] = alterar_actor(lineas[2])
    escribir_lineas(log, lineas)
    assert hallazgos(verificar(log, ancla, almacen, proveedor))[0] == (3, "sello")


def test_log_en_disco_truncado_falla(escenario):
    log, ancla, almacen, _, proveedor = escenario
    escribir_lineas(log, lineas_de(log)[:3])
    assert hallazgos(verificar(log, ancla, almacen, proveedor)) == [(4, "truncado")]


def test_log_en_disco_sin_ancla_falla(escenario):
    log, ancla, almacen, _, proveedor = escenario
    ancla.unlink()
    assert hallazgos(verificar(log, ancla, almacen, proveedor)) == [(4, "ancla")]


def test_evidencia_en_disco_alterada_falla_en_su_entrada(escenario):
    log, ancla, almacen, objetos, proveedor = escenario
    (objetos / sha(CONTENIDO_A)).write_bytes(b"manipulada")
    assert hallazgos(verificar(log, ancla, almacen, proveedor)) == [(1, "evidencia")]


def test_evidencia_en_disco_borrada_falla_en_su_entrada(escenario):
    log, ancla, almacen, objetos, proveedor = escenario
    (objetos / sha(CONTENIDO_B)).unlink()
    assert hallazgos(verificar(log, ancla, almacen, proveedor)) == [(4, "evidencia")]


def test_recalcular_el_archivo_con_sha256_sin_llave_no_pasa(escenario):
    log, ancla, almacen, _, proveedor = escenario
    previo, reescritas = "0" * 64, []
    for entrada in map(json.loads, lineas_de(log)):
        entrada["actor"] = "intruso"
        entrada["prev_hash"] = previo
        contenido = {k: v for k, v in entrada.items() if k != "entry_hash"}
        previo = entrada["entry_hash"] = hashlib.sha256(json.dumps(contenido, sort_keys=True).encode()).hexdigest()
        reescritas.append(json.dumps(entrada, sort_keys=True, separators=(",", ":")))
    escribir_lineas(log, reescritas)
    assert hallazgos(verificar(log, ancla, almacen, proveedor))[0] == (1, "sello")


def test_el_log_reabierto_sigue_verificando_tras_nuevos_registros(escenario, llave):
    log, ancla, almacen, objetos, proveedor = escenario
    nuevo = b"evidencia sintetica C"
    escribir_objetos(objetos, nuevo)
    registrar_pasos(JsonlCustodyLog(log, proveedor.kek(), FakeClock()), [(nuevo, "ingreso", nuevo, "recepcion")])
    assert len(lineas_de(log)) == len(PASOS) + 1
    assert verificar(log, ancla, almacen, proveedor).ok is True


def test_llave_con_permisos_abiertos_no_da_veredicto(escenario, tmp_path, llave):
    log, ancla, almacen, _, _ = escenario
    abierta = FileKeyProvider(escribir_llave(tmp_path / "abierta.custody-key", llave, modo=0o644))
    with pytest.raises(KeyUnavailable):
        verificar(log, ancla, almacen, abierta)
