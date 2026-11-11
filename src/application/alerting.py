import logging
from collections.abc import Sequence

from src.application.ports import AlertPublisher, FindingStore
from src.domain.alert_policy import Alert, case_closed_alert, high_incident_alerts
from src.domain.finding import Finding


class SafeAlertPublisher:
    def __init__(self, inner: AlertPublisher, log: logging.Logger) -> None:
        self._inner = inner
        self._log = log

    def publish(self, kind: str, case_id: str, detail: str) -> None:
        try:
            self._inner.publish(kind, case_id, detail)
        except Exception:
            self._log.exception("alerta %s del caso %s no publicada", kind, case_id)


class AlertingFindingStore:
    def __init__(self, inner: FindingStore, publisher: AlertPublisher) -> None:
        self._inner = inner
        self._publisher = publisher

    def add(self, case_id: str, findings: Sequence[Finding]) -> None:
        self._inner.add(case_id, findings)
        _publish_all(self._publisher, high_incident_alerts(case_id, findings))

    def list(self, case_id: str) -> list[Finding]:
        return self._inner.list(case_id)


def notify_case_closed(publisher: AlertPublisher, case_id: str, status: str) -> None:
    _publish_all(publisher, [case_closed_alert(case_id, status)])


def _publish_all(publisher: AlertPublisher, alerts: Sequence[Alert]) -> None:
    for alert in alerts:
        publisher.publish(alert.kind, alert.case_id, alert.detail)
