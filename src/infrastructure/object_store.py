from __future__ import annotations

from collections.abc import Mapping
import os

import minio

from src.adapters.encrypted_object_store import EncryptedObjectStore
from src.adapters.envelope_cipher import EnvelopeCipher
from src.adapters.file_key_provider import FileKeyProvider
from src.adapters.minio_object_store import MinioObjectStore
from src.adapters.disk_chunk_staging import DiskChunkStaging
from src.application.chunked_upload import ChunkedUpload
from src.infrastructure.tls import TlsSettings, exigir_cifrado, minio_http_client


def crear_subidas(env: Mapping[str, str] | None = None) -> ChunkedUpload:
    env = os.environ if env is None else env
    staging_dir = env.get("STAGING_DIR", "/var/lib/dispatcher/staging").strip()
    if not staging_dir:
        raise ValueError("faltan variables requeridas de MinIO, OBJECTS_BUCKET o STAGING_DIR")
    return ChunkedUpload(DiskChunkStaging(staging_dir), crear_almacen_lectura(env))


def crear_almacen_lectura(env: Mapping[str, str] | None = None) -> EncryptedObjectStore:
    env = os.environ if env is None else env
    endpoint = env.get("MINIO_ENDPOINT", "").strip()
    access_key = env.get("MINIO_ACCESS_KEY", "").strip()
    secret_key = env.get("MINIO_SECRET_KEY", "")
    bucket = env.get("OBJECTS_BUCKET", "objetos").strip()
    if not all((endpoint, access_key, secret_key, bucket)):
        raise ValueError("faltan variables requeridas de MinIO o OBJECTS_BUCKET")
    secure = env.get("MINIO_SECURE", "true").strip().lower() not in {"0", "false", "no", "off"}
    tls = TlsSettings.from_env(env)
    exigir_cifrado(tls, minio_secure=secure)
    cliente = minio.Minio(endpoint, access_key=access_key, secret_key=secret_key,
                          secure=secure, http_client=minio_http_client(tls))
    if not cliente.bucket_exists(bucket):
        cliente.make_bucket(bucket)
    return EncryptedObjectStore(
        MinioObjectStore(cliente, bucket),
        EnvelopeCipher(FileKeyProvider.from_env(env)),
    )
