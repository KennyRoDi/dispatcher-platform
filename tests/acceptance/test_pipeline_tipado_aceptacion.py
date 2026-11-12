"""Aceptación del pipeline tipado (F-43, parte 5): caso de cuatro fuentes y tres workers de nodos distintos.

Todo con dobles de modelo y fakeredis: demuestra el cableado y el cierre del caso, no el rendimiento ni la
exactitud de los modelos, y no sustituye la prueba con tres nodos reales.
"""
import json
import socket
from collections import Counter
from datetime import date
from pathlib import Path

import pytest

import src.coordinator.main as main
from src.coordinator import conexion, rutas_casos, rutas_reporte
from src.workers.heartbeat import Heartbeat
from tests.ayudas_pipeline_tipado import FOTO_FALSA, TELEGRAM, VIDEO_FALSO, VOZ_FALSA, WHATSAPP, Pipeline

pytestmark = [pytest.mark.acceptance, pytest.mark.usefixtures("sin_autorizacion")]

EVIDENCIA = Path(__file__).resolve().parents[2] / "docs" / "evidencia"
FUENTES = {"nota.txt": WHATSAPP, "chat.json": TELEGRAM, "foto.jpg": FOTO_FALSA, "voz.mp3": VOZ_FALSA, "clip.mp4": VIDEO_FALSO}


@pytest.fixture
def pipe(tmp_path, monkeypatch):
    pipeline = Pipeline(tmp_path, monkeypatch, conexion, main, rutas_casos, rutas_reporte)
    yield pipeline
    pipeline.cerrar()


def test_caso_completo_registra_el_log_de_punta_a_punta(pipe):
    case_id = pipe.crear_caso(FUENTES)
    antes = pipe.colas()
    workers = [pipe.worker("text", node="nodo-b"), pipe.worker("image", node="nodo-c"), pipe.worker("audio", node="nodo-d")]

    procesadas = pipe.drenar(*workers)

    assert pipe.caso(case_id)["status"] == "completed"
    assert procesadas == 6
    subtareas = pipe.subtareas(case_id)
    hallazgos = pipe.hallazgos(case_id)
    alertas = pipe.alertas()
    reporte = pipe.reporte(case_id)
    hoy = date.today().isoformat()
    lineas = [
        f"# F-43: caso completo de punta a punta ({hoy})",
        "",
        "Generado por `tests/acceptance/test_pipeline_tipado_aceptacion.py` con el coordinador real, tres workers tipados "
        "(`text`, `image`, `audio`), fakeredis, un almacén cifrado en memoria y dobles de modelo. Los hallazgos salen de "
        "dobles: este registro prueba el cableado y el cierre del caso, no la exactitud ni el rendimiento de los modelos "
        "(eso lo miden F-07, F-08 y F-09 con los modelos reales).",
        "",
        f"Caso `{case_id}` con cinco fuentes (texto de WhatsApp, texto de Telegram, imagen, audio y video).",
        "",
        f"Colas tras `POST /cases`: `{json.dumps(antes)}` (el video se expande en una sub-tarea de imagen y otra de audio).",
        "",
        "| Sub-tarea | Fuente | Estado | Worker | Intentos |",
        "|---|---|---|---|---|",
    ]
    lineas += [
        f"| {tipo} | `{ruta}` | {s['status']} | {s['worker_id']} | {s['attempts']} |"
        for (tipo, ruta), s in sorted(subtareas.items())
    ]
    conteo = Counter(h.category for h in hallazgos)
    lineas += [
        "",
        f"Sub-tareas procesadas: {procesadas}. Estado final del caso: `{pipe.caso(case_id)['status']}`.",
        f"Hallazgos en `case:{{id}}:findings`: {len(hallazgos)} ({', '.join(f'{c}: {n}' for c, n in sorted(conteo.items()))}).",
        f"Alertas en orden de emisión: {', '.join(tipo for tipo, _ in alertas)}.",
        f"Reporte consolidado: {len(reporte['hallazgos'])} hallazgos, {len(reporte['categorias'])} categorías, "
        f"{len(reporte['linea_temporal'])} eventos en la línea temporal, {len(reporte['incidencias'])} incidencias.",
    ]
    EVIDENCIA.mkdir(parents=True, exist_ok=True)
    (EVIDENCIA / f"F-43_caso_completo_{hoy}.md").write_text("\n".join(lineas) + "\n", encoding="utf-8")

    assert [tipo for tipo, _ in alertas][-1] == "caso_finalizado"
    assert len(reporte["hallazgos"]) == len(hallazgos)


def test_tres_workers_de_nodos_distintos_aparecen_en_get_workers(pipe, monkeypatch):
    nodos = {"text": "nodo-b", "image": "nodo-c", "audio": "nodo-d"}
    case_id = pipe.crear_caso(FUENTES)
    workers = {kind: pipe.worker(kind, node=nodo) for kind, nodo in nodos.items()}

    pipe.drenar(*workers.values())
    for kind, worker in workers.items():
        monkeypatch.setattr(socket, "gethostname", lambda nombre=nodos[kind]: f"{nombre}.local")
        Heartbeat(
            worker.settings, pipe.redis, worker.stats, worker.stop_event, ffmpeg_info=("test", "none"), processor=None
        ).beat()

    entradas = pipe.client.get("/workers").json()
    assert pipe.caso(case_id)["status"] == "completed"
    assert {e["worker_id"] for e in entradas} == {"w-text", "w-image", "w-audio"}
    assert all(e["alive"] for e in entradas)
    assert {e["hostname"] for e in entradas} == {"nodo-b.local", "nodo-c.local", "nodo-d.local"}
    assert {e["host"] for e in entradas} == set(nodos.values())
    assert {e["queues"] for e in entradas} == set(nodos)
    subtareas = pipe.subtareas(case_id)
    assert {s["worker_id"] for s in subtareas.values()} == {"w-text", "w-image", "w-audio"}
    assert Counter(s["worker_id"] for s in subtareas.values()) == {"w-text": 2, "w-image": 2, "w-audio": 2}
