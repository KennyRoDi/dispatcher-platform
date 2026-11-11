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


def test_salida_no_sobrescribe_la_muestra_de_entrada(tmp_path):
    sample = _write(tmp_path / "muestra.json", SAMPLE)
    observed = _write(tmp_path / "salidas.json", OBSERVED)

    main(["comparar", "--muestra", sample, "--salidas", observed, "--salida", sample])

    assert json.loads((tmp_path / "muestra.json").read_text(encoding="utf-8")) == SAMPLE


def test_salida_no_sobrescribe_las_salidas_de_entrada(tmp_path):
    sample = _write(tmp_path / "muestra.json", SAMPLE)
    observed = _write(tmp_path / "salidas.json", OBSERVED)

    main(["comparar", "--muestra", sample, "--salidas", observed, "--salida", observed])

    assert json.loads((tmp_path / "salidas.json").read_text(encoding="utf-8")) == OBSERVED


def test_json_con_anidamiento_profundo_es_un_error_controlado(tmp_path, capsys):
    deep = tmp_path / "profundo.json"
    deep.write_text("[" * 100_000 + "]" * 100_000, encoding="utf-8")

    assert main(["procedencia", "--muestra", str(deep)]) == 1
    assert capsys.readouterr().err.startswith("error:")


def test_markdown_no_rompe_la_tabla_con_barra_o_salto_en_la_categoria():
    comparison = Comparison((CategoryScore("a|b\nc", 1, 0, 0, 0),), 1, 1)

    table = render_markdown(comparison).replace("\\|", "").splitlines()
    header_columns = table[0].count("|")

    assert all(line.count("|") == header_columns for line in table[:3])


def test_salida_enlace_simbolico_a_la_muestra_no_la_sobrescribe(tmp_path, capsys):
    sample = _write(tmp_path / "muestra.json", SAMPLE)
    observed = _write(tmp_path / "salidas.json", OBSERVED)
    link = tmp_path / "enlace.md"
    link.symlink_to(sample)

    assert main(["comparar", "--muestra", sample, "--salidas", observed, "--salida", str(link)]) == 1
    assert json.loads((tmp_path / "muestra.json").read_text(encoding="utf-8")) == SAMPLE
    assert capsys.readouterr().err.startswith("error:")


def test_ctrl_c_termina_con_130_sin_traza(tmp_path, monkeypatch, capsys):
    import scripts.dataset_verdad as cli

    def interrupted(args):
        raise KeyboardInterrupt

    monkeypatch.setattr(cli, "_procedencia", interrupted)

    assert main(["procedencia", "--muestra", _write(tmp_path / "m.json", SAMPLE)]) == 130
    assert capsys.readouterr().err == ""
