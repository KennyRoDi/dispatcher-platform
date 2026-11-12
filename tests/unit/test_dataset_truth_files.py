import os
import hashlib
import json
from pathlib import Path

import pytest

from scripts.dataset_sintetico import MANIFEST_FIELDS, build_manifest
from src.adapters.dataset_truth_files import (
    read_manifest_records,
    read_observed,
    read_sample_records,
    read_sample_truth,
    render_markdown,
    render_text,
    sample_from_manifest,
)
from src.domain.dataset_plan import DatasetParams, plan_dataset
from src.domain.ground_truth import CategoryScore, Comparison, GroundTruthItem, ObservedItem
from src.domain.provenance import SourceRecord, validate_provenance

REDUCED = DatasetParams(
    cases=8,
    light_heterogeneous=2,
    heavy_heterogeneous=2,
    messages=200,
    images=60,
    audios=24,
    heavy_bytes=1024,
)
VIDEO_SUFFIX = ".mpg"


class DobleDeEjecutor:
    def __call__(self, args: list[str]) -> None:
        output = Path(args[-1])
        output.parent.mkdir(parents=True, exist_ok=True)
        if output.suffix == VIDEO_SUFFIX:
            output.write_bytes(b"\0" * 2048)
            return
        output.write_bytes(hashlib.sha256(" ".join(args[:-1]).encode()).digest())


def _write(tmp_path: Path, content, name: str = "datos.json") -> Path:
    path = tmp_path / name
    path.write_text(content if isinstance(content, str) else json.dumps(content), encoding="utf-8")
    return path


def _manifest_row(path="imagenes/objetos_001.png", **overrides) -> dict:
    row = {name: None for name in MANIFEST_FIELDS}
    row.update(case="caso-01", kind="imagen", path=path, bytes=10, origen="sintetico", licencia="MIT")
    return {**row, **overrides}


def _image_row(path, etiqueta, categoria) -> dict:
    return _manifest_row(path, etiqueta=etiqueta, categoria=categoria, positivo=etiqueta == "positivo")


def _sample_row(path="imagenes/objetos_001.png", **overrides) -> dict:
    return {"path": path, "kind": "imagen", "origen": "sintetico", "licencia": "MIT", "esperadas": ["objetos"], **overrides}


def test_lee_registros_de_procedencia_del_manifiesto(tmp_path):
    rows = [_manifest_row("a.png"), _manifest_row("b.png", origen="propio", licencia="CC-BY-4.0")]

    records = read_manifest_records(_write(tmp_path, rows))

    assert records == [SourceRecord("a.png", "sintetico", "MIT"), SourceRecord("b.png", "propio", "CC-BY-4.0")]


def test_lee_registros_de_procedencia_de_la_muestra(tmp_path):
    sample = [_sample_row("a.png"), _sample_row("b.png", origen="publico", licencia="CC0-1.0")]

    records = read_sample_records(_write(tmp_path, sample))

    assert records == [SourceRecord("a.png", "sintetico", "MIT"), SourceRecord("b.png", "publico", "CC0-1.0")]


@pytest.mark.parametrize("reader", [read_manifest_records, read_sample_records])
def test_origen_o_licencia_ausentes_o_nulos_se_leen_como_none(tmp_path, reader):
    sample = [{"path": "a.png", "kind": "imagen", "esperadas": []}, _sample_row("b.png", origen=None, licencia=None)]

    records = reader(_write(tmp_path, sample))

    assert records == [SourceRecord("a.png", None, None), SourceRecord("b.png", None, None)]
    assert len(validate_provenance(records)) == 4


@pytest.mark.parametrize("reader", [read_manifest_records, read_sample_records])
@pytest.mark.parametrize("field", ["origen", "licencia"])
@pytest.mark.parametrize("value", [5, 1.5, True, ["MIT"], {"id": "MIT"}])
def test_origen_o_licencia_que_no_son_texto_dan_value_error_con_la_ruta(tmp_path, reader, field, value):
    path = _write(tmp_path, [_sample_row("fuente-rara.png", **{field: value})])

    with pytest.raises(ValueError, match="fuente-rara.png"):
        reader(path)


def test_lee_la_verdad_de_la_muestra(tmp_path):
    sample = [_sample_row("a.png", esperadas=["objetos", "personas", "objetos"]), _sample_row("b.png", esperadas=[])]

    truth = read_sample_truth(_write(tmp_path, sample))

    assert truth == [
        GroundTruthItem("a.png", frozenset({"objetos", "personas"})),
        GroundTruthItem("b.png", frozenset()),
    ]


def test_lee_las_salidas_del_analisis(tmp_path):
    outputs = [{"path": "a.png", "categorias": ["objetos"]}, {"path": "b.png", "categorias": []}]

    observed = read_observed(_write(tmp_path, outputs))

    assert observed == [ObservedItem("a.png", frozenset({"objetos"})), ObservedItem("b.png", frozenset())]


@pytest.mark.parametrize(
    ("reader", "valid_row"),
    [
        (read_manifest_records, _manifest_row("a.png")),
        (read_sample_records, _sample_row("a.png")),
        (read_sample_truth, _sample_row("a.png")),
        (read_observed, {"path": "a.png", "categorias": []}),
    ],
)
@pytest.mark.parametrize("path", [pytest.param("/etc/passwd", marks=pytest.mark.skipif(os.name == "nt", reason="en Windows una ruta con / inicial no es absoluta")), "../escape.png", "imagenes/../../escape.png", "a\x00b.png", 7, None])
def test_lectores_rechazan_rutas_peligrosas(tmp_path, reader, valid_row, path):
    with pytest.raises(ValueError):
        reader(_write(tmp_path, [{**valid_row, "path": path}]))


@pytest.mark.parametrize(
    "reader",
    [read_manifest_records, read_sample_records, read_sample_truth, read_observed],
)
@pytest.mark.parametrize(
    "content",
    [{"path": "a.png"}, "texto", 3, None, ["a.png"], [[]], [{"kind": "imagen"}]],
)
def test_lectores_rechazan_formatos_invalidos(tmp_path, reader, content):
    with pytest.raises(ValueError):
        reader(_write(tmp_path, content))


@pytest.mark.parametrize("reader", [read_manifest_records, read_sample_records, read_sample_truth, read_observed])
def test_lectores_rechazan_json_malformado_con_value_error(tmp_path, reader):
    with pytest.raises(ValueError):
        reader(_write(tmp_path, '[{"path": "a.png",'))


@pytest.mark.parametrize("reader", [read_manifest_records, read_sample_records, read_sample_truth, read_observed])
def test_lectores_rechazan_rutas_inexistentes(tmp_path, reader):
    with pytest.raises((OSError, ValueError)):
        reader(tmp_path / "no-existe.json")


@pytest.mark.parametrize("bad", ["objetos", [1], [["objetos"]], [None], {"objetos": 1}, None, 5])
def test_lector_de_la_verdad_rechaza_esperadas_que_no_son_lista_de_texto(tmp_path, bad):
    with pytest.raises(ValueError):
        read_sample_truth(_write(tmp_path, [_sample_row("a.png", esperadas=bad)]))


def test_lector_de_la_verdad_rechaza_muestra_sin_esperadas(tmp_path):
    row = {key: value for key, value in _sample_row("a.png").items() if key != "esperadas"}

    with pytest.raises(ValueError):
        read_sample_truth(_write(tmp_path, [row]))


@pytest.mark.parametrize("bad", ["objetos", [1], [None], {"objetos": 1}, None, 5])
def test_lector_de_salidas_rechaza_categorias_que_no_son_lista_de_texto(tmp_path, bad):
    with pytest.raises(ValueError):
        read_observed(_write(tmp_path, [{"path": "a.png", "categorias": bad}]))


def test_sample_from_manifest_solo_convierte_imagenes_con_etiqueta():
    rows = [
        _image_row("imagenes/objetos_001.png", "positivo", "objetos"),
        _image_row("imagenes/objetos_002.png", "neutro", "objetos"),
        _image_row("imagenes/paisajes_001.png", "positivo", "paisajes"),
        _manifest_row("chats/caso-01.txt", kind="texto"),
        _manifest_row("audios/a.mp3", kind="audio", etiqueta="tono"),
        _manifest_row("videos/v.mpg", kind="video"),
        _manifest_row("documentos/d.txt", kind="documento"),
        _manifest_row("imagenes/sin_etiqueta.png", categoria="objetos"),
        _manifest_row("imagenes/sin_categoria.png", etiqueta="positivo"),
    ]

    sample = sample_from_manifest(rows)

    assert [row["path"] for row in sample] == [
        "imagenes/objetos_001.png",
        "imagenes/objetos_002.png",
        "imagenes/paisajes_001.png",
    ]
    assert [row["esperadas"] for row in sample] == [["objetos"], [], ["paisajes"]]
    assert {row["kind"] for row in sample} == {"imagen"}


def test_sample_from_manifest_conserva_origen_y_licencia():
    rows = [_image_row("a.png", "positivo", "objetos")]
    rows[0].update(origen="propio", licencia="CC-BY-4.0")

    [row] = sample_from_manifest(rows)

    assert (row["origen"], row["licencia"]) == ("propio", "CC-BY-4.0")


def test_la_muestra_derivada_se_lee_con_los_lectores_de_la_muestra(tmp_path):
    rows = [_image_row("a.png", "positivo", "objetos"), _image_row("b.png", "neutro", "paisajes")]
    path = _write(tmp_path, sample_from_manifest(rows))

    assert read_sample_truth(path) == [
        GroundTruthItem("a.png", frozenset({"objetos"})),
        GroundTruthItem("b.png", frozenset()),
    ]
    assert read_sample_records(path) == [SourceRecord("a.png", "sintetico", "MIT"), SourceRecord("b.png", "sintetico", "MIT")]


def test_acepta_el_manifiesto_que_genera_f03(tmp_path):
    out = tmp_path / "dataset"
    rows = build_manifest(plan_dataset(1, REDUCED), out, DobleDeEjecutor())
    manifest = _write(tmp_path, rows, "manifest.json")

    records = read_manifest_records(manifest)

    assert len(records) == len(rows)
    assert validate_provenance(records) == []
    assert all(set(row) == set(MANIFEST_FIELDS) for row in rows)


def _comparison() -> Comparison:
    scores = (
        CategoryScore("objetos", tp=1, fp=1, fn=1, tn=1),
        CategoryScore("paisajes", tp=0, fp=0, fn=1, tn=3),
    )
    return Comparison(scores, total=4, exact_matches=2)


def test_render_text_muestra_aciertos_errores_y_tamano_de_la_muestra():
    text = render_text(_comparison())

    assert "aciertos" in text.lower()
    assert "errores" in text.lower()
    assert "exactitud" in text.lower()
    objetos = next(line for line in text.splitlines() if "objetos" in line)
    paisajes = next(line for line in text.splitlines() if "paisajes" in line)
    assert "n/d" in paisajes
    assert "n/d" not in objetos
    assert "4" in text


def test_render_markdown_es_una_tabla_con_una_fila_por_categoria():
    markdown = render_markdown(_comparison())

    table = [line for line in markdown.splitlines() if line.startswith("|")]
    assert len(table) >= 4
    assert set(table[1].replace("|", "").replace(" ", "").replace(":", "")) == {"-"}
    assert "aciertos" in table[0].lower() and "errores" in table[0].lower()
    assert any(row.startswith("| objetos") for row in table[2:])
    assert any(row.startswith("| paisajes") and "n/d" in row for row in table[2:])
    assert "exactitud" in markdown.lower()

