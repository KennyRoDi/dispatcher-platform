from __future__ import annotations

import argparse
import csv
import hashlib
import os
import statistics
import time
from pathlib import Path

import minio
import requests

from scripts.subir_por_chunks import parse_tamano, sha256_bytes
from src.infrastructure.tls import TlsSettings, exigir_cifrado, minio_http_client

MIB = 1 << 20


def parse_chunk_sizes(value: str) -> list[int]:
    if not value.strip():
        raise ValueError("--chunk requiere al menos un tamaño")
    chunks = [parse_tamano(item.strip()) for item in value.split(",")]
    if len(set(chunks)) != len(chunks):
        raise ValueError("--chunk requiere tamaños únicos")
    return chunks


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(MIB):
            digest.update(block)
    return digest.hexdigest()


def _coordinator_url(remote: str) -> tuple[str, bool | str]:
    configured = os.environ.get("COORDINATOR_URL", "").strip()
    tls_enabled = os.environ.get("TLS_ENABLED", "true").strip().lower() not in {"0", "false", "no", "off"}
    if configured:
        return configured.rstrip("/"), os.environ.get("TLS_CA_FILE") if tls_enabled else False
    scheme = "https" if tls_enabled else "http"
    return f"{scheme}://{remote}:8000", os.environ.get("TLS_CA_FILE") if tls_enabled else False


def _run(path: Path, chunk_size: int, base_url: str, verify, session, object_client, bucket: str) -> dict:
    size = path.stat().st_size
    digest = _sha256(path)
    started = time.perf_counter()
    try:
        response = session.post(f"{base_url}/uploads", json={"sha256": digest, "size": size,
                                 "chunk_size": chunk_size}, timeout=60, verify=verify)
        if response.status_code != 201:
            raise RuntimeError(f"inicio de subida: {response.status_code} {response.text}")
        upload = response.json()
        upload_url = f"{base_url}/uploads/{upload['upload_id']}"
        with path.open("rb") as stream:
            for index in range(upload["chunk_count"]):
                chunk = stream.read(chunk_size)
                response = session.put(f"{upload_url}/chunks/{index}", data=chunk,
                                       headers={"X-Chunk-SHA256": sha256_bytes(chunk)}, timeout=600,
                                       verify=verify)
                if response.status_code not in (200, 204):
                    raise RuntimeError(f"chunk {index}: {response.status_code} {response.text}")
        complete_started = time.perf_counter()
        response = session.post(f"{upload_url}/complete", timeout=600, verify=verify)
        complete_seconds = time.perf_counter() - complete_started
        if response.status_code != 201:
            raise RuntimeError(f"completar subida: {response.status_code} {response.text}")
        total_seconds = time.perf_counter() - started
    finally:
        object_client.remove_object(bucket, digest)
    return {"sha256": digest, "chunk_bytes": chunk_size, "bytes": size,
            "total_seconds": total_seconds, "complete_seconds": complete_seconds,
            "mb_per_second": size / MIB / total_seconds}


def medir(path: Path, chunk_sizes: list[int], reps: int, remote: str, salida: Path) -> list[dict]:
    if not path.is_file() or path.stat().st_size < 200 * MIB:
        raise ValueError("--file debe ser un archivo del dataset sintético de al menos 200 MiB")
    env = os.environ
    bucket = env.get("OBJECTS_BUCKET", "objetos")
    minio_endpoint = env["MINIO_ENDPOINT"]
    minio_secure = env.get("MINIO_SECURE", "true").strip().lower() not in {"0", "false", "no", "off"}
    tls = TlsSettings.from_env(env)
    exigir_cifrado(tls, minio_secure=minio_secure)
    object_client = minio.Minio(minio_endpoint, access_key=env["MINIO_ACCESS_KEY"],
                                secret_key=env["MINIO_SECRET_KEY"], secure=minio_secure,
                                http_client=minio_http_client(tls))
    if not object_client.bucket_exists(bucket):
        raise ValueError(f"el bucket {bucket!r} no existe")
    if next(object_client.list_objects(bucket, recursive=True), None) is not None:
        raise ValueError("el bucket debe estar vacío al iniciar la medición")
    base_url, verify = _coordinator_url(remote)
    records: list[dict] = []
    for chunk_size in chunk_sizes:
        for repetition in range(1, reps + 1):
            records.append({"repetition": repetition, **_run(path, chunk_size, base_url,
                            verify, requests, object_client, bucket)})
    salida.parent.mkdir(parents=True, exist_ok=True)
    with salida.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=("repetition", "sha256", "chunk_bytes", "bytes",
                                    "total_seconds", "complete_seconds", "mb_per_second"))
        writer.writeheader()
        writer.writerows(records)
    for chunk_size in chunk_sizes:
        rates = [row["mb_per_second"] for row in records if row["chunk_bytes"] == chunk_size]
        deviation = statistics.stdev(rates) if len(rates) > 1 else 0.0
        print(f"chunk={chunk_size} bytes; mean={statistics.mean(rates):.3f} MiB/s; sd={deviation:.3f} MiB/s")
    return records


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Mide throughput de subida por tamaño de chunk (F-22/M3).")
    parser.add_argument("--file", required=True, type=Path)
    parser.add_argument("--chunk", required=True, help="lista separada por comas, por ejemplo 256K,1M,4M,16M")
    parser.add_argument("--reps", type=int, default=5)
    parser.add_argument("--remote", required=True, help="host del coordinador en el Nodo A")
    parser.add_argument("--out", type=Path, default=Path("docs/evidencia/m3_chunks.csv"))
    args = parser.parse_args(argv)
    if args.reps < 2:
        parser.error("--reps debe ser al menos 2")
    try:
        chunks = parse_chunk_sizes(args.chunk)
    except ValueError as error:
        parser.error(str(error))
    medir(args.file, chunks, args.reps, args.remote, args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
