import hashlib
import json
import os
import stat
import threading
from datetime import datetime, timedelta

import pytest

pytest.importorskip("fcntl", reason="requiere POSIX: fcntl y os.geteuid")

from src.adapters.jsonl_custody_log import CustodyCorrupted, JsonlCustodyLog
from src.application.ports import CustodyLog
from src.domain.custody_chain import GENESIS_HASH, Anchor, make_anchor, verify_chain
from tests.contratos import comprobar_custody_log
from tests.dobles import FakeClock, FakeCustodyLog


def sha(texto: str) -> str:
    return hashlib.sha256(texto.encode()).hexdigest()


def ruta_ancla(ruta):
    return ruta.with_name(ruta.name + ".head")


def leer_disco(ruta):
    datos = ruta.read_bytes().decode("utf-8") if ruta.exists() else ""
    assert datos == "" or datos.endswith("\n")
    lineas = datos[:-1].split("\n") if datos else []
    ancla = None
    if ruta_ancla(ruta).exists():
        ancla = Anchor(**json.loads(ruta_ancla(ruta).read_text(encoding="utf-8")))
    return lineas, ancla


def escribir_ancla(ruta, ancla: Anchor):
    contenido = {"seq": ancla.seq, "entry_hash": ancla.entry_hash, "mac": ancla.mac}
    ruta_ancla(ruta).write_text(json.dumps(contenido), encoding="utf-8")


def abrir(ruta, llave, reloj=None):
    return JsonlCustodyLog(ruta, llave, reloj or FakeClock())


def registrar(log, cantidad, desde=0, actor="coordinador"):
    for i in range(desde, desde + cantidad):
        log.record(sha(f"e{i}"), "ingreso" if i == 0 else "transcribir", sha(f"r{i}"), actor)


@pytest.fixture
def llave():
    return os.urandom(32)


@pytest.fixture
def ruta(tmp_path):
    return tmp_path / "custodia.jsonl"


def test_el_adaptador_cumple_el_puerto(ruta, llave):
    assert isinstance(abrir(ruta, llave), CustodyLog)


def test_el_doble_sellado_cumple_el_contrato(llave):
    log = FakeCustodyLog(llave)
    comprobar_custody_log(log, log.leer, llave)


def test_el_adaptador_jsonl_cumple_el_contrato(ruta, llave):
    comprobar_custody_log(abrir(ruta, llave), lambda: leer_disco(ruta), llave)


def test_cada_registro_anexa_un_eslabon_sellado_enlazado_al_anterior(ruta, llave):
    reloj = FakeClock()
    log = abrir(ruta, llave, reloj)
    esperado = []
    for i in range(3):
        log.record(sha(f"e{i}"), "ingreso", sha(f"e{i}"), "recepcion")
        esperado.append(reloj.now().isoformat())
        reloj.advance(timedelta(seconds=7))
    lineas, ancla = leer_disco(ruta)
    entradas = [json.loads(linea) for linea in lineas]
    assert [e["seq"] for e in entradas] == [0, 1, 2]
    assert entradas[0]["prev_hash"] == GENESIS_HASH
    assert [e["prev_hash"] for e in entradas[1:]] == [e["entry_hash"] for e in entradas[:-1]]
    assert [e["ts"] for e in entradas] == esperado
    assert verify_chain(lineas, llave, ancla) == []


def test_la_fecha_registrada_es_utc_y_viene_del_reloj_inyectado(ruta, llave):
    abrir(ruta, llave, FakeClock(datetime.fromisoformat("2026-11-10T12:34:56+00:00"))).record(
        sha("e"), "ingreso", sha("e"), "recepcion"
    )
    entrada = json.loads(leer_disco(ruta)[0][0])
    assert datetime.fromisoformat(entrada["ts"]).utcoffset() == timedelta(0)
    assert entrada["ts"] == "2026-11-10T12:34:56+00:00"


def test_una_llave_distinta_no_valida_el_log(ruta, llave):
    registrar(abrir(ruta, llave), 2)
    lineas, ancla = leer_disco(ruta)
    assert verify_chain(lineas, os.urandom(32), ancla)


def test_la_llave_no_se_escribe_en_disco(ruta, llave):
    registrar(abrir(ruta, llave), 2)
    assert llave not in ruta.read_bytes()
    assert llave not in ruta_ancla(ruta).read_bytes()
    assert llave.hex().encode() not in ruta.read_bytes() + ruta_ancla(ruta).read_bytes()


@pytest.mark.parametrize("cantidad", [0, 1, 16, 31, 33, 64])
def test_la_llave_debe_medir_32_bytes(ruta, cantidad):
    with pytest.raises(ValueError):
        abrir(ruta, os.urandom(cantidad))


def test_la_llave_debe_ser_bytes(ruta):
    with pytest.raises((TypeError, ValueError)):
        abrir(ruta, os.urandom(32).hex())


def test_el_ancla_sigue_al_ultimo_eslabon_tras_cada_anexo(ruta, llave):
    log = abrir(ruta, llave)
    for i in range(3):
        registrar(log, 1, desde=i)
        lineas, ancla = leer_disco(ruta)
        ultimo = json.loads(lineas[-1])
        assert ancla == make_anchor(llave, i, ultimo["entry_hash"])


def test_el_ancla_se_escribe_con_archivo_temporal_y_rename_en_el_mismo_directorio(ruta, llave, monkeypatch):
    reemplazos = []
    original = os.replace

    def espia(origen, destino, *args, **kwargs):
        reemplazos.append((os.fspath(origen), os.fspath(destino)))
        return original(origen, destino, *args, **kwargs)

    monkeypatch.setattr(os, "replace", espia)
    registrar(abrir(ruta, llave), 2)
    assert len(reemplazos) == 3
    for origen, destino in reemplazos:
        assert destino == os.fspath(ruta_ancla(ruta))
        assert origen != destino
        assert os.path.dirname(origen) == os.path.dirname(destino)
    assert sorted(p.name for p in ruta.parent.iterdir()) == [ruta.name, ruta_ancla(ruta).name]


def test_cada_anexo_sincroniza_el_log_el_ancla_y_el_directorio(ruta, llave, monkeypatch):
    sincronizados = []
    original = os.fsync

    def espia(fd):
        sincronizados.append(fd)
        return original(fd)

    monkeypatch.setattr(os, "fsync", espia)
    log = abrir(ruta, llave)
    log.record(sha("e"), "ingreso", sha("e"), "recepcion")
    assert len(sincronizados) >= 3
    antes = len(sincronizados)
    log.record(sha("e"), "transcribir", sha("r"), "worker-1")
    assert len(sincronizados) - antes >= 3


def test_el_log_se_abre_en_modo_append_sin_truncar(ruta, llave, monkeypatch):
    aperturas = []
    original = os.open

    def espia(path, flags, *args, **kwargs):
        if os.fspath(path) == os.fspath(ruta):
            aperturas.append(flags)
        return original(path, flags, *args, **kwargs)

    monkeypatch.setattr(os, "open", espia)
    registrar(abrir(ruta, llave), 2)
    assert aperturas
    assert all(flags & os.O_APPEND and not flags & os.O_TRUNC for flags in aperturas)


def test_anexar_no_reescribe_las_lineas_previas(ruta, llave):
    log = abrir(ruta, llave)
    registrar(log, 1)
    inodo, previo = ruta.stat().st_ino, ruta.read_bytes()
    registrar(log, 2, desde=1)
    assert ruta.stat().st_ino == inodo
    assert ruta.read_bytes().startswith(previo)
    assert len(leer_disco(ruta)[0]) == 3


def test_los_archivos_tienen_permisos_0600_aunque_el_umask_sea_laxo(ruta, llave):
    anterior = os.umask(0)
    try:
        registrar(abrir(ruta, llave), 2)
    finally:
        os.umask(anterior)
    assert stat.S_IMODE(ruta.stat().st_mode) == 0o600
    assert stat.S_IMODE(ruta_ancla(ruta).stat().st_mode) == 0o600


def test_reabrir_un_log_existente_continua_la_cadena(ruta, llave):
    registrar(abrir(ruta, llave), 2)
    ultimo = json.loads(leer_disco(ruta)[0][-1])
    registrar(abrir(ruta, llave), 2, desde=2)
    lineas, ancla = leer_disco(ruta)
    entradas = [json.loads(linea) for linea in lineas]
    assert [e["seq"] for e in entradas] == [0, 1, 2, 3]
    assert entradas[2]["prev_hash"] == ultimo["entry_hash"]
    assert verify_chain(lineas, llave, ancla) == []


def test_un_log_vacio_sin_ancla_se_abre_y_empieza_en_el_genesis(ruta, llave):
    ruta.touch()
    registrar(abrir(ruta, llave), 1)
    lineas, ancla = leer_disco(ruta)
    assert json.loads(lineas[0])["prev_hash"] == GENESIS_HASH
    assert verify_chain(lineas, llave, ancla) == []


def snapshot(ruta):
    ancla = ruta_ancla(ruta)
    return ruta.read_bytes() if ruta.exists() else None, ancla.read_bytes() if ancla.exists() else None


def assert_falla_cerrado(ruta, llave):
    antes = snapshot(ruta)
    with pytest.raises(CustodyCorrupted):
        abrir(ruta, llave).record(sha("nuevo"), "transcribir", sha("r"), "coordinador")
    assert snapshot(ruta) == antes


def test_un_eslabon_alterado_impide_anexar(ruta, llave):
    registrar(abrir(ruta, llave), 3)
    ruta.write_bytes(ruta.read_bytes().replace(b"coordinador", b"intruso"))
    assert_falla_cerrado(ruta, llave)


def test_una_ultima_linea_ilegible_impide_anexar(ruta, llave):
    registrar(abrir(ruta, llave), 2)
    ruta.write_bytes(ruta.read_bytes() + b"{no es json\n")
    assert_falla_cerrado(ruta, llave)


def test_una_llave_equivocada_impide_anexar(ruta, llave):
    registrar(abrir(ruta, llave), 2)
    antes = snapshot(ruta)
    with pytest.raises(CustodyCorrupted):
        abrir(ruta, os.urandom(32)).record(sha("n"), "transcribir", sha("r"), "coordinador")
    assert snapshot(ruta) == antes


def test_anexar_sobre_un_log_truncado_se_detecta_por_el_ancla(ruta, llave):
    registrar(abrir(ruta, llave), 3)
    lineas, _ = leer_disco(ruta)
    ruta.write_bytes(("\n".join(lineas[:2]) + "\n").encode())
    assert_falla_cerrado(ruta, llave)


def test_anexar_sobre_un_log_cortado_a_mitad_de_linea_falla_cerrado(ruta, llave):
    registrar(abrir(ruta, llave), 3)
    ruta.write_bytes(ruta.read_bytes()[:-25])
    assert_falla_cerrado(ruta, llave)


def test_un_log_borrado_con_ancla_presente_es_truncamiento(ruta, llave):
    registrar(abrir(ruta, llave), 2)
    ruta.unlink()
    assert_falla_cerrado(ruta, llave)


def test_un_log_con_entradas_y_sin_ancla_falla_cerrado(ruta, llave):
    registrar(abrir(ruta, llave), 2)
    ruta_ancla(ruta).unlink()
    assert_falla_cerrado(ruta, llave)


def test_un_ancla_con_sello_invalido_falla_cerrado(ruta, llave):
    registrar(abrir(ruta, llave), 2)
    _, ancla = leer_disco(ruta)
    escribir_ancla(ruta, Anchor(ancla.seq, ancla.entry_hash, "0" * 64))
    assert_falla_cerrado(ruta, llave)


def test_un_ancla_adelantada_falla_cerrado(ruta, llave):
    registrar(abrir(ruta, llave), 2)
    escribir_ancla(ruta, make_anchor(llave, 5, sha("falso")))
    assert_falla_cerrado(ruta, llave)


def test_un_ancla_que_no_es_json_falla_cerrado(ruta, llave):
    registrar(abrir(ruta, llave), 2)
    ruta_ancla(ruta).write_bytes(b"\x00basura")
    assert_falla_cerrado(ruta, llave)


def test_un_ancla_de_otro_eslabon_falla_cerrado(ruta, llave):
    registrar(abrir(ruta, llave), 2)
    escribir_ancla(ruta, make_anchor(llave, 1, sha("otro")))
    assert_falla_cerrado(ruta, llave)


def test_un_ancla_atrasada_una_entrada_se_tolera_y_se_corrige_al_anexar(ruta, llave):
    registrar(abrir(ruta, llave), 3)
    lineas, _ = leer_disco(ruta)
    escribir_ancla(ruta, make_anchor(llave, 1, json.loads(lineas[1])["entry_hash"]))
    registrar(abrir(ruta, llave), 1, desde=3)
    lineas, ancla = leer_disco(ruta)
    assert len(lineas) == 4
    assert ancla.seq == 3
    assert verify_chain(lineas, llave, ancla) == []


def test_un_ancla_atrasada_dos_entradas_falla_cerrado(ruta, llave):
    registrar(abrir(ruta, llave), 3)
    lineas, _ = leer_disco(ruta)
    escribir_ancla(ruta, make_anchor(llave, 0, json.loads(lineas[0])["entry_hash"]))
    assert_falla_cerrado(ruta, llave)


def test_si_falla_el_rename_del_ancla_el_log_se_puede_reabrir(ruta, llave, monkeypatch):
    log = abrir(ruta, llave)
    registrar(log, 1)
    with monkeypatch.context() as parche:
        parche.setattr(os, "replace", lambda *args, **kwargs: (_ for _ in ()).throw(OSError("disco lleno")))
        with pytest.raises(OSError):
            registrar(log, 1, desde=1)
    registrar(abrir(ruta, llave), 1, desde=2)
    lineas, ancla = leer_disco(ruta)
    assert [json.loads(linea)["seq"] for linea in lineas] == [0, 1, 2]
    assert verify_chain(lineas, llave, ancla) == []


@pytest.mark.parametrize(
    "argumentos",
    [
        (None, "ingreso", sha("x"), "coordinador"),
        (sha("x"), 7, sha("x"), "coordinador"),
        (sha("x"), "ingreso", None, "coordinador"),
        (sha("x"), "ingreso", sha("x"), b"coordinador"),
        (sha("x"), "ingreso", sha("x"), "\ud800"),
    ],
)
def test_un_registro_invalido_se_rechaza_sin_tocar_el_log(ruta, llave, argumentos):
    log = abrir(ruta, llave)
    registrar(log, 1)
    antes = snapshot(ruta)
    with pytest.raises(ValueError):
        log.record(*argumentos)
    assert snapshot(ruta) == antes
    registrar(log, 1, desde=1)
    lineas, ancla = leer_disco(ruta)
    assert verify_chain(lineas, llave, ancla) == []


def test_los_separadores_unicode_de_linea_no_parten_el_log(ruta, llave):
    actor = "a b c\x85d\ne\r\nf\x0bg\x0ch\x1ci"
    log = abrir(ruta, llave)
    log.record(sha("x"), "ingreso", sha("x"), actor)
    registrar(abrir(ruta, llave), 1, desde=1)
    contenido = ruta.read_bytes().decode("utf-8")
    assert contenido.count("\n") == 2
    assert len(contenido.splitlines()) == 2
    for caracter in "  \x85":
        assert caracter not in contenido
    lineas, ancla = leer_disco(ruta)
    assert json.loads(lineas[0])["actor"] == actor
    assert verify_chain(lineas, llave, ancla) == []


def test_los_hilos_de_un_mismo_escritor_no_rompen_la_cadena(ruta, llave):
    log = abrir(ruta, llave)
    hilos, por_hilo = 8, 25
    barrera = threading.Barrier(hilos)

    def trabajar(numero):
        barrera.wait()
        registrar(log, por_hilo, desde=numero * por_hilo, actor=f"hilo-{numero}")

    ejecutar(trabajar, hilos)
    lineas, ancla = leer_disco(ruta)
    assert [json.loads(linea)["seq"] for linea in lineas] == list(range(hilos * por_hilo))
    assert ancla.seq == hilos * por_hilo - 1
    assert verify_chain(lineas, llave, ancla) == []


def test_varios_escritores_sobre_el_mismo_archivo_no_rompen_la_cadena(ruta, llave):
    escritores, por_escritor = 4, 20
    logs = [abrir(ruta, llave) for _ in range(escritores)]
    barrera = threading.Barrier(escritores)

    def trabajar(numero):
        barrera.wait()
        registrar(logs[numero], por_escritor, desde=numero * por_escritor, actor=f"proceso-{numero}")

    ejecutar(trabajar, escritores)
    lineas, ancla = leer_disco(ruta)
    assert [json.loads(linea)["seq"] for linea in lineas] == list(range(escritores * por_escritor))
    assert verify_chain(lineas, llave, ancla) == []


def ejecutar(trabajo, cantidad):
    errores = []

    def envuelto(numero):
        try:
            trabajo(numero)
        except BaseException as error:
            errores.append(error)

    hilos = [threading.Thread(target=envuelto, args=(i,)) for i in range(cantidad)]
    for hilo in hilos:
        hilo.start()
    for hilo in hilos:
        hilo.join()
    assert errores == []
