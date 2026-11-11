import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import fakeredis
import pytest
from fastapi.testclient import TestClient

import src.coordinator.main as main
from src.adapters.redis_alert_stream import RedisAlertStream
from src.application.alerting import AlertingFindingStore, SafeAlertPublisher
from src.coordinator import conexion, rutas_alertas
from src.domain.finding import EvidenceRef, Finding, Severity
from tests.ayudas_cierre import crear_caso, reportar
from tests.dobles import FakeClock, FakeFindingStore

pytestmark = pytest.mark.acceptance

INICIO = datetime(2026, 11, 3, 8, 0, tzinfo=timezone.utc)
SHA = "a" * 64
DURACION_DEL_PROCESO = timedelta(minutes=12)


def test_alerta_de_incidencia_y_de_cierre_visible_en_alerts(monkeypatch):
    redis_falso = fakeredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(conexion, "redis_client", redis_falso)
    reloj = FakeClock(INICIO)
    flujo = RedisAlertStream(redis_falso, reloj)
    main.app.dependency_overrides[rutas_alertas.obtener_publicador_alertas] = lambda: SafeAlertPublisher(flujo, rutas_alertas.logger)
    main.app.dependency_overrides[rutas_alertas.obtener_lector_alertas] = lambda: flujo
    try:
        cliente = TestClient(main.app)
        case_id, (subtarea,) = crear_caso(cliente)
        almacen = AlertingFindingStore(FakeFindingStore(), flujo)

        marca_hallazgo = reloj.now()
        almacen.add(case_id, [Finding("amenaza", Severity.ALTA, 0.9, EvidenceRef(SHA, "mensajes 3"), "texto sintetico")])
        assert [a["kind"] for a in cliente.get("/alerts").json()["alertas"]] == ["incidencia_alta"]

        reloj.advance(DURACION_DEL_PROCESO)
        assert reportar(cliente, case_id, subtarea).json()["case_status"] == "completed"
        alertas = cliente.get("/alerts").json()["alertas"]
    finally:
        main.app.dependency_overrides.clear()

    cierre, incidencia = alertas
    assert (incidencia["kind"], cierre["kind"]) == ("incidencia_alta", "caso_finalizado")
    assert incidencia["case_id"] == cierre["case_id"] == case_id
    assert json.loads(incidencia["detail"]) == {"categoria": "amenaza", "confianza": 0.9, "sha256": SHA, "posicion": "mensajes 3"}
    assert json.loads(cierre["detail"]) == {"estado": "completed"}
    emision_incidencia = datetime.fromisoformat(incidencia["emitted_at"])
    emision_cierre = datetime.fromisoformat(cierre["emitted_at"])
    assert emision_incidencia == marca_hallazgo
    assert emision_cierre - emision_incidencia == DURACION_DEL_PROCESO

    salida = os.environ.get("F14_EJEMPLO_JSON")
    if salida:
        evidencia = {
            "reloj": "FakeClock inyectado con datos sinteticos; no mide rendimiento",
            "caso": case_id,
            "marca_hallazgo_alto": marca_hallazgo.isoformat(),
            "alertas": [{"kind": a["kind"], "emitted_at": a["emitted_at"]} for a in (incidencia, cierre)],
            "de_la_incidencia_al_cierre_s": (emision_cierre - emision_incidencia).total_seconds(),
        }
        Path(salida).write_text(json.dumps(evidencia, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
