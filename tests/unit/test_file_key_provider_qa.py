import base64
import os
import traceback

import pytest

from src.adapters.file_key_provider import FileKeyProvider
from src.application.ports import KeyUnavailable


def _descriptores_abiertos() -> int:
    return len(os.listdir("/proc/self/fd"))


def _locales_de_la_traza(error: BaseException) -> list[object]:
    return [valor for marco, _ in traceback.walk_tb(error.__traceback__) for valor in marco.f_locals.values()]


def _alguna_local_contiene(error: BaseException, secretos: list[bytes]) -> bool:
    for valor in _locales_de_la_traza(error):
        texto = valor if isinstance(valor, bytes) else repr(valor).encode() if isinstance(valor, str) else b""
        if any(secreto in texto for secreto in secretos):
            return True
    return False


def _formas(kek: bytes) -> list[bytes]:
    return [kek, base64.b64encode(kek), kek.hex().encode()]


@pytest.mark.xfail(strict=True, reason="QA: ValueError por ruta con NUL se escapa; debe ser KeyUnavailable")
@pytest.mark.parametrize("ruta", ["a\0b", "\0"])
def test_ruta_con_nul_falla_con_key_unavailable(ruta):
    with pytest.raises(KeyUnavailable):
        FileKeyProvider(ruta).kek()


@pytest.mark.xfail(strict=True, reason="QA: KEK_FILE con NUL en el entorno da ValueError, no KeyUnavailable")
def test_kek_file_con_nul_en_el_entorno_falla_con_key_unavailable():
    with pytest.raises(KeyUnavailable):
        FileKeyProvider.from_env({"KEK_FILE": "a\0b"}).kek()


@pytest.mark.xfail(strict=True, reason="QA: UnicodeEncodeError (ValueError) con sustituto aislado en la ruta")
def test_ruta_con_sustituto_unicode_falla_con_key_unavailable():
    with pytest.raises(KeyUnavailable):
        FileKeyProvider("\ud800").kek()


@pytest.mark.xfail(strict=True, reason="QA: os.fdopen falla con un directorio y el descriptor de os.open no se cierra")
def test_un_directorio_no_filtra_descriptores(tmp_path):
    carpeta = tmp_path / "carpeta.kek"
    carpeta.mkdir(mode=0o700)
    antes = _descriptores_abiertos()
    for _ in range(50):
        with pytest.raises(KeyUnavailable):
            FileKeyProvider(carpeta).kek()
    assert _descriptores_abiertos() == antes


@pytest.mark.parametrize("rechazo", ["permisos", "corta", "ausente", "fifo"])
def test_los_demas_rechazos_no_filtran_descriptores(tmp_path, rechazo):
    ruta = tmp_path / "k.kek"
    if rechazo == "fifo":
        os.mkfifo(ruta, 0o600)
    elif rechazo == "permisos":
        ruta.write_bytes(os.urandom(32))
        ruta.chmod(0o644)
    elif rechazo == "corta":
        ruta.write_bytes(os.urandom(5))
        ruta.chmod(0o400)
    antes = _descriptores_abiertos()
    for _ in range(50):
        with pytest.raises(KeyUnavailable):
            FileKeyProvider(ruta).kek()
    assert _descriptores_abiertos() == antes


@pytest.mark.xfail(strict=True, reason="QA: el marco de _checked conserva la KEK de un archivo de 33 bytes (p. ej. con salto de línea)")
def test_la_traza_no_conserva_la_kek_en_variables_locales_con_largo_incorrecto(tmp_path):
    kek = os.urandom(32)
    ruta = tmp_path / "con-salto.kek"
    ruta.write_bytes(kek + b"\n")
    ruta.chmod(0o400)
    with pytest.raises(KeyUnavailable) as info:
        FileKeyProvider(ruta).kek()
    assert not _alguna_local_contiene(info.value, _formas(kek))


@pytest.mark.xfail(strict=True, reason="QA: el marco de _checked conserva la KEK base64 de largo incorrecto")
def test_la_traza_no_conserva_la_kek_base64_de_largo_incorrecto():
    kek = os.urandom(31)
    with pytest.raises(KeyUnavailable) as info:
        FileKeyProvider.from_env({"KEK": base64.b64encode(kek).decode()}).kek()
    assert not _alguna_local_contiene(info.value, _formas(kek))


@pytest.mark.xfail(strict=True, reason="QA: el marco de _decode_base64 conserva el texto de la KEK mal escrita (`encoded`)")
def test_la_traza_no_conserva_la_kek_base64_invalida():
    kek = os.urandom(32)
    mala = base64.b64encode(kek).decode()[:-1] + "!"
    with pytest.raises(KeyUnavailable) as info:
        FileKeyProvider.from_env({"KEK": mala}).kek()
    assert not _alguna_local_contiene(info.value, [mala[:-1].encode()])


@pytest.mark.parametrize("modo", [0o200, 0o000, 0o100])
def test_archivo_sin_lectura_para_el_propietario_falla_cerrado(tmp_path, modo):
    ruta = tmp_path / "k.kek"
    ruta.write_bytes(os.urandom(32))
    ruta.chmod(modo)
    with pytest.raises(KeyUnavailable):
        FileKeyProvider(ruta).kek()


@pytest.mark.xfail(strict=True, reason="QA: el SPEC pide 0400/0600 pero 0500, 0700, 4400 y 1400 se aceptan (solo se mira grupo y otros)")
@pytest.mark.parametrize("modo", [0o500, 0o700, 0o4400, 0o1400])
def test_solo_se_aceptan_los_modos_0400_y_0600(tmp_path, modo):
    ruta = tmp_path / "k.kek"
    ruta.write_bytes(os.urandom(32))
    ruta.chmod(modo)
    with pytest.raises(KeyUnavailable):
        FileKeyProvider(ruta).kek()


@pytest.mark.parametrize("valor", [None, "", "   ", "\n"])
def test_kek_file_en_blanco_y_kek_ausente_falla_cerrado(valor):
    entorno = {"KEK": ""} if valor is None else {"KEK_FILE": valor}
    with pytest.raises(KeyUnavailable):
        FileKeyProvider.from_env(entorno).kek()


@pytest.mark.parametrize("variante", ["salto_interno", "espacio_interno", "urlsafe", "sin_relleno", "no_ascii", "basura_tras_relleno"])
def test_kek_base64_malformada_se_rechaza(variante):
    kek = os.urandom(32)
    texto = base64.b64encode(kek).decode()
    while variante == "urlsafe" and "+" not in texto and "/" not in texto:
        kek = os.urandom(32)
        texto = base64.b64encode(kek).decode()
    malas = {
        "salto_interno": texto[:10] + "\n" + texto[10:],
        "espacio_interno": texto[:10] + " " + texto[10:],
        "urlsafe": base64.urlsafe_b64encode(kek).decode(),
        "sin_relleno": texto.rstrip("="),
        "no_ascii": texto[:-1] + "é",
        "basura_tras_relleno": texto + "AAAA",
    }
    with pytest.raises(KeyUnavailable):
        FileKeyProvider.from_env({"KEK": malas[variante]}).kek()


@pytest.mark.parametrize("sobrante", [b"\n", b"\0", b"x", os.urandom(1000)])
def test_archivo_de_33_o_mas_bytes_se_rechaza_aunque_los_32_primeros_sean_validos(tmp_path, sobrante):
    kek = os.urandom(32)
    ruta = tmp_path / "k.kek"
    ruta.write_bytes(kek + sobrante)
    ruta.chmod(0o400)
    with pytest.raises(KeyUnavailable):
        FileKeyProvider(ruta).kek()


def test_umask_restrictivo_o_laxo_no_cambia_el_resultado(tmp_path):
    kek = os.urandom(32)
    ruta = tmp_path / "k.kek"
    ruta.write_bytes(kek)
    ruta.chmod(0o400)
    anterior = os.umask(0o777)
    try:
        assert FileKeyProvider(ruta).kek() == kek
    finally:
        os.umask(anterior)


def test_cambiar_el_contenido_entre_llamadas_se_refleja_y_valida_de_nuevo(tmp_path):
    ruta = tmp_path / "k.kek"
    primera, segunda = os.urandom(32), os.urandom(32)
    ruta.write_bytes(primera)
    ruta.chmod(0o600)
    proveedor = FileKeyProvider(ruta)
    assert proveedor.kek() == primera
    ruta.write_bytes(segunda)
    assert proveedor.kek() == segunda
    ruta.write_bytes(segunda[:31])
    with pytest.raises(KeyUnavailable):
        proveedor.kek()


def test_enlace_simbolico_cambiado_a_un_destino_inseguro_se_revalida(tmp_path):
    bueno, malo = tmp_path / "bueno.kek", tmp_path / "malo.kek"
    bueno.write_bytes(os.urandom(32))
    bueno.chmod(0o400)
    malo.write_bytes(os.urandom(32))
    malo.chmod(0o644)
    enlace = tmp_path / "enlace.kek"
    enlace.symlink_to(bueno)
    proveedor = FileKeyProvider(enlace)
    proveedor.kek()
    enlace.unlink()
    enlace.symlink_to(malo)
    with pytest.raises(KeyUnavailable):
        proveedor.kek()


def test_el_modo_se_comprueba_sobre_el_descriptor_abierto_no_sobre_la_ruta(tmp_path, monkeypatch):
    kek = os.urandom(32)
    ruta = tmp_path / "k.kek"
    ruta.write_bytes(kek)
    ruta.chmod(0o400)
    leido = {}
    original = os.fstat

    def fstat_y_abrir_permisos(fd):
        info = original(fd)
        leido["modo"] = info.st_mode
        ruta.chmod(0o644)
        return info

    monkeypatch.setattr(os, "fstat", fstat_y_abrir_permisos)
    # Cambiar el modo tras fstat no puede alterar lo ya validado: se usa el mismo descriptor.
    assert FileKeyProvider(ruta).kek() == kek
    assert leido["modo"] & 0o777 == 0o400


@pytest.mark.parametrize("contenido", [b"\0" * 32, b"A" * 32])
def test_una_kek_de_32_bytes_triviales_se_acepta_sin_juzgar_entropia(tmp_path, contenido):
    ruta = tmp_path / "k.kek"
    ruta.write_bytes(contenido)
    ruta.chmod(0o400)
    assert FileKeyProvider(ruta).kek() == contenido


def test_repr_vars_y_str_no_exponen_la_kek_en_base64():
    kek = os.urandom(32)
    proveedor = FileKeyProvider.from_env({"KEK": base64.b64encode(kek).decode()})
    for texto in (repr(proveedor), str(proveedor), repr(vars(proveedor))):
        assert base64.b64encode(kek).decode() not in texto
        assert repr(kek) not in texto


def test_causa_y_contexto_de_la_excepcion_no_contienen_la_kek(tmp_path):
    kek = os.urandom(32)
    proveedores = []
    ruta = tmp_path / "k.kek"
    ruta.write_bytes(kek + b"x")
    ruta.chmod(0o400)
    proveedores.append(FileKeyProvider(ruta))
    proveedores.append(FileKeyProvider.from_env({"KEK": base64.b64encode(kek).decode()[:-1] + "!"}))
    for proveedor in proveedores:
        with pytest.raises(KeyUnavailable) as info:
            proveedor.kek()
        for cadena in (info.value.__cause__, info.value.__context__):
            texto = "" if cadena is None else repr(cadena) + str(cadena)
            assert base64.b64encode(kek).decode() not in texto and kek.hex() not in texto and repr(kek) not in texto
