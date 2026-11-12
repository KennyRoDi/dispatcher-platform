import hashlib

from src.adapters.hashing import sha256_de_archivo


def test_sha256_de_archivo_coincide_con_hashlib(tmp_path):
    ruta = tmp_path / "datos.bin"
    contenido = bytes(range(256)) * 5000
    ruta.write_bytes(contenido)

    assert sha256_de_archivo(ruta) == hashlib.sha256(contenido).hexdigest()


def test_sha256_de_archivo_vacio(tmp_path):
    ruta = tmp_path / "vacio.bin"
    ruta.write_bytes(b"")

    assert sha256_de_archivo(ruta) == hashlib.sha256(b"").hexdigest()
