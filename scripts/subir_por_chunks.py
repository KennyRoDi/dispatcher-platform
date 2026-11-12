from __future__ import annotations

import argparse
import hashlib
import re
import sys
from pathlib import Path

import requests

BLOQUE = 1 << 20
_SUFIJOS = {"": 1, "k": 1 << 10, "m": 1 << 20}


class SubidaFallida(Exception):
    pass


def parse_tamano(texto: str) -> int:
    coincidencia = re.fullmatch(r"(\d+)([kKmM]?)", texto)
    if not coincidencia or int(coincidencia.group(1)) == 0:
        raise ValueError(f"tamaño inválido: {texto!r}")
    return int(coincidencia.group(1)) * _SUFIJOS[coincidencia.group(2).lower()]


def sha256_bytes(datos: bytes) -> str:
    return hashlib.sha256(datos).hexdigest()


def sha256_archivo(ruta: Path, bloque: int = BLOQUE) -> str:
    resumen = hashlib.sha256()
    with open(ruta, "rb") as archivo:
        while parte := archivo.read(bloque):
            resumen.update(parte)
    return resumen.hexdigest()


def _exigir(respuesta, codigo: int, accion: str):
    if respuesta.status_code != codigo:
        raise SubidaFallida(f"{accion}: {respuesta.status_code} {respuesta.text}")
    return respuesta


def _enviar(session, url: str, ruta: Path, chunk_size: int, indices) -> None:
    with open(ruta, "rb") as archivo:
        for indice in indices:
            archivo.seek(indice * chunk_size)
            dato = archivo.read(chunk_size)
            respuesta = session.put(f"{url}/chunks/{indice}", data=dato,
                                    headers={"X-Chunk-SHA256": sha256_bytes(dato)}, timeout=60)
            if respuesta.status_code not in (200, 204):
                raise SubidaFallida(f"chunk {indice}: {respuesta.status_code} {respuesta.text}")


def subir(ruta: Path, url_base: str, chunk_size: int, session=requests, reintentos: int = 3) -> dict:
    ruta = Path(ruta)
    size = ruta.stat().st_size
    inicio_respuesta = session.post(f"{url_base}/uploads", json={
        "sha256": sha256_archivo(ruta), "size": size, "chunk_size": chunk_size}, timeout=60)
    if inicio_respuesta.status_code == 200:
        return _exigir(inicio_respuesta, 200, "consultar objeto").json()
    inicio = _exigir(inicio_respuesta, 201, "iniciar").json()
    url = f"{url_base}/uploads/{inicio['upload_id']}"
    pendientes = range(inicio["chunk_count"])
    for _ in range(reintentos + 1):
        _enviar(session, url, ruta, chunk_size, pendientes)
        respuesta = session.post(f"{url}/complete", timeout=600)
        if respuesta.status_code != 409:
            return _exigir(respuesta, 201, "completar").json()
        pendientes = respuesta.json()["missing"]
    raise SubidaFallida(f"faltan chunks tras {reintentos} reintentos: {pendientes}")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Sube un archivo al coordinador por chunks verificados (F-22).")
    parser.add_argument("archivo", type=Path)
    parser.add_argument("--url", default="http://localhost:8000")
    parser.add_argument("--chunk", type=parse_tamano, default=4 << 20)
    args = parser.parse_args(argv)
    print(subir(args.archivo, args.url.rstrip("/"), args.chunk))
    return 0


if __name__ == "__main__":
    sys.exit(main())
