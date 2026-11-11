import logging
from datetime import datetime, timezone

from src.domain.alert_policy import StoredAlert

logger = logging.getLogger(__name__)


class RedisAlertStream:
    def __init__(self, client, clock, key: str = "alerts", maxlen: int = 1000) -> None:
        self._client = client
        self._clock = clock
        self._key = key
        self._maxlen = maxlen

    def publish(self, kind: str, case_id: str, detail: str) -> None:
        emitted_at = self._clock.now().astimezone(timezone.utc).isoformat()
        fields = {"kind": kind, "case_id": case_id, "detail": detail, "emitted_at": emitted_at}
        self._client.xadd(self._key, fields, maxlen=self._maxlen, approximate=True)

    def recent(self, limit: int) -> list[StoredAlert]:
        entries = self._client.xrevrange(self._key, count=limit)
        decoded = [_decode(entry_id, fields) for entry_id, fields in entries]
        valid = [alert for alert in decoded if alert is not None]
        if len(valid) < len(decoded):
            logger.warning("%d alertas ilegibles omitidas", len(decoded) - len(valid))
        return valid


def _decode(entry_id: str, fields: dict) -> StoredAlert | None:
    try:
        return StoredAlert(
            entry_id, fields["kind"], fields["case_id"], fields["detail"], datetime.fromisoformat(fields["emitted_at"])
        )
    except (KeyError, ValueError, TypeError):
        return None
