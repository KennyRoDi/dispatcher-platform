from __future__ import annotations

import argparse
import csv
import os
from pathlib import Path
import minio

from scripts.subir_por_chunks import parse_tamano, subir
from src.infrastructure.tls import TlsSettings, exigir_cifrado, minio_http_client


def medir(carpeta: Path, reps: int, salida: Path) -> None:
    archivos = sorted(path for path in carpeta.rglob("*") if path.is_file())
    if not archivos:
        raise ValueError("el dataset no contiene archivos")
    base = os.environ.get("COORDINATOR_URL", "http://localhost:8000").rstrip("/")
    bucket = os.environ.get("OBJECTS_BUCKET", "objetos")
    endpoint = os.environ["MINIO_ENDPOINT"]
    secure = os.environ.get("MINIO_SECURE", "true").strip().lower() not in {"0", "false", "no", "off"}
    env = os.environ
    tls = TlsSettings.from_env(env)
    exigir_cifrado(tls, minio_secure=secure)
    cliente = minio.Minio(endpoint, access_key=env["MINIO_ACCESS_KEY"],
                          secret_key=env["MINIO_SECRET_KEY"], secure=secure,
                          http_client=minio_http_client(tls))
    if not cliente.bucket_exists(bucket):
        raise ValueError(f"el bucket {bucket!r} no existe")
    if any(cliente.list_objects(bucket, recursive=True)):
        raise ValueError("el bucket debe estar vacío al iniciar la medición")
    logical = 0
    for _ in range(reps):
        for archivo in archivos:
            subir(archivo, base, parse_tamano(os.environ.get("M3_CHUNK_SIZE", "4M")))
            logical += archivo.stat().st_size
    physical = sum(item.size for item in cliente.list_objects(bucket, recursive=True))
    saved = logical - physical
    ratio = 1 - physical / logical if logical else 0.0
    salida.parent.mkdir(parents=True, exist_ok=True)
    with salida.open("w", newline="", encoding="utf-8") as archivo:
        writer = csv.DictWriter(archivo, fieldnames=("files", "repetitions", "logical_bytes", "stored_bytes", "bytes_saved", "dedup_ratio"))
        writer.writeheader()
        writer.writerow({"files": len(archivos), "repetitions": reps, "logical_bytes": logical,
                         "stored_bytes": physical, "bytes_saved": saved, "dedup_ratio": f"{ratio:.8f}"})


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Mide la deduplicación de almacenamiento de objetos (F-23).")
    parser.add_argument("--dir", required=True, type=Path)
    parser.add_argument("--reps", type=int, default=3)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    if args.reps < 1:
        parser.error("--reps debe ser al menos 1")
    medir(args.dir, args.reps, args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
