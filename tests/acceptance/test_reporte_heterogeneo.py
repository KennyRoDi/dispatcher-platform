import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import src.coordinator.main as main
from src.coordinator import rutas_reporte
from src.domain.consolidated_report import CaseInfo, CaseSource
from src.domain.finding import EvidenceRef, Finding, Severity
from tests.dobles import FakeCaseCatalog, FakeClock, FakeFindingStore, FakeObjectStore

pytestmark = pytest.mark.acceptance

SHA_TEXTO = "1" * 64
SHA_IMAGEN = "2" * 64
SHA_AUDIO = "3" * 64
INICIO = datetime(2026, 11, 3, 8, 0, tzinfo=timezone.utc)
SECCIONES = ["hallazgos", "categorias", "linea_temporal", "incidencias"]


def caso_heterogeneo():
    fuentes = (
        CaseSource(SHA_TEXTO, "chat-sintetico.txt", "texto", "completed"),
        CaseSource(SHA_IMAGEN, "imagen-sintetica.png", "imagen", "completed"),
        CaseSource(SHA_AUDIO, "audio-sintetico.wav", "audio", "completed"),
    )
    return CaseInfo("caso-heterogeneo", "completed", INICIO, INICIO + timedelta(minutes=12), fuentes)


def hallazgos_heterogeneos():
    def hallazgo(categoria, severidad, sha, posicion, detalle=""):
        return Finding(categoria, severidad, 0.9, EvidenceRef(sha, posicion), detalle)

    return [
        hallazgo("amenaza", Severity.ALTA, SHA_TEXTO, "mensajes 3", "3 2026-11-03T09:00:00+00:00 wa-3"),
        hallazgo("ofensivo", Severity.MEDIA, SHA_TEXTO, "mensajes 7", "7 2026-11-03T09:04:00+00:00 wa-7"),
        hallazgo("tema", Severity.BAJA, SHA_TEXTO, "mensajes 0-49"),
        hallazgo("objeto", Severity.MEDIA, SHA_IMAGEN, "caja 10,20,110,220"),
        hallazgo("transcripcion", Severity.MEDIA, SHA_AUDIO, "segmento 2 t=1.00-4.50s", "texto sintetico"),
    ]


def test_reporte_de_caso_heterogeneo_sintetico():
    hallazgos = FakeFindingStore()
    hallazgos.add("caso-heterogeneo", hallazgos_heterogeneos())
    almacen = FakeObjectStore()
    almacen.objetos.update({SHA_TEXTO: b"x", SHA_IMAGEN: b"x", SHA_AUDIO: b"x"})
    reloj = FakeClock(INICIO + timedelta(hours=2))
    main.app.dependency_overrides[rutas_reporte.obtener_hallazgos] = lambda: hallazgos
    main.app.dependency_overrides[rutas_reporte.obtener_catalogo] = lambda: FakeCaseCatalog([caso_heterogeneo()])
    main.app.dependency_overrides[rutas_reporte.obtener_almacen] = lambda: almacen
    main.app.dependency_overrides[rutas_reporte.obtener_reloj] = lambda: reloj
    try:
        respuesta = TestClient(main.app).get("/cases/caso-heterogeneo/consolidated-report")
    finally:
        main.app.dependency_overrides.clear()

    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert all(seccion in datos for seccion in SECCIONES)
    assert {c["categoria"] for c in datos["categorias"]} == {"amenaza", "ofensivo", "tema", "objeto", "transcripcion"}
    assert [e["categoria"] for e in datos["linea_temporal"]] == ["amenaza", "ofensivo"]
    assert {e["categoria"] for e in datos["sin_marca_absoluta"]} == {"objeto", "transcripcion"}
    fuentes = {f["fuente"]["tipo"] for h in datos["hallazgos"] for f in h["evidencia"]}
    assert fuentes == {"texto", "imagen", "audio"}
    assert [i["tipo"] for i in datos["incidencias"]] == ["severidad_alta"]
    salida = os.environ.get("F13_EJEMPLO_JSON")
    if salida:
        Path(salida).write_text(json.dumps(datos, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
