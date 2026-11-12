import base64
import hashlib
import io
import logging
import os
import re
import subprocess
import threading
from pathlib import Path

import pytest

pytest.importorskip("fcntl", reason="requiere POSIX: fcntl y os.geteuid")

from src.adapters.envelope_cipher import EnvelopeCipher
from src.adapters.file_key_provider import FileKeyProvider
from src.application.ports import DecryptionError, KeyUnavailable
from tests.contratos import comprobar_key_provider, comprobar_key_provider_sin_kek
from tests.dobles import FakeKeyProvider

RAIZ = Path(__file__).resolve().parents[2]
MODOS_PERMITIDOS = (0o400, 0o600)
MODOS_CON_GRUPO_U_OTROS = (0o640, 0o644, 0o604, 0o660, 0o666, 0o602, 0o620, 0o410, 0o401)


def _escribir(ruta: Path, contenido: bytes, modo: int = 0o400) -> Path:
    ruta.write_bytes(contenido)
    ruta.chmod(modo)
    return ruta


def _kek_en_archivo(tmp_path: Path, modo: int = 0o400, nombre: str = "nodo.kek") -> tuple[Path, bytes]:
    kek = os.urandom(32)
    return _escribir(tmp_path / nombre, kek, modo), kek


def _desde_entorno(entorno: dict[str, str]) -> bytes:
    return FileKeyProvider.from_env(entorno).kek()


def _formas(kek: bytes) -> list[str]:
    return [kek.hex(), base64.b64encode(kek).decode(), repr(kek), str(kek), base64.urlsafe_b64encode(kek).decode()]


def _sin_kek_en(texto: str, kek: bytes) -> bool:
    return not any(forma in texto for forma in _formas(kek))


@pytest.mark.parametrize("modo", MODOS_PERMITIDOS)
def test_lee_la_kek_de_un_archivo_con_permisos_de_propietario(tmp_path, modo):
    ruta, kek = _kek_en_archivo(tmp_path, modo)
    assert FileKeyProvider(ruta).kek() == kek


@pytest.mark.parametrize("modo", MODOS_CON_GRUPO_U_OTROS)
def test_kek_legible_por_grupo_u_otros_se_rechaza(tmp_path, modo):
    ruta, kek = _kek_en_archivo(tmp_path, modo)
    with pytest.raises(KeyUnavailable) as info:
        FileKeyProvider(ruta).kek()
    assert _sin_kek_en(str(info.value), kek)


def test_archivo_ausente_falla_cerrado(tmp_path):
    with pytest.raises(KeyUnavailable):
        FileKeyProvider(tmp_path / "no-existe.kek").kek()


def test_archivo_vacio_falla_cerrado(tmp_path):
    with pytest.raises(KeyUnavailable):
        FileKeyProvider(_escribir(tmp_path / "vacia.kek", b"")).kek()


@pytest.mark.parametrize("largo", [1, 16, 31, 33, 64, 4096, 1_000_000])
def test_kek_de_largo_distinto_de_32_se_rechaza(tmp_path, largo):
    contenido = os.urandom(largo)
    ruta = _escribir(tmp_path / "mala.kek", contenido)
    with pytest.raises(KeyUnavailable) as info:
        FileKeyProvider(ruta).kek()
    if largo >= 16:
        assert _sin_kek_en(str(info.value), contenido[:32])


def test_salto_de_linea_final_cuenta_como_byte_y_se_rechaza(tmp_path):
    ruta = _escribir(tmp_path / "texto.kek", os.urandom(32) + b"\n")
    with pytest.raises(KeyUnavailable):
        FileKeyProvider(ruta).kek()


def test_el_archivo_se_lee_en_binario_sin_interpretar_el_contenido(tmp_path):
    kek = bytes(range(32))
    assert FileKeyProvider(_escribir(tmp_path / "bytes.kek", kek)).kek() == kek
    con_nul_y_crlf = b"\x00\r\n" * 10 + b"\xff\xfe"
    assert len(con_nul_y_crlf) == 32
    assert FileKeyProvider(_escribir(tmp_path / "raro.kek", con_nul_y_crlf)).kek() == con_nul_y_crlf


def test_un_directorio_no_es_una_kek(tmp_path):
    directorio = tmp_path / "carpeta.kek"
    directorio.mkdir(mode=0o700)
    with pytest.raises(KeyUnavailable):
        FileKeyProvider(directorio).kek()


def test_un_fifo_no_bloquea_y_se_rechaza(tmp_path):
    fifo = tmp_path / "tuberia.kek"
    os.mkfifo(fifo, 0o600)
    resultado: list[BaseException | bytes] = []

    def intentar():
        try:
            resultado.append(FileKeyProvider(fifo).kek())
        except BaseException as error:
            resultado.append(error)

    hilo = threading.Thread(target=intentar, daemon=True)
    hilo.start()
    hilo.join(timeout=5)
    assert not hilo.is_alive(), "leer un FIFO sin escritor bloqueó al proveedor"
    assert len(resultado) == 1 and isinstance(resultado[0], KeyUnavailable)


def test_enlace_simbolico_a_un_archivo_regular_valido_se_sigue(tmp_path):
    ruta, kek = _kek_en_archivo(tmp_path)
    enlace = tmp_path / "enlace.kek"
    enlace.symlink_to(ruta)
    assert FileKeyProvider(enlace).kek() == kek


def test_enlace_simbolico_hacia_un_destino_legible_por_otros_se_rechaza(tmp_path):
    ruta, _ = _kek_en_archivo(tmp_path, 0o644)
    enlace = tmp_path / "enlace.kek"
    enlace.symlink_to(ruta)
    with pytest.raises(KeyUnavailable):
        FileKeyProvider(enlace).kek()


def test_enlace_simbolico_roto_o_en_ciclo_falla_cerrado(tmp_path):
    roto = tmp_path / "roto.kek"
    roto.symlink_to(tmp_path / "no-existe")
    ciclo_a, ciclo_b = tmp_path / "a.kek", tmp_path / "b.kek"
    ciclo_a.symlink_to(ciclo_b)
    ciclo_b.symlink_to(ciclo_a)
    for enlace in (roto, ciclo_a):
        with pytest.raises(KeyUnavailable):
            FileKeyProvider(enlace).kek()


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignora los permisos de lectura")
def test_archivo_sin_permiso_de_lectura_falla_cerrado(tmp_path):
    ruta, _ = _kek_en_archivo(tmp_path, 0o000)
    with pytest.raises(KeyUnavailable):
        FileKeyProvider(ruta).kek()


def test_acepta_ruta_como_cadena(tmp_path):
    ruta, kek = _kek_en_archivo(tmp_path)
    assert FileKeyProvider(str(ruta)).kek() == kek


def test_from_env_lee_kek_file(tmp_path):
    ruta, kek = _kek_en_archivo(tmp_path)
    assert _desde_entorno({"KEK_FILE": str(ruta)}) == kek


def test_from_env_sin_kek_file_ni_kek_falla_cerrado():
    with pytest.raises(KeyUnavailable):
        _desde_entorno({})


@pytest.mark.parametrize("entorno", [{"KEK_FILE": ""}, {"KEK": ""}, {"KEK_FILE": "", "KEK": ""}, {"KEK_FILE": "   "}])
def test_from_env_con_valores_vacios_falla_cerrado(entorno):
    with pytest.raises(KeyUnavailable):
        _desde_entorno(entorno)


def test_from_env_usa_os_environ_por_omisión(tmp_path, monkeypatch):
    ruta, kek = _kek_en_archivo(tmp_path)
    monkeypatch.setenv("KEK_FILE", str(ruta))
    monkeypatch.delenv("KEK", raising=False)
    assert FileKeyProvider.from_env().kek() == kek
    monkeypatch.delenv("KEK_FILE")
    with pytest.raises(KeyUnavailable):
        FileKeyProvider.from_env().kek()


def test_from_env_kek_en_base64_solo_para_desarrollo():
    kek = os.urandom(32)
    assert _desde_entorno({"KEK": base64.b64encode(kek).decode()}) == kek


@pytest.mark.parametrize("valor", ["no es base64 !!!", "====", "AAAA", base64.b64encode(os.urandom(31)).decode(), base64.b64encode(os.urandom(33)).decode(), base64.b64encode(os.urandom(64)).decode()])
def test_from_env_kek_invalida_falla_cerrado(valor):
    with pytest.raises(KeyUnavailable) as info:
        _desde_entorno({"KEK": valor})
    assert valor not in str(info.value)


def test_kek_file_tiene_prioridad_sobre_la_variable_kek(tmp_path):
    ruta, kek_archivo = _kek_en_archivo(tmp_path)
    kek_variable = os.urandom(32)
    entorno = {"KEK_FILE": str(ruta), "KEK": base64.b64encode(kek_variable).decode()}
    assert _desde_entorno(entorno) == kek_archivo


@pytest.mark.parametrize("preparar", ["ausente", "permisos", "largo"])
def test_kek_file_defectuoso_no_cae_a_la_variable_kek(tmp_path, preparar):
    ruta = tmp_path / "nodo.kek"
    if preparar == "permisos":
        _escribir(ruta, os.urandom(32), 0o644)
    elif preparar == "largo":
        _escribir(ruta, os.urandom(10))
    variable = base64.b64encode(os.urandom(32)).decode()
    with pytest.raises(KeyUnavailable):
        _desde_entorno({"KEK_FILE": str(ruta), "KEK": variable})


def test_repr_y_str_del_proveedor_no_muestran_la_kek(tmp_path):
    ruta, kek = _kek_en_archivo(tmp_path)
    variable = os.urandom(32)
    proveedores = [
        FileKeyProvider(ruta),
        FileKeyProvider.from_env({"KEK_FILE": str(ruta)}),
        FileKeyProvider.from_env({"KEK": base64.b64encode(variable).decode()}),
    ]
    for proveedor in proveedores:
        proveedor.kek()
        for texto in (repr(proveedor), str(proveedor), f"{proveedor!r}", repr(vars(proveedor)) if hasattr(proveedor, "__dict__") else ""):
            assert _sin_kek_en(texto, kek)
            assert _sin_kek_en(texto, variable)


def test_las_excepciones_no_muestran_el_contenido_de_la_kek(tmp_path):
    contenido = os.urandom(31)
    ruta = _escribir(tmp_path / "corta.kek", contenido)
    variable = base64.b64encode(os.urandom(31)).decode()
    for crear in (lambda: FileKeyProvider(ruta).kek(), lambda: _desde_entorno({"KEK": variable})):
        with pytest.raises(KeyUnavailable) as info:
            crear()
        textos = [str(info.value), repr(info.value), *map(str, info.value.args)]
        assert all(_sin_kek_en(texto, contenido) and variable not in texto for texto in textos)


def test_los_registros_de_log_no_contienen_la_kek(tmp_path, caplog):
    ruta, kek = _kek_en_archivo(tmp_path)
    corta = _escribir(tmp_path / "corta.kek", os.urandom(5))
    variable = os.urandom(32)
    caplog.set_level(logging.DEBUG)
    FileKeyProvider(ruta).kek()
    _desde_entorno({"KEK": base64.b64encode(variable).decode()})
    for malo in (FileKeyProvider(corta), FileKeyProvider(tmp_path / "ausente.kek")):
        with pytest.raises(KeyUnavailable):
            malo.kek()
    texto = "\n".join(registro.getMessage() + repr(registro.args) + str(registro.exc_text) for registro in caplog.records)
    assert _sin_kek_en(texto, kek) and _sin_kek_en(texto, variable)


def test_la_traza_de_un_error_no_contiene_la_kek(tmp_path):
    import traceback

    contenido = os.urandom(20)
    ruta = _escribir(tmp_path / "corta.kek", contenido)
    with pytest.raises(KeyUnavailable) as info:
        FileKeyProvider(ruta).kek()
    traza = "".join(traceback.format_exception(info.value))
    assert _sin_kek_en(traza, contenido)


def test_proveedor_de_archivo_cumple_el_contrato(tmp_path):
    ruta, kek = _kek_en_archivo(tmp_path)
    comprobar_key_provider(FileKeyProvider(ruta), kek)
    comprobar_key_provider_sin_kek(FileKeyProvider(tmp_path / "ausente.kek"))


def test_doble_cumple_el_contrato():
    kek = os.urandom(32)
    comprobar_key_provider(FakeKeyProvider(kek), kek)
    comprobar_key_provider_sin_kek(FakeKeyProvider())


def _sha(datos: bytes) -> str:
    return hashlib.sha256(datos).hexdigest()


def _cifrar(cifrador: EnvelopeCipher, claro: bytes) -> bytes:
    return b"".join(cifrador.encrypt(io.BytesIO(claro), _sha(claro)))


def _descifrar(cifrador: EnvelopeCipher, cifrado: bytes, sha: str) -> bytes:
    return b"".join(cifrador.decrypt(io.BytesIO(cifrado), sha))


@pytest.mark.parametrize("claro", [b"", b"x", os.urandom(100), os.urandom(64 * 3), os.urandom(64 * 3 + 7)])
def test_ida_y_vuelta_con_envelope_cipher_y_kek_de_archivo(tmp_path, claro):
    ruta, _ = _kek_en_archivo(tmp_path)
    cifrador = EnvelopeCipher(FileKeyProvider(ruta), chunk_size=64)
    assert _descifrar(cifrador, _cifrar(cifrador, claro), _sha(claro)) == claro


def test_otro_nodo_con_el_mismo_archivo_descifra_lo_cifrado_por_el_primero(tmp_path):
    ruta, _ = _kek_en_archivo(tmp_path)
    claro = os.urandom(200)
    cifrado = _cifrar(EnvelopeCipher(FileKeyProvider(ruta), chunk_size=64), claro)
    otro = EnvelopeCipher(FileKeyProvider.from_env({"KEK_FILE": str(ruta)}), chunk_size=64)
    assert _descifrar(otro, cifrado, _sha(claro)) == claro


def test_una_kek_distinta_no_descifra(tmp_path):
    ruta, _ = _kek_en_archivo(tmp_path)
    otra, _ = _kek_en_archivo(tmp_path, nombre="otra.kek")
    claro = os.urandom(200)
    cifrado = _cifrar(EnvelopeCipher(FileKeyProvider(ruta), chunk_size=64), claro)
    with pytest.raises(DecryptionError):
        _descifrar(EnvelopeCipher(FileKeyProvider(otra), chunk_size=64), cifrado, _sha(claro))


def test_sin_kek_el_cifrador_no_produce_ni_consume_datos(tmp_path):
    cifrador = EnvelopeCipher(FileKeyProvider(tmp_path / "ausente.kek"), chunk_size=64)
    with pytest.raises(KeyUnavailable):
        next(cifrador.encrypt(io.BytesIO(b"secreto"), _sha(b"secreto")))
    with pytest.raises(KeyUnavailable):
        next(cifrador.decrypt(io.BytesIO(b"\x00" * 200), _sha(b"secreto")))


def test_la_kek_se_vuelve_a_leer_si_el_archivo_cambia_de_permisos(tmp_path):
    ruta, kek = _kek_en_archivo(tmp_path)
    proveedor = FileKeyProvider(ruta)
    assert proveedor.kek() == kek
    ruta.chmod(0o644)
    with pytest.raises(KeyUnavailable):
        proveedor.kek()


def test_gitignore_excluye_los_archivos_de_kek():
    lineas = {linea.strip() for linea in (RAIZ / ".gitignore").read_text().splitlines()}
    assert {"*.kek", "kek*"} <= lineas


def test_no_hay_archivos_de_kek_versionados():
    rastreados = subprocess.run(["git", "ls-files"], cwd=RAIZ, capture_output=True, text=True, check=True).stdout.splitlines()
    assert [ruta for ruta in rastreados if ruta.endswith(".kek") or Path(ruta).name.startswith("kek")] == []


LLAVE_PRIVADA = re.compile(r"-----BEGIN (?:[A-Z]+ )*PRIVATE KEY-----")
SECRETO_MINIO = re.compile(r"MINIO_SECRET_KEY=([^\s`'\"|$<>{}]+)")
VALOR_DE_DEMO_DECLARADO = "minioadmin"


def _lineas_agregadas_o_quitadas_del_historial() -> list[tuple[str, str]]:
    salida = subprocess.run(
        ["git", "log", "-p", "--all", "--no-color", "--format="], cwd=RAIZ, capture_output=True, text=True, errors="replace", check=True
    ).stdout
    archivo, encontradas = "", []
    for linea in salida.splitlines():
        if linea.startswith("diff --git "):
            archivo = linea.rsplit(" b/", 1)[-1]
        elif linea[:1] in "+-" and not linea.startswith(("+++", "---")):
            encontradas.append((archivo, linea))
    return encontradas


def test_historial_sin_llaves():
    """Comando de la ficha M4: `git log -p --all | grep -nE 'BEGIN .*PRIVATE KEY|MINIO_SECRET_KEY=.+'`.

    Se excluyen los .md y tests/ porque citan el patrón, y se admite el valor de demo
    `minioadmin` de los archivos de despliegue local (riesgo 7 del SPEC).
    """
    sospechosas = []
    for archivo, linea in _lineas_agregadas_o_quitadas_del_historial():
        if archivo.endswith(".md") or archivo.startswith("tests/"):
            continue
        valor = SECRETO_MINIO.search(linea)
        if LLAVE_PRIVADA.search(linea) or (valor and valor.group(1) != VALOR_DE_DEMO_DECLARADO):
            sospechosas.append(f"{archivo}: {linea[:60]}")
    assert sospechosas == []
