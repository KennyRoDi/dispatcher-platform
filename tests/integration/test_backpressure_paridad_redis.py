"""QA F-24 parte 1, fase 4: el script Lua deja en Redis lo mismo que el pipeline sin límite."""
import itertools
import uuid

import pytest
from fastapi.testclient import TestClient

import src.coordinator.main as main
from src.coordinator import rutas_casos
from tests.integration.test_backpressure_redis import r, servidor_redis  # noqa: F401

pytestmark = pytest.mark.integration

CASO = {
    "case_id": "cañón \"x\" 'y' 漢字",
    "priority": "high",
    "metadata": {"a": "ñ\"'\\", "b": [1, 2.5, None, True], "c": {}},
    "subtasks": [
        {"task_type": "transcode_video", "file_path": "vídeos/a \"c\".mp4", "params": {}, "metadata": {"t": "é"}},
        {"task_type": "auto", "file_path": "x.mp3"},
        {"task_type": "generate_thumbnail", "file_path": "", "params": {"w": 1.0, "z": 10**20}},
        {"task_type": "transcode_video", "file_path": "b.mp4"},
    ],
}


def _foto(cliente):
    leer = {"hash": cliente.hgetall, "list": lambda k: cliente.lrange(k, 0, -1), "set": cliente.smembers,
            "string": cliente.get}
    return {k: (cliente.type(k), leer[cliente.type(k)](k)) for k in cliente.scan_iter("*")}


def _crear(r, monkeypatch, limite):
    r.flushdb()
    monkeypatch.setenv("QUEUE_MAX_DEPTH", str(limite))
    contador = itertools.count()
    monkeypatch.setattr(rutas_casos.uuid, "uuid4", lambda: uuid.UUID(int=next(contador)))
    monkeypatch.setattr(rutas_casos, "now_iso", lambda: "2026-11-11T00:00:00+00:00")
    respuesta = TestClient(main.app).post("/cases", json=CASO)
    assert respuesta.status_code == 201
    return respuesta.json(), _foto(r)


def test_lua_y_pipeline_dejan_el_mismo_estado(r, monkeypatch):
    sin_limite = _crear(r, monkeypatch, 0)
    con_limite = _crear(r, monkeypatch, 1000)
    assert con_limite == sin_limite


@pytest.mark.xfail(strict=True, reason="H4 QA F-24 (preexistente): un case_id que choca con otra clave deja "
                                       "el caso a medias; Lua no revierte los comandos previos al error")
def test_error_a_mitad_del_script_no_deja_rastro(r):
    cliente = TestClient(main.app, raise_server_exceptions=False)
    sub = [{"task_type": "transcode_video", "file_path": "a.mp4"}]
    assert cliente.post("/cases", json={"case_id": "a:subtasks", "subtasks": sub}).status_code == 201
    antes = _foto(r)
    respuesta = cliente.post("/cases", json={"case_id": "a", "subtasks": sub})
    assert respuesta.status_code != 201
    assert _foto(r) == antes
