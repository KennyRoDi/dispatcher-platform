import json

import pytest

from scripts.dataset_verdad import main
from src.adapters.dataset_truth_files import render_markdown
from src.domain.ground_truth import CategoryScore, Comparison

SAMPLE = [{"path": "a.png", "origen": "sintetico", "licencia": "MIT", "esperadas": ["objetos"]}]
OBSERVED = [{"path": "a.png", "categorias": ["objetos"]}]


def _write(path, data):
    path.write_text(json.dumps(data), encoding="utf-8")
    return str(path)


@pytest.mark.xfail(
    strict=True,
    reason="QA F-04 parte 3: --salida igual a --muestra sobrescribe la muestra etiquetada sin aviso (dataset_verdad.py:46)",
)
def test_salida_no_sobrescribe_la_muestra_de_entrada(tmp_path):
    sample = _write(tmp_path / "muestra.json", SAMPLE)
    observed = _write(tmp_path / "salidas.json", OBSERVED)

    main(["comparar", "--muestra", sample, "--salidas", observed, "--salida", sample])

    assert json.loads((tmp_path / "muestra.json").read_text(encoding="utf-8")) == SAMPLE


@pytest.mark.xfail(
    strict=True,
    reason="QA F-04 parte 3: --salida igual a --salidas destruye las salidas del analisis (dataset_verdad.py:46)",
)
def test_salida_no_sobrescribe_las_salidas_de_entrada(tmp_path):
    sample = _write(tmp_path / "muestra.json", SAMPLE)
    observed = _write(tmp_path / "salidas.json", OBSERVED)

    main(["comparar", "--muestra", sample, "--salidas", observed, "--salida", observed])

    assert json.loads((tmp_path / "salidas.json").read_text(encoding="utf-8")) == OBSERVED


@pytest.mark.xfail(
    strict=True,
    raises=RecursionError,
    reason="QA F-04 parte 3: JSON con anidamiento profundo lanza RecursionError con traza en vez de 'error: ...' y codigo 1 (dataset_truth_files.py:79)",
)
def test_json_con_anidamiento_profundo_es_un_error_controlado(tmp_path, capsys):
    deep = tmp_path / "profundo.json"
    deep.write_text("[" * 100_000 + "]" * 100_000, encoding="utf-8")

    assert main(["procedencia", "--muestra", str(deep)]) == 1
    assert capsys.readouterr().err.startswith("error:")


@pytest.mark.xfail(
    strict=True,
    reason="QA F-04 parte 3: render_markdown no escapa '|' ni saltos de linea en la categoria y rompe la tabla (dataset_truth_files.py:57)",
)
def test_markdown_no_rompe_la_tabla_con_barra_o_salto_en_la_categoria():
    comparison = Comparison((CategoryScore("a|b\nc", 1, 0, 0, 0),), 1, 1)

    table = render_markdown(comparison).replace("\\|", "").splitlines()
    header_columns = table[0].count("|")

    assert all(line.count("|") == header_columns for line in table[:3])
