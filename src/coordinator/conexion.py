from __future__ import annotations

import logging
import os
from typing import Optional

import redis as redis_lib
from fastapi import HTTPException

from src.infrastructure.tls import TlsSettings, redis_kwargs

logger = logging.getLogger(__name__)

REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
REDIS_PASSWORD: Optional[str] = os.getenv("REDIS_PASSWORD") or None  # "" → None

def make_redis_client(tls: TlsSettings | None = None) -> redis_lib.Redis:
    tls = tls if tls is not None else TlsSettings.from_env()
    return redis_lib.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        password=REDIS_PASSWORD,
        decode_responses=True,
        socket_keepalive=True,
        health_check_interval=30,
        **redis_kwargs(tls),
    )


redis_client: redis_lib.Redis = make_redis_client()


def redis_unavailable(e: Exception) -> HTTPException:
    """Convert a Redis connection error into a clean HTTP 503."""
    logger.error("Redis no disponible: %s", e)
    return HTTPException(
        status_code=503,
        detail=(
            f"Redis no está disponible ({REDIS_HOST}:{REDIS_PORT}). "
            "Inicia Redis antes de usar el coordinador. "
            f"Detalle: {e}"
        ),
    )


