import json
import os

import pytest

from scripts.dataset_sintetico import MANIFEST_NAME, main, validate_manifest
from src.domain.dataset_plan import DatasetParams
from tests.unit.test_dataset_sintetico import FakeRunner, _generate, _params_file, _rows


class FailingAt(FakeRunner):
    def __init__(self, failing_call: int):
        super().__init__()
        self.failing_call = failing_call

    def __call__(self, args):
        super().__call__(args)
        if len(self.calls) == self.failing_call:
            raise RuntimeError("ffmpeg fallo")


def _generated(tmp_path):
    out = tmp_path / "out"
    assert _generate(out, tmp_path) == 0
    return out, _rows(out)


def _rewrite(out, rows):
    (out / MANIFEST_NAME).write_text(json.dumps(rows), encoding="utf-8")


@pytest.mark.xfail(strict=True, reason="QA parte 6: una ruta con NUL hace que el validador termine con ValueError (lstat) en vez de reportar la fila")
def test_una_ruta_con_nul_se_reporta_como_problema(tmp_path):
    out, rows = _generated(tmp_path)
    rows[0]["path"] = "caso-01/a\x00b"
    _rewrite(out, rows)

    problems = validate_manifest(out / MANIFEST_NAME)

    assert any("a\x00b" in problem or "invalida" in problem for problem in problems)


@pytest.mark.xfail(strict=True, reason="QA parte 6: un directorio sin permiso de acceso da PermissionError en _check_row (file.is_file()), solo se capturo la lectura del hash")
@pytest.mark.skipif(os.geteuid() == 0, reason="root ignora los permisos")
def test_un_directorio_sin_permiso_se_reporta_como_problema(tmp_path):
    out, rows = _generated(tmp_path)
    blocked = out / rows[0]["path"].split("/")[0]
    blocked.chmod(0)
    try:
        problems = validate_manifest(out / MANIFEST_NAME)
    finally:
        blocked.chmod(0o755)

    assert any(rows[0]["path"] in problem for problem in problems)


@pytest.mark.xfail(strict=True, reason="QA parte 6: DatasetParams acepta nan, inf y floats; plan_dataset falla despues con TypeError o ValueError opacos")
@pytest.mark.parametrize("field,value", [("cases", float("nan")), ("cases", 1.5), ("messages", float("nan")), ("images", float("inf"))])
def test_los_parametros_no_enteros_se_rechazan_con_valueerror(field, value):
    with pytest.raises(ValueError):
        DatasetParams(**{field: value})


@pytest.mark.xfail(strict=True, reason="QA parte 6: si --out no existia y la generacion falla, solo se borra --out; los padres creados por mkdir(parents=True) quedan")
def test_si_falla_con_out_anidado_no_quedan_directorios_padre_creados(tmp_path):
    out = tmp_path / "a" / "b" / "out"
    with pytest.raises(RuntimeError):
        _generate(out, tmp_path, runner=FailingAt(5))

    assert not (tmp_path / "a").exists()


@pytest.mark.xfail(strict=True, reason="QA parte 6: _produce borra por vacio un directorio de caso que ya existia (vacio) antes de la ejecucion")
def test_si_falla_se_conserva_un_directorio_de_caso_vacio_preexistente(tmp_path):
    out = tmp_path / "out"
    (out / "caso-01").mkdir(parents=True)
    with pytest.raises(RuntimeError):
        _generate(out, tmp_path, runner=FailingAt(1))

    assert (out / "caso-01").is_dir()


@pytest.mark.xfail(strict=True, reason="QA parte 6: con un enlace caso-01 hacia fuera de --out se escribe fuera y la limpieza (rglob sin seguir enlaces) no borra esos archivos tras un fallo")
def test_si_falla_no_quedan_huerfanos_detras_de_un_enlace_preexistente(tmp_path):
    outside = tmp_path / "fuera"
    outside.mkdir()
    out = tmp_path / "out"
    out.mkdir()
    (out / "caso-01").symlink_to(outside)
    with pytest.raises(RuntimeError):
        main(["--out", str(out), "--params", str(_params_file(tmp_path))], runner=FailingAt(20))

    assert list(outside.iterdir()) == []
