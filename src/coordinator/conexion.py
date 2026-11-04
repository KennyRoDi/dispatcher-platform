from __future__ import annotations

import logging
import os
from typing import Optional

import redis as redis_lib
from fastapi import HTTPException

logger = logging.getLogger(__name__)

REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
REDIS_PASSWORD: Optional[str] = os.getenv("REDIS_PASSWORD") or None  # "" → None

redis_client: redis_lib.Redis = redis_lib.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    password=REDIS_PASSWORD,
    decode_responses=True,
    socket_keepalive=True,
    health_check_interval=30,
)


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


