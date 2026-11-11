import json
from pathlib import Path

import pytest

from scripts.dataset_verdad import main
from src.adapters.dataset_truth_files import render_markdown, render_text
from src.domain.ground_truth import GroundTruthItem, ObservedItem, compare


def _write(tmp_path: Path, content, name: str) -> Path:
    path = tmp_path / name
    path.write_text(content if isinstance(content, str) else json.dumps(content), encoding="utf-8")
    return path


def _sample_row(path, esperadas, origen="sintetico", licencia="MIT") -> dict:
    return {"path": path, "kind": "imagen", "origen": origen, "licencia": licencia, "esperadas": esperadas}


def _sample() -> list[dict]:
    return [
        _sample_row("a.png", ["objetos"]),
        _sample_row("b.png", ["objetos"]),
        _sample_row("c.png", ["paisajes"]),
        _sample_row("d.png", []),
    ]


def _outputs() -> list[dict]:
    return [
        {"path": "a.png", "categorias": ["objetos"]},
        {"path": "b.png", "categorias": []},
        {"path": "c.png", "categorias": ["objetos"]},
        {"path": "d.png", "categorias": []},
    ]


def _expected_comparison():
    truth = [
        GroundTruthItem("a.png", frozenset({"objetos"})),
        GroundTruthItem("b.png", frozenset({"objetos"})),
        GroundTruthItem("c.png", frozenset({"paisajes"})),
        GroundTruthItem("d.png", frozenset()),
    ]
    observed = [
        ObservedItem("a.png", frozenset({"objetos"})),
        ObservedItem("b.png", frozenset()),
        ObservedItem("c.png", frozenset({"objetos"})),
        ObservedItem("d.png", frozenset()),
    ]
    return compare(truth, observed)


def _compare(tmp_path, sample=None, outputs=None, *extra) -> list[str]:
    muestra = _write(tmp_path, _sample() if sample is None else sample, "muestra.json")
    salidas = _write(tmp_path, _outputs() if outputs is None else outputs, "salidas.json")
    return ["comparar", "--muestra", str(muestra), "--salidas", str(salidas), *extra]


def test_cli_procedencia_termina_en_0_si_todo_cumple(tmp_path, capsys):
    manifest = _write(tmp_path, _sample(), "manifest.json")

    assert main(["procedencia", "--manifiesto", str(manifest)]) == 0
    assert main(["procedencia", "--muestra", str(manifest)]) == 0
    assert capsys.readouterr().out.strip()


def test_cli_procedencia_termina_en_1_con_fuente_sin_licencia(tmp_path, capsys):
    sample = _sample() + [_sample_row("sin-lic.png", [], licencia=None), _sample_row("en-blanco.png", [], licencia="  ")]
    muestra = _write(tmp_path, sample, "muestra.json")

    code = main(["procedencia", "--muestra", str(muestra)])

    out = capsys.readouterr().out
    assert code == 1
    assert "sin-lic.png" in out
    assert "en-blanco.png" in out
    assert "a.png" not in out


def test_cli_procedencia_sobre_el_manifiesto_reporta_origen_no_admitido(tmp_path, capsys):
    manifest = [{"case": "caso-01", "kind": "imagen", "path": "x.png", "origen": "real", "licencia": "MIT"}]

    code = main(["procedencia", "--manifiesto", str(_write(tmp_path, manifest, "manifest.json"))])

    assert code == 1
    assert "x.png" in capsys.readouterr().out


def test_cli_procedencia_exige_exactamente_una_entrada(tmp_path):
    archivo = str(_write(tmp_path, _sample(), "muestra.json"))

    with pytest.raises(SystemExit) as sin_entrada:
        main(["procedencia"])
    with pytest.raises(SystemExit) as dos_entradas:
        main(["procedencia", "--manifiesto", archivo, "--muestra", archivo])

    assert sin_entrada.value.code == 2
    assert dos_entradas.value.code == 2


def test_cli_sin_subcomando_o_con_uno_desconocido_sale_con_2():
    for argv in ([], ["inventado"]):
        with pytest.raises(SystemExit) as error:
            main(argv)
        assert error.value.code == 2


@pytest.mark.parametrize("argv", [["procedencia", "--manifiesto"], ["comparar", "--muestra", "m.json"]])
def test_cli_con_argumentos_incompletos_sale_con_2(argv):
    with pytest.raises(SystemExit) as error:
        main(argv)

    assert error.value.code == 2


def test_cli_procedencia_con_ruta_inexistente_termina_en_1_y_nombra_la_ruta(tmp_path, capsys):
    ausente = tmp_path / "no-existe.json"

    code = main(["procedencia", "--manifiesto", str(ausente)])

    captured = capsys.readouterr()
    assert code == 1
    assert "no-existe.json" in captured.out + captured.err


def test_cli_procedencia_con_json_malformado_termina_en_1_sin_traza(tmp_path, capsys):
    broken = _write(tmp_path, '[{"path": "a.png",', "roto.json")

    code = main(["procedencia", "--muestra", str(broken)])

    captured = capsys.readouterr()
    assert code == 1
    assert "roto.json" in captured.out + captured.err
    assert "Traceback" not in captured.out + captured.err


def test_cli_procedencia_con_origen_que_no_es_texto_termina_en_1(tmp_path, capsys):
    sample = [_sample_row("rara.png", [], origen=5)]

    code = main(["procedencia", "--muestra", str(_write(tmp_path, sample, "muestra.json"))])

    captured = capsys.readouterr()
    assert code == 1
    assert "rara.png" in captured.out + captured.err


def test_cli_comparar_imprime_la_tabla_por_categoria_y_termina_en_0(tmp_path, capsys):
    code = main(_compare(tmp_path))

    out = capsys.readouterr().out
    assert code == 0
    assert render_text(_expected_comparison()) in out
    assert "objetos" in out and "paisajes" in out


def test_cli_comparar_con_formato_markdown(tmp_path, capsys):
    code = main(_compare(tmp_path, None, None, "--formato", "markdown"))

    out = capsys.readouterr().out
    assert code == 0
    assert render_markdown(_expected_comparison()) in out


def test_cli_comparar_rechaza_un_formato_desconocido(tmp_path):
    with pytest.raises(SystemExit) as error:
        main(_compare(tmp_path, None, None, "--formato", "html"))

    assert error.value.code == 2


def test_cli_comparar_escribe_solo_en_salida(tmp_path):
    destino = tmp_path / "resultado" / "tabla.md"
    destino.parent.mkdir()

    code = main(_compare(tmp_path, None, None, "--formato", "markdown", "--salida", str(destino)))

    assert code == 0
    assert render_markdown(_expected_comparison()) in destino.read_text(encoding="utf-8")
    assert sorted(path.name for path in tmp_path.iterdir()) == ["muestra.json", "resultado", "salidas.json"]
    assert sorted(path.name for path in destino.parent.iterdir()) == ["tabla.md"]


def test_cli_comparar_no_calcula_si_la_muestra_falla_procedencia(tmp_path, capsys):
    sample = _sample() + [_sample_row("sin-lic.png", [], licencia=None)]
    outputs = _outputs() + [{"path": "sin-lic.png", "categorias": []}]
    destino = tmp_path / "tabla.txt"

    code = main(_compare(tmp_path, sample, outputs, "--salida", str(destino)))

    out = capsys.readouterr().out
    assert code == 1
    assert "sin-lic.png" in out
    assert "objetos" not in out
    assert "exactitud" not in out.lower()
    assert not destino.exists()


def test_cli_comparar_con_origen_no_admitido_no_calcula(tmp_path, capsys):
    sample = [_sample_row("a.png", ["objetos"], origen="tercero")]
    outputs = [{"path": "a.png", "categorias": ["objetos"]}]

    code = main(_compare(tmp_path, sample, outputs))

    out = capsys.readouterr().out
    assert code == 1
    assert "a.png" in out
    assert "exactitud" not in out.lower()


def test_cli_comparar_no_lee_las_salidas_si_falla_procedencia(tmp_path, capsys):
    sample = [_sample_row("a.png", [], licencia=None)]
    muestra = _write(tmp_path, sample, "muestra.json")

    code = main(["comparar", "--muestra", str(muestra), "--salidas", str(tmp_path / "no-existe.json")])

    assert code == 1
    assert "a.png" in capsys.readouterr().out


@pytest.mark.parametrize(
    ("sample", "outputs"),
    [
        (_sample(), _outputs()[:-1]),
        (_sample()[:-1], _outputs()),
        (_sample() + [_sample_row("a.png", [])], _outputs()),
        (_sample(), _outputs() + [{"path": "a.png", "categorias": []}]),
    ],
    ids=["elemento_sin_salida", "salida_sin_etiqueta", "etiqueta_repetida", "salida_repetida"],
)
def test_cli_comparar_con_datos_incompletos_termina_en_1_sin_traza(tmp_path, capsys, sample, outputs):
    code = main(_compare(tmp_path, sample, outputs))

    captured = capsys.readouterr()
    assert code == 1
    assert captured.out + captured.err
    assert "Traceback" not in captured.out + captured.err
    assert "exactitud" not in captured.out.lower()


def test_cli_comparar_con_muestra_vacia_termina_en_1(tmp_path, capsys):
    code = main(_compare(tmp_path, [], []))

    assert code == 1
    assert "Traceback" not in capsys.readouterr().err


def test_cli_comparar_con_salidas_inexistentes_termina_en_1(tmp_path, capsys):
    muestra = _write(tmp_path, _sample(), "muestra.json")

    code = main(["comparar", "--muestra", str(muestra), "--salidas", str(tmp_path / "ausente.json")])

    captured = capsys.readouterr()
    assert code == 1
    assert "ausente.json" in captured.out + captured.err


def test_cli_comparar_con_salidas_malformadas_termina_en_1(tmp_path, capsys):
    muestra = _write(tmp_path, _sample(), "muestra.json")
    salidas = _write(tmp_path, "[{", "salidas.json")

    code = main(["comparar", "--muestra", str(muestra), "--salidas", str(salidas)])

    assert code == 1
    assert "Traceback" not in capsys.readouterr().err


def test_cli_comparar_con_rutas_peligrosas_termina_en_1(tmp_path, capsys):
    sample = [_sample_row("../escape.png", ["objetos"])]
    outputs = [{"path": "../escape.png", "categorias": ["objetos"]}]

    code = main(_compare(tmp_path, sample, outputs))

    assert code == 1
    assert "exactitud" not in capsys.readouterr().out.lower()
