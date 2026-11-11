import logging
from datetime import datetime, timezone

# redis-py no ofrece forma pública de leer sin decodificar con decode_responses=True; su propio
# código usa esta constante interna (commands/core.py). Una prueba avisa si deja de existir.
from redis.client import NEVER_DECODE

from src.domain.alert_policy import StoredAlert

logger = logging.getLogger(__name__)


class RedisAlertStream:
    def __init__(self, client, clock, key: str = "alerts", maxlen: int = 1000) -> None:
        if maxlen < 1:
            raise ValueError(f"maxlen debe ser positivo: {maxlen}")
        self._client = client
        self._clock = clock
        self._key = key
        self._maxlen = maxlen

    def publish(self, kind: str, case_id: str, detail: str) -> None:
        emitted_at = self._clock.now().astimezone(timezone.utc).isoformat()
        fields = {"kind": kind, "case_id": case_id, "detail": detail, "emitted_at": emitted_at}
        self._client.xadd(self._key, fields, maxlen=self._maxlen, approximate=True)

    def recent(self, limit: int) -> list[StoredAlert]:
        if limit < 1:
            return []
        entries = self._read(limit)
        decoded = [_decode(entry_id, fields) for entry_id, fields in entries]
        valid = [alert for alert in decoded if alert is not None]
        if len(valid) < len(decoded):
            logger.warning("%d alertas ilegibles omitidas", len(decoded) - len(valid))
        return valid

    def _read(self, limit: int) -> list:
        try:
            return self._client.xrevrange(self._key, count=limit)
        except UnicodeDecodeError:
            # Bytes no UTF-8 de una entrada ajena rompen la lectura decodificada: se relee en crudo.
            return self._client.execute_command(
                "XREVRANGE", self._key, "+", "-", "COUNT", limit, **{NEVER_DECODE: True}
            )


def _text(value) -> str:
    return value.decode("utf-8") if isinstance(value, bytes) else value


def _decode(entry_id, fields: dict) -> StoredAlert | None:
    try:
        text = {_text(name): _text(value) for name, value in fields.items()}
        emitted_at = datetime.fromisoformat(text["emitted_at"])
        if emitted_at.tzinfo is None:
            return None
        return StoredAlert(_text(entry_id), text["kind"], text["case_id"], text["detail"], emitted_at.astimezone(timezone.utc))
    except (KeyError, ValueError, TypeError, AttributeError):
        return None
