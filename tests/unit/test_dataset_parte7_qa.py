import json
import os

import pytest

from scripts.dataset_sintetico import MANIFEST_NAME, _generate as generate_dataset, main, validate_manifest
from src.domain.dataset_plan import DatasetParams, plan_dataset
from tests.unit.test_dataset_parte6_qa import FailingAt
from tests.unit.test_dataset_sintetico import FakeRunner, _generate, _params_file, _rows


def _generated(tmp_path):
    out = tmp_path / "out"
    assert _generate(out, tmp_path) == 0
    return out, _rows(out)


def test_una_ruta_con_sustituto_unicode_suelto_se_reporta_como_problema(tmp_path):
    out, rows = _generated(tmp_path)
    rows[0]["path"] = "caso-01/\ud800x"
    (out / MANIFEST_NAME).write_text(json.dumps(rows), encoding="utf-8")

    problems = validate_manifest(out / MANIFEST_NAME)

    assert any("caso-01" in problem for problem in problems)


@pytest.mark.usefixtures("symlink_capable")
def test_un_out_que_es_un_enlace_roto_se_rechaza_con_error_de_uso(tmp_path):
    out = tmp_path / "roto"
    out.symlink_to(tmp_path / "no-existe")

    with pytest.raises(SystemExit):
        _generate(out, tmp_path)


def test_si_mkdir_falla_a_mitad_de_la_cadena_no_quedan_padres_creados(tmp_path):
    out = tmp_path / "a" / "b" / ("x" * 300)
    with pytest.raises(OSError):
        _generate(out, tmp_path)

    assert not (tmp_path / "a").exists()


def test_un_out_con_punto_punto_conserva_el_error_original_y_no_deja_padres(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(RuntimeError, match="ffmpeg fallo"):
        main(["--out", "./rel/../otro/out", "--params", str(_params_file(tmp_path))], runner=FailingAt(5))

    assert not (tmp_path / "rel").exists()


@pytest.mark.usefixtures("symlink_capable")
def test_rechazar_un_enlace_no_borra_el_manifiesto_previo(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    (out / MANIFEST_NAME).write_text("[]", encoding="utf-8")
    (out / "caso-01").symlink_to(tmp_path)
    with pytest.raises(RuntimeError):
        generate_dataset(plan_dataset(1, DatasetParams()), out, FakeRunner())

    assert (out / MANIFEST_NAME).read_text(encoding="utf-8") == "[]"


def test_un_enlace_ajeno_a_los_casos_dentro_de_out_se_rechaza_sin_tocar_nada(tmp_path):
    outside = tmp_path / "fuera"
    outside.mkdir()
    out = tmp_path / "out"
    out.mkdir()
    (out / "notas").symlink_to(outside)

    with pytest.raises(SystemExit):
        _generate(out, tmp_path)

    assert list(outside.iterdir()) == []
    assert (out / "notas").is_symlink()
