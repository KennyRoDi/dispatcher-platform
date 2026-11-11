import errno
import hashlib
import json
import multiprocessing
import os
import stat
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone

import pytest

import src.adapters.jsonl_custody_log as modulo
from src.adapters.jsonl_custody_log import CustodyCorrupted, JsonlCustodyLog
from src.domain.custody_chain import Anchor, verify_chain
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


def verifica(ruta, llave):
    lineas, ancla = leer_disco(ruta)
    return verify_chain(lineas, llave, ancla) == []


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


def _escribir_en_proceso(ruta, llave, etiqueta, cantidad, relleno):
    log = JsonlCustodyLog(ruta, llave, FakeClock())
    for i in range(cantidad):
        log.record(sha(f"{etiqueta}{i}"), "transcribir", sha("r"), "x" * relleno)


@pytest.mark.parametrize("relleno", [0, 10_000])
def test_varios_procesos_sobre_el_mismo_log_no_rompen_la_cadena(ruta, llave, relleno):
    procesos, por_proceso = 4, 15
    contexto = multiprocessing.get_context("fork")
    hijos = [
        contexto.Process(target=_escribir_en_proceso, args=(ruta, llave, f"p{n}", por_proceso, relleno))
        for n in range(procesos)
    ]
    for hijo in hijos:
        hijo.start()
    for hijo in hijos:
        hijo.join(60)
    assert [hijo.exitcode for hijo in hijos] == [0] * procesos
    lineas, ancla = leer_disco(ruta)
    assert [json.loads(linea)["seq"] for linea in lineas] == list(range(procesos * por_proceso))
    assert ancla.seq == procesos * por_proceso - 1
    assert verifica(ruta, llave)


def test_un_proceso_muerto_entre_el_anexo_y_el_ancla_se_recupera_al_reabrir(ruta, llave):
    codigo = (
        "import os, sys\n"
        "from src.adapters.jsonl_custody_log import JsonlCustodyLog\n"
        "from tests.dobles import FakeClock\n"
        "log = JsonlCustodyLog(sys.argv[1], bytes.fromhex(sys.argv[2]), FakeClock())\n"
        "log.record('a' * 64, 'ingreso', 'a' * 64, 'x')\n"
        "log._write_anchor = lambda ancla: os._exit(9)\n"
        "log.record('b' * 64, 'transcribir', 'c' * 64, 'x')\n"
    )
    resultado = subprocess.run([sys.executable, "-c", codigo, str(ruta), llave.hex()], cwd=os.getcwd())
    assert resultado.returncode == 9
    assert len(leer_disco(ruta)[0]) == 2
    registrar(abrir(ruta, llave), 1, desde=2)
    assert len(leer_disco(ruta)[0]) == 3
    assert verifica(ruta, llave)


def test_un_temporal_huerfano_del_ancla_no_estorba_y_se_consume(ruta, llave):
    registrar(abrir(ruta, llave), 1)
    temporal = ruta.with_name(ruta_ancla(ruta).name + ".tmp")
    temporal.write_bytes(b"basura" * 100)
    registrar(abrir(ruta, llave), 1, desde=1)
    assert verifica(ruta, llave)
    assert not temporal.exists()


def test_el_ancla_de_otro_log_con_la_misma_llave_falla_cerrado(tmp_path, llave):
    uno, otro = tmp_path / "uno.jsonl", tmp_path / "otro.jsonl"
    log_uno, log_otro = abrir(uno, llave), abrir(otro, llave)
    for i in range(3):
        log_uno.record(sha(f"u{i}"), "transcribir", sha("r"), "x")
        log_otro.record(sha(f"o{i}"), "transcribir", sha("r"), "x")
    ruta_ancla(otro).write_bytes(ruta_ancla(uno).read_bytes())
    antes = otro.read_bytes()
    with pytest.raises(CustodyCorrupted):
        log_otro.record(sha("n"), "transcribir", sha("r"), "x")
    assert otro.read_bytes() == antes


def test_otro_escritor_sin_flock_entre_la_verificacion_y_el_anexo_se_detecta(ruta, llave, monkeypatch):
    log = abrir(ruta, llave)
    registrar(log, 1)
    original = JsonlCustodyLog._read_verified

    def verificar_y_colarse(self, fd):
        lineas = original(self, fd)
        with open(ruta, "ab") as intruso:
            intruso.write(b'{"intruso": 1}\n')
        return lineas

    monkeypatch.setattr(JsonlCustodyLog, "_read_verified", verificar_y_colarse)
    log.record(sha("b"), "transcribir", sha("r"), "x")
    monkeypatch.undo()
    assert not verifica(ruta, llave)
    with pytest.raises(CustodyCorrupted):
        abrir(ruta, llave).record(sha("c"), "transcribir", sha("r"), "x")


def test_una_zona_horaria_distinta_de_utc_se_registra_en_utc(ruta, llave):
    reloj = FakeClock(datetime(2026, 11, 10, 12, 0, tzinfo=timezone(timedelta(hours=5, minutes=30))))
    abrir(ruta, llave, reloj).record(sha("a"), "ingreso", sha("a"), "x")
    assert json.loads(leer_disco(ruta)[0][0])["ts"] == "2026-11-10T06:30:00+00:00"


def test_los_errores_de_anexo_no_filtran_descriptores(ruta, llave):
    log = abrir(ruta, llave)
    registrar(log, 1)
    ruta.write_bytes(ruta.read_bytes() + b"x")
    antes = len(os.listdir("/proc/self/fd"))
    for _ in range(50):
        with pytest.raises(CustodyCorrupted):
            registrar(log, 1, desde=1)
    assert len(os.listdir("/proc/self/fd")) == antes


def test_un_directorio_inexistente_falla_sin_crear_nada(tmp_path, llave):
    with pytest.raises(FileNotFoundError):
        registrar(abrir(tmp_path / "no" / "existe" / "c.jsonl", llave), 1)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignora los permisos")
def test_un_directorio_sin_permiso_de_escritura_falla_sin_dejar_archivos(tmp_path, llave):
    directorio = tmp_path / "ro"
    directorio.mkdir()
    directorio.chmod(0o500)
    try:
        with pytest.raises(PermissionError):
            registrar(abrir(directorio / "c.jsonl", llave), 1)
        assert list(directorio.iterdir()) == []
    finally:
        directorio.chmod(0o700)


@pytest.mark.xfail(strict=True, reason="QA-A1 (media): anexa y luego falla el ancla; con 2 fallos seguidos el log queda atrasado 2 y se bloquea")
def test_un_ancla_que_no_se_puede_escribir_no_deja_el_log_fuera_de_tolerancia(ruta, llave):
    log = abrir(ruta, llave)
    registrar(log, 1)
    obstaculo = ruta.with_name(ruta_ancla(ruta).name + ".tmp")
    obstaculo.mkdir()
    for i in (1, 2):
        with pytest.raises(OSError):
            registrar(log, 1, desde=i)
        assert verifica(ruta, llave), f"tras el fallo {i} el log ya no verifica contra su ancla"
    obstaculo.rmdir()
    registrar(abrir(ruta, llave), 1, desde=3)


@pytest.mark.xfail(strict=True, reason="QA-A2 (media): una caida tras el primer anexo deja 1 entrada sin ancla y el log no se recupera nunca")
def test_una_caida_tras_la_primera_entrada_antes_del_ancla_se_recupera(ruta, llave, monkeypatch):
    def caer(self, ancla):
        raise OSError(errno.EIO, "caida simulada")

    with monkeypatch.context() as parche:
        parche.setattr(JsonlCustodyLog, "_write_anchor", caer)
        with pytest.raises(OSError):
            registrar(abrir(ruta, llave), 1)
    assert len(leer_disco(ruta)[0]) == 1
    registrar(abrir(ruta, llave), 1, desde=1)
    assert verifica(ruta, llave)


@pytest.mark.xfail(strict=True, reason="QA-A3 (media): un write parcial (ENOSPC) deja una cola sin salto de linea; el log queda inservible")
def test_un_write_parcial_no_deja_el_log_inservible(ruta, llave, monkeypatch):
    log = abrir(ruta, llave)
    registrar(log, 1)
    original = os.write
    fallos = []

    def escribir_a_medias(fd, datos):
        if not fallos:
            fallos.append(1)
            original(fd, bytes(datos)[:50])
            raise OSError(errno.ENOSPC, "disco lleno")
        return original(fd, datos)

    with monkeypatch.context() as parche:
        parche.setattr(os, "write", escribir_a_medias)
        with pytest.raises(OSError):
            registrar(log, 1, desde=1)
    registrar(abrir(ruta, llave), 1, desde=2)
    assert verifica(ruta, llave)


@pytest.mark.xfail(strict=True, reason="QA-A4 (media): el temporal del ancla se abre con O_TRUNC siguiendo enlaces: sobrescribe y cambia el modo de un archivo ajeno")
def test_un_temporal_del_ancla_que_es_enlace_no_toca_el_destino(ruta, llave, tmp_path):
    victima = tmp_path / "victima.txt"
    victima.write_text("PRECIOSO")
    victima.chmod(0o644)
    os.symlink(victima, ruta.with_name(ruta_ancla(ruta).name + ".tmp"))
    try:
        registrar(abrir(ruta, llave), 1)
    except OSError:
        pass
    assert victima.read_text() == "PRECIOSO"
    assert stat.S_IMODE(victima.stat().st_mode) == 0o644


@pytest.mark.xfail(strict=True, reason="QA-A5 (baja): un log que es enlace simbolico se sigue y se le hace chmod 0600 al destino")
def test_un_log_que_es_enlace_simbolico_no_se_sigue(ruta, llave, tmp_path):
    destino = tmp_path / "fuera.jsonl"
    destino.write_bytes(b"")
    destino.chmod(0o644)
    os.symlink(destino, ruta)
    try:
        registrar(abrir(ruta, llave), 1)
    except OSError:
        pass
    assert destino.read_bytes() == b""
    assert stat.S_IMODE(destino.stat().st_mode) == 0o644


@pytest.mark.xfail(strict=True, reason="QA-A6 (baja): si el log se reemplaza mientras se espera el flock, el anexo va al inodo viejo y record() responde exito")
def test_un_log_reemplazado_mientras_se_espera_el_candado_no_pierde_el_registro(ruta, llave, monkeypatch):
    registrar(abrir(ruta, llave), 1)
    original = modulo.fcntl.flock
    cambiado = []

    def reemplazar_antes_del_candado(fd, operacion):
        if not cambiado:
            cambiado.append(1)
            os.rename(ruta, ruta.with_name("custodia.viejo"))
            ruta.write_bytes(b"")
        return original(fd, operacion)

    monkeypatch.setattr(modulo.fcntl, "flock", reemplazar_antes_del_candado)
    try:
        registrar(abrir(ruta, llave), 1, desde=1)
    except (CustodyCorrupted, OSError):
        return
    assert ruta.stat().st_size > 0, "record() respondio exito pero el registro quedo en un inodo huerfano"


@pytest.mark.xfail(strict=True, reason="QA-A7 (baja): un reloj sin zona se interpreta como hora local del proceso, no como UTC")
def test_un_reloj_sin_zona_no_da_una_fecha_segun_la_zona_del_proceso(ruta, llave, monkeypatch):
    class RelojIngenuo:
        def now(self):
            return datetime(2026, 11, 10, 12, 0, 0)

    monkeypatch.setenv("TZ", "America/Costa_Rica")
    time.tzset()
    try:
        try:
            JsonlCustodyLog(ruta, llave, RelojIngenuo()).record(sha("a"), "ingreso", sha("a"), "x")
        except ValueError:
            return
        assert json.loads(leer_disco(ruta)[0][0])["ts"] == "2026-11-10T12:00:00+00:00"
    finally:
        monkeypatch.undo()
        time.tzset()


@pytest.mark.xfail(strict=True, reason="QA-A8 (media): record() no valida el formato de los hashes ni la operacion vacia")
@pytest.mark.parametrize(
    "argumentos",
    [
        ("no-es-un-hash", "ingreso", "no-es-un-hash", "x"),
        (sha("a"), "", sha("b"), "x"),
        (sha("a"), "transcribir", "A" * 3, "x"),
    ],
)
def test_un_registro_con_hashes_mal_formados_se_rechaza(ruta, llave, argumentos):
    with pytest.raises(ValueError):
        abrir(ruta, llave).record(*argumentos)


@pytest.mark.xfail(strict=True, reason="QA-A9 (media): una entrada ingreso con result_sha256 distinto de evidence_sha256 se acepta (SPEC: iguales)")
def test_un_ingreso_con_resultado_distinto_de_la_evidencia_se_rechaza(ruta, llave):
    with pytest.raises(ValueError):
        abrir(ruta, llave).record(sha("a"), "ingreso", sha("b"), "x")
