import json

import pytest

from scripts.dataset_sintetico import MANIFEST_NAME, main, validate_manifest
from tests.unit.test_dataset_sintetico import REDUCED, FakeRunner, _guardar, _rows, reduced  # noqa: F401


class ForbiddenRunner:
    def __call__(self, args):
        raise AssertionError("no debe generar nada con parametros invalidos")


def _corromper_chat(out, sufijo, contenido):
    fila = next(r for r in _rows(out) if r["kind"] == "texto" and r["path"].endswith(sufijo))
    (out / fila["path"]).write_bytes(contenido)
    return fila["path"]


@pytest.mark.parametrize(
    "sufijo,contenido",
    [(".txt", b"\xff\xfe\x00 no es utf-8"), (".json", b'{"messages": [1, 2'), (".json", b'{"sin_mensajes": []}')],
)
def test_validar_reporta_un_chat_ilegible_sin_traza(reduced, capsys, sufijo, contenido):  # noqa: F811
    ruta = _corromper_chat(reduced, sufijo, contenido)

    problemas = validate_manifest(reduced / MANIFEST_NAME)
    assert any(ruta in p and "mensajes" in p for p in problemas)

    assert main(["--validar", "--out", str(reduced)], runner=ForbiddenRunner()) == 1
    assert ruta in capsys.readouterr().out


@pytest.mark.parametrize("contenido", ['{"a": 1}', "[1, 2]", "", "\xff"])
def test_validar_reporta_un_manifiesto_que_no_es_una_lista_de_filas(tmp_path, capsys, contenido):
    (tmp_path / MANIFEST_NAME).write_text(contenido, encoding="utf-8", errors="surrogateescape")

    assert main(["--validar", "--out", str(tmp_path)], runner=ForbiddenRunner()) == 1
    assert capsys.readouterr().out.strip()


@pytest.mark.parametrize("ruta", ["../fuera", "/etc/passwd", r"C:\fuera", r"..\fuera", 5])
def test_validar_rechaza_rutas_que_salen_del_directorio(reduced, ruta):  # noqa: F811
    rows = _rows(reduced)
    rows[0]["path"] = ruta
    _guardar(reduced, rows)

    assert any("ruta invalida" in p for p in validate_manifest(reduced / MANIFEST_NAME))


def test_validar_reporta_las_rutas_duplicadas_una_vez_por_fila_repetida(reduced):  # noqa: F811
    rows = _rows(reduced)
    _guardar(reduced, rows + [rows[0]] * 3)

    problemas = [p for p in validate_manifest(reduced / MANIFEST_NAME) if "duplicada" in p]

    assert problemas == [f"{rows[0]['path']}: fila duplicada"] * 3


def test_validar_exige_los_tipos_de_los_heterogeneos_pesados(reduced):  # noqa: F811
    rows = _rows(reduced)
    victima = next(r["case"] for r in rows if r["heterogeneo"] == "pesado")
    _guardar(reduced, [r for r in rows if not (r["case"] == victima and r["kind"] == "video")])

    problemas = validate_manifest(reduced / MANIFEST_NAME)

    assert any(victima in p and "video" in p for p in problemas)


def test_un_dataset_coherente_no_reporta_tipos_faltantes(reduced):  # noqa: F811
    assert not any("sin los tipos" in p for p in validate_manifest(reduced / MANIFEST_NAME))


@pytest.mark.parametrize(
    "cambio",
    [
        {"images": "300"},
        {"images": 1.5},
        {"images": True},
        {"audios": None},
        {"messages": -1},
        {"heavy_bytes": -1},
        {"cases": 0},
        {"imagenes": 300},
    ],
)
def test_la_cli_rechaza_params_invalidos_antes_de_generar(tmp_path, capsys, cambio):
    params = tmp_path / "p.json"
    params.write_text(json.dumps({**REDUCED, **cambio}), encoding="utf-8")
    out = tmp_path / "out"

    with pytest.raises(SystemExit) as salida:
        main(["--out", str(out), "--params", str(params)], runner=ForbiddenRunner())

    assert salida.value.code != 0
    assert "--params" in capsys.readouterr().err
    assert not out.exists()


@pytest.mark.parametrize("contenido", ["[1, 2]", "no es json", '"texto"'])
def test_la_cli_rechaza_un_params_que_no_es_un_objeto_json(tmp_path, contenido):
    params = tmp_path / "p.json"
    params.write_text(contenido, encoding="utf-8")

    with pytest.raises(SystemExit) as salida:
        main(["--out", str(tmp_path / "out"), "--params", str(params)], runner=ForbiddenRunner())

    assert salida.value.code != 0
    assert not (tmp_path / "out").exists()


def test_la_cli_rechaza_un_params_inexistente(tmp_path):
    with pytest.raises(SystemExit) as salida:
        main(["--out", str(tmp_path / "out"), "--params", str(tmp_path / "no.json")], runner=ForbiddenRunner())

    assert salida.value.code != 0
