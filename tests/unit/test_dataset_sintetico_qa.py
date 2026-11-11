import json

import pytest

from scripts.dataset_sintetico import MANIFEST_NAME, main, validate_manifest
from src.adapters.hashing import sha256_de_archivo
from src.domain.dataset_plan import MIN_HEAVY_BYTES
from tests.unit.test_dataset_sintetico import FakeRunner, REDUCED, _guardar, _rows, reduced  # noqa: F401


def test_validar_no_cuenta_dos_veces_la_misma_ruta(reduced):  # noqa: F811
    rows = _rows(reduced)
    _guardar(reduced, rows + [r for r in rows if r["kind"] == "imagen"] * 10)

    problemas = validate_manifest(reduced / MANIFEST_NAME)

    assert any("imagenes: 60 de al menos 300" in p or "duplicad" in p for p in problemas)


def test_validar_reporta_un_heterogeneo_liviano_sin_todos_los_tipos(reduced):  # noqa: F811
    rows = _rows(reduced)
    victima = next(r["case"] for r in rows if r["heterogeneo"] == "liviano")
    _guardar(reduced, [r for r in rows if not (r["case"] == victima and r["kind"] != "texto")])

    problemas = validate_manifest(reduced / MANIFEST_NAME)

    assert any(victima in p for p in problemas)


def test_validar_no_cuenta_como_pesado_un_caso_no_heterogeneo(reduced):  # noqa: F811
    rows = _rows(reduced)
    fila = next(r for r in rows if r["heterogeneo"] == "no")
    archivo = reduced / fila["path"]
    with archivo.open("r+b") as handle:
        handle.truncate(MIN_HEAVY_BYTES)
    fila["bytes"] = MIN_HEAVY_BYTES
    fila["sha256"] = sha256_de_archivo(archivo)
    _guardar(reduced, rows)

    problemas = validate_manifest(reduced / MANIFEST_NAME)

    assert "casos pesados de al menos 200 MiB: 0 de al menos 5" in problemas


@pytest.mark.parametrize("contenido", ['[{"case": "caso-01"', '[{"case": "caso-01", "path": "x"}]'])
def test_validar_reporta_un_manifiesto_corrupto_sin_traza(tmp_path, capsys, contenido):
    (tmp_path / MANIFEST_NAME).write_text(contenido, encoding="utf-8")

    assert main(["--validar", "--out", str(tmp_path)]) == 1
    assert capsys.readouterr().out.strip()


def test_la_cli_rechaza_parametros_negativos(tmp_path):
    params = tmp_path / "p.json"
    params.write_text(json.dumps({**REDUCED, "messages": -5, "images": -3}), encoding="utf-8")

    with pytest.raises((SystemExit, ValueError)):
        main(["--out", str(tmp_path / "o"), "--params", str(params)], runner=FakeRunner())
