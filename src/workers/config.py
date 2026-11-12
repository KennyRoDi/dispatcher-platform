from __future__ import annotations

import math
import os
import socket
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Mapping

import dotenv
import redis

from src.domain.admission import FootprintTable
from src.infrastructure.tls import TlsSettings, redis_kwargs

OPERATIONS = (
    "transcode_video",
    "extract_audio",
    "generate_thumbnail",
    "convert_audio",
    "extract_metadata",
)

WORKER_KINDS = ("text", "image", "audio")

_TRUE_VALUES = {"1", "true", "yes", "on"}
_HWACCEL_VALUES = ("nvenc",)


def _default_worker_id() -> str:
    return "worker-" + socket.gethostname()


def _str(env: Mapping[str, str], name: str, default: str) -> str:
    value = env.get(name)
    if value is None or value == "":
        return default
    return value


def _optional_str(env: Mapping[str, str], name: str) -> str | None:
    value = env.get(name)
    if value is None or value == "":
        return None
    return value


def _int(env: Mapping[str, str], name: str, default: int) -> int:
    value = env.get(name)
    if value is None or value == "":
        return default
    return int(value)


def _float(env: Mapping[str, str], name: str, default: float) -> float:
    value = env.get(name)
    if value is None or value == "":
        return default
    return float(value)


def _optional_float(env: Mapping[str, str], name: str) -> float | None:
    value = env.get(name)
    if value is None or value == "":
        return None
    return float(value)


def _bool(env: Mapping[str, str], name: str, default: bool) -> bool:
    value = env.get(name)
    if value is None or value == "":
        return default
    return value.strip().lower() in _TRUE_VALUES


def _parse_worker_queues(raw: str) -> tuple[str, ...]:
    queues: list[str] = []
    for item in raw.split(","):
        item = item.strip()
        if not item:
            continue
        if item.startswith("queue:"):
            item = item[len("queue:"):]
        if item not in OPERATIONS:
            raise ValueError(f"invalid operation in WORKER_QUEUES: {item!r}")
        queues.append(item)
    if not queues:
        raise ValueError(f"WORKER_QUEUES must not be empty: {raw!r}")
    return tuple(queues)


def _parse_hwaccel(raw: str | None) -> str | None:
    if raw is None or raw.strip() == "":
        return None
    value = raw.strip().lower()
    if value not in _HWACCEL_VALUES:
        raise ValueError(f"invalid HWACCEL: {raw!r} (accepted: {', '.join(_HWACCEL_VALUES)})")
    return value


def _typed_worker_settings(env: Mapping[str, str], worker_concurrency: int) -> str | None:
    kind = _optional_str(env, "WORKER_KIND")
    if kind is None:
        return None
    if kind not in WORKER_KINDS:
        raise ValueError(f"invalid WORKER_KIND: {kind!r} (accepted: {', '.join(WORKER_KINDS)})")
    # spaCy, transformers, YOLO and CTranslate2 are not known to be thread-safe sharing one model.
    if worker_concurrency != 1:
        raise ValueError(f"WORKER_CONCURRENCY must be 1 with WORKER_KIND: {worker_concurrency}")
    _required_bytes(env, f"FOOTPRINT_{kind.upper()}_BYTES")
    return kind


@dataclass(frozen=True)
class Settings:
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_password: str | None = None
    coordinator_url: str = "http://localhost:8000"
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_secure: bool = False
    dataset_bucket: str = "dataset"
    results_bucket: str = "results"
    worker_id: str = field(default_factory=_default_worker_id)
    node_name: str = field(default_factory=socket.gethostname)
    worker_queues: tuple[str, ...] = OPERATIONS
    worker_concurrency: int = 1
    work_dir: Path = Path(tempfile.gettempdir()) / "mm-worker"
    heartbeat_interval: float = 5.0
    heartbeat_ttl: int = 15
    ffmpeg_timeout: float | None = None
    reaper_interval: float = 10.0
    reaper_max_age: float = 2100.0
    max_attempts: int = 3
    retry_base_s: float = 1
    retry_cap_s: float = 30
    hwaccel: str | None = None
    node_ip: str | None = None
    worker_token: str | None = field(default=None, repr=False)
    worker_kind: str | None = None

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "Settings":
        if env is None:
            dotenv.load_dotenv()
            env = os.environ
        # A .env saved on Windows carries \r on every value; strip it and stray spaces.
        env = {k: v.strip() for k, v in env.items() if isinstance(v, str)}

        coordinator_url = _str(env, "COORDINATOR_URL", cls.coordinator_url).rstrip("/")

        raw_queues = _optional_str(env, "WORKER_QUEUES")
        worker_queues = _parse_worker_queues(raw_queues) if raw_queues is not None else cls.worker_queues

        worker_concurrency = _int(env, "WORKER_CONCURRENCY", cls.worker_concurrency)
        if worker_concurrency < 1:
            raise ValueError(f"WORKER_CONCURRENCY must be >= 1: {worker_concurrency}")

        retry_base_s = _float(env, "RETRY_BASE_S", cls.retry_base_s)
        retry_cap_s = _float(env, "RETRY_CAP_S", cls.retry_cap_s)
        if not (math.isfinite(retry_base_s) and math.isfinite(retry_cap_s)) or retry_base_s <= 0 or retry_cap_s < retry_base_s:
            raise ValueError(f"RETRY_BASE_S debe ser > 0 y <= RETRY_CAP_S: {retry_base_s}, {retry_cap_s}")

        worker_kind = _typed_worker_settings(env, worker_concurrency)

        raw_work_dir = _optional_str(env, "WORK_DIR")
        work_dir = Path(raw_work_dir) if raw_work_dir is not None else cls.work_dir

        raw_worker_id = _optional_str(env, "WORKER_ID")
        worker_id = raw_worker_id if raw_worker_id is not None else _default_worker_id()

        return cls(
            redis_host=_str(env, "REDIS_HOST", cls.redis_host),
            redis_port=_int(env, "REDIS_PORT", cls.redis_port),
            redis_password=_optional_str(env, "REDIS_PASSWORD"),
            coordinator_url=coordinator_url,
            minio_endpoint=_str(env, "MINIO_ENDPOINT", cls.minio_endpoint),
            minio_access_key=_str(env, "MINIO_ACCESS_KEY", cls.minio_access_key),
            minio_secret_key=_str(env, "MINIO_SECRET_KEY", cls.minio_secret_key),
            minio_secure=_bool(env, "MINIO_SECURE", cls.minio_secure),
            dataset_bucket=_str(env, "DATASET_BUCKET", cls.dataset_bucket),
            results_bucket=_str(env, "RESULTS_BUCKET", cls.results_bucket),
            worker_id=worker_id,
            node_name=_str(env, "NODE_NAME", socket.gethostname()),
            worker_queues=worker_queues,
            worker_concurrency=worker_concurrency,
            work_dir=work_dir,
            heartbeat_interval=_float(env, "HEARTBEAT_INTERVAL", cls.heartbeat_interval),
            heartbeat_ttl=_int(env, "HEARTBEAT_TTL", cls.heartbeat_ttl),
            ffmpeg_timeout=_optional_float(env, "FFMPEG_TIMEOUT"),
            reaper_interval=_float(env, "REAPER_INTERVAL", cls.reaper_interval),
            reaper_max_age=_float(env, "REAPER_MAX_AGE", cls.reaper_max_age),
            max_attempts=_int(env, "MAX_ATTEMPTS", cls.max_attempts),
            retry_base_s=retry_base_s,
            retry_cap_s=retry_cap_s,
            hwaccel=_parse_hwaccel(env.get("HWACCEL")),
            node_ip=_optional_str(env, "NODE_IP"),
            worker_token=_optional_str(env, "WORKER_TOKEN"),
            worker_kind=worker_kind,
        )

    def queue_keys(self) -> list[str]:
        """BLPOP key order: every high-priority queue first, then every normal queue."""
        high = [f"queue:{operation}:high" for operation in self.worker_queues]
        normal = [f"queue:{operation}" for operation in self.worker_queues]
        return high + normal

    def threads_per_job(self) -> int:
        cpu_count = os.process_cpu_count() or 1
        return max(1, cpu_count // self.worker_concurrency)


def _required_bytes(env: Mapping[str, str], name: str) -> int:
    value = env.get(name, "").strip()
    if not value.isascii() or not value.isdecimal():
        raise ValueError(f"{name} es obligatoria y debe ser un entero en bytes")
    return int(value)


def load_admission_config(
    env: Mapping[str, str], operations: Iterable[str]
) -> tuple[FootprintTable, int]:
    margin = _required_bytes(env, "ADMISSION_MARGIN_BYTES")
    footprints = {
        operation: _required_bytes(env, f"FOOTPRINT_{operation.upper()}_BYTES")
        for operation in operations
    }
    return FootprintTable(footprints), margin


def make_redis(settings: Settings, tls: TlsSettings | None = None) -> redis.Redis:
    tls = tls if tls is not None else TlsSettings.from_env()
    return redis.Redis(
        host=settings.redis_host,
        port=settings.redis_port,
        password=settings.redis_password,
        decode_responses=True,
        socket_keepalive=True,
        health_check_interval=30,
        **redis_kwargs(tls),
    )
