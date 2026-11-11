import re
import subprocess
from dataclasses import replace
from pathlib import Path

import pytest

from src.adapters.document_generator import LICENSE_NAME, ORIGIN, generate_documents
from src.adapters import media_generator
from src.domain.dataset_plan import DatasetParams, plan_dataset

DATO_REAL = re.compile(r"@|https?://|www\.|\d{7,}")
SUFFIXES = {".txt", ".md"}
PARAMS = DatasetParams(
    cases=8, light_heterogeneous=3, heavy_heterogeneous=2, messages=200, images=60, audios=24, heavy_bytes=1024
)


@pytest.fixture
def plan():
    return plan_dataset(7, PARAMS)


def _livianos(plan):
    return {c.name for c in plan.cases if c.heterogeneo == "liviano"}


def _contenido(files):
    return {f.path.name: f.path.read_bytes() for f in files}


def test_genera_documentos_solo_para_los_casos_heterogeneos_livianos(plan, tmp_path):
    files = generate_documents(plan, tmp_path)

    assert {f.case for f in files} == _livianos(plan)
    assert all(f.kind == "documento" for f in files)


def test_los_documentos_quedan_dentro_de_out_dir_y_su_caso(plan, tmp_path):
    files = generate_documents(plan, tmp_path)

    for f in files:
        assert f.path.is_file() and f.path.stat().st_size > 0
        assert f.path.suffix in SUFFIXES
        assert f.path.resolve().parent == (tmp_path / f.case).resolve()


def test_los_documentos_declaran_origen_licencia_y_semilla(plan, tmp_path):
    files = generate_documents(plan, tmp_path)

    assert ORIGIN == "sintetico"
    assert LICENSE_NAME == media_generator.LICENSE_NAME == "MIT"
    assert files and all(f.origen == ORIGIN and f.licencia == LICENSE_NAME and f.semilla == 7 for f in files)


def test_los_documentos_son_utf8_validos_sin_datos_reales(plan, tmp_path):
    for f in generate_documents(plan, tmp_path):
        texto = f.path.read_bytes().decode("utf-8")
        assert texto.strip()
        assert not DATO_REAL.search(texto)


def test_la_misma_semilla_produce_los_mismos_documentos(plan, tmp_path):
    primero = generate_documents(plan, tmp_path / "a")
    segundo = generate_documents(plan_dataset(7, PARAMS), tmp_path / "b")

    assert _contenido(primero) == _contenido(segundo)
    assert [f.path.relative_to(tmp_path / "a") for f in primero] == [f.path.relative_to(tmp_path / "b") for f in segundo]


def test_semillas_distintas_producen_documentos_distintos(plan, tmp_path):
    primero = generate_documents(plan, tmp_path / "a")
    segundo = generate_documents(plan_dataset(8, PARAMS), tmp_path / "b")

    assert sorted(_contenido(primero).values()) != sorted(_contenido(segundo).values())


def test_no_usa_ffmpeg_ni_subprocesos(plan, tmp_path, monkeypatch):
    def prohibido(*args, **kwargs):
        raise AssertionError("el generador de documentos no ejecuta procesos")

    monkeypatch.setattr(subprocess, "run", prohibido)
    monkeypatch.setattr(subprocess, "Popen", prohibido)

    assert generate_documents(plan, tmp_path)


def test_un_plan_sin_casos_livianos_no_escribe_nada(tmp_path):
    plan = plan_dataset(7, replace(PARAMS, light_heterogeneous=0))

    assert generate_documents(plan, tmp_path) == []
    assert list(tmp_path.rglob("*")) == []


@pytest.mark.parametrize("nombre", ["../escape", "a/../../escape", "sub/caso"])
def test_un_nombre_de_caso_que_escapa_se_rechaza_sin_escribir_fuera(plan, tmp_path, nombre):
    destino = tmp_path / "out"
    mala = replace(plan, cases=(replace(plan.cases[0], name=nombre),))

    with pytest.raises(ValueError):
        generate_documents(mala, destino)

    assert not (tmp_path / "escape").exists()
    assert not [p for p in tmp_path.rglob("*") if p.is_file()]


def test_un_nombre_de_caso_absoluto_se_rechaza_sin_escribir_fuera(plan, tmp_path):
    fuera = tmp_path / "fuera"
    mala = replace(plan, cases=(replace(plan.cases[0], name=str(fuera)),))

    with pytest.raises(ValueError):
        generate_documents(mala, tmp_path / "out")

    assert not fuera.exists()
