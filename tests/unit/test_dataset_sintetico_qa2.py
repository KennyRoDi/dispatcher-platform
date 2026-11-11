import os

import pytest

from scripts.dataset_sintetico import MANIFEST_NAME, main, validate_manifest
from tests.unit.test_dataset_sintetico import FakeRunner, _guardar, _rows, _params_file, reduced  # noqa: F401


@pytest.mark.parametrize("valor", ["123", None])
def test_validar_reporta_bytes_que_no_es_entero_sin_traza(reduced, valor):  # noqa: F811
    rows = _rows(reduced)
    rows[0]["bytes"] = valor
    _guardar(reduced, rows)

    problemas = validate_manifest(reduced / MANIFEST_NAME)

    assert any(rows[0]["path"] in p for p in problemas)


def test_validar_reporta_un_case_nulo_sin_traza(reduced):  # noqa: F811
    rows = _rows(reduced)
    rows[0]["case"] = None
    _guardar(reduced, rows)

    problemas = validate_manifest(reduced / MANIFEST_NAME)

    assert any(rows[0]["path"] in p for p in problemas)


@pytest.mark.parametrize("variante", ["./{}", "{}/"])
def test_validar_detecta_duplicados_con_otra_grafia_de_la_ruta(reduced, variante):  # noqa: F811
    rows = _rows(reduced)
    imagen = next(r for r in rows if r["kind"] == "imagen")
    rows.append({**imagen, "path": variante.format(imagen["path"])})
    _guardar(reduced, rows)

    problemas = validate_manifest(reduced / MANIFEST_NAME)

    assert any("duplicad" in p or "ruta invalida" in p for p in problemas)


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignora los permisos")
def test_validar_reporta_un_archivo_ilegible_sin_traza(reduced):  # noqa: F811
    imagen = next(r for r in _rows(reduced) if r["kind"] == "imagen")
    archivo = reduced / imagen["path"]
    archivo.chmod(0)
    try:
        problemas = validate_manifest(reduced / MANIFEST_NAME)
    finally:
        archivo.chmod(0o644)

    assert any(imagen["path"] in p for p in problemas)


def test_validar_rechaza_un_enlace_simbolico_que_sale_del_directorio(reduced, tmp_path):  # noqa: F811
    imagen = next(r for r in _rows(reduced) if r["kind"] == "imagen")
    archivo = reduced / imagen["path"]
    fuera = tmp_path / "fuera.bin"
    fuera.write_bytes(archivo.read_bytes())
    archivo.unlink()
    archivo.symlink_to(fuera)

    problemas = validate_manifest(reduced / MANIFEST_NAME)

    assert any(imagen["path"] in p for p in problemas)


def test_la_cli_informa_un_out_que_es_un_archivo_sin_traza(tmp_path, capsys):
    out = tmp_path / "archivo"
    out.write_text("x", encoding="utf-8")

    try:
        codigo = main(["--out", str(out), "--params", str(_params_file(tmp_path))], runner=FakeRunner())
    except SystemExit as salida:
        codigo = salida.code

    assert codigo not in (0, None)


@pytest.mark.parametrize("campo,valor", [("etiqueta", {"a": 1}), ("duracion_s", [1]), ("case", ["x"])])
def test_validar_reporta_valores_no_escalares_sin_traza(reduced, campo, valor):  # noqa: F811
    rows = _rows(reduced)
    rows[0][campo] = valor
    _guardar(reduced, rows)

    assert any("escalares" in p for p in validate_manifest(reduced / MANIFEST_NAME))


def test_validar_exige_el_documento_de_los_heterogeneos_livianos(reduced):  # noqa: F811
    rows = _rows(reduced)
    victima = next(r["case"] for r in rows if r["heterogeneo"] == "liviano")
    _guardar(reduced, [r for r in rows if not (r["case"] == victima and r["kind"] == "documento")])

    problemas = validate_manifest(reduced / MANIFEST_NAME)

    assert any(victima in p and "documento" in p for p in problemas)
