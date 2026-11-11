import pytest

from scripts.dataset_sintetico import MANIFEST_NAME, main
from tests.unit.test_dataset_sintetico import VIDEO_SUFFIX, FakeRunner, _generate, _params_file


class FailingRunner(FakeRunner):
    def __init__(self, fail_when):
        super().__init__()
        self.fail_when = fail_when

    def __call__(self, args):
        super().__call__(args)
        if self.fail_when(len(self.calls), args[-1]):
            raise RuntimeError("ffmpeg fallo")


def _run_and_swallow(out, tmp_path, runner):
    try:
        _generate(out, tmp_path, runner=runner)
    except Exception:  # noqa: BLE001
        pass


def _files(out):
    return {p for p in out.rglob("*") if p.is_file()}


FALLOS = [
    pytest.param(lambda n, salida: n == 1, id="primer-medio"),
    pytest.param(lambda n, salida: n == 50, id="medio-del-plan"),
    pytest.param(lambda n, salida: salida.endswith(VIDEO_SUFFIX), id="caso-pesado"),
]


@pytest.mark.parametrize("fail_when", FALLOS)
def test_si_la_generacion_falla_se_limpian_los_archivos_de_esa_ejecucion(tmp_path, fail_when):
    out = tmp_path / "out"
    out.mkdir()
    ajeno = out / "notas.txt"
    ajeno.write_text("mio", encoding="utf-8")

    _run_and_swallow(out, tmp_path, FailingRunner(fail_when))

    assert _files(out) == {ajeno}
    assert ajeno.read_text(encoding="utf-8") == "mio"


@pytest.mark.parametrize("fail_when", FALLOS)
def test_si_la_generacion_falla_no_queda_el_manifiesto_previo(tmp_path, fail_when):
    out = tmp_path / "out"
    assert _generate(out, tmp_path) == 0
    assert (out / MANIFEST_NAME).is_file()

    _run_and_swallow(out, tmp_path, FailingRunner(fail_when))

    assert not (out / MANIFEST_NAME).exists()


def test_al_empezar_a_generar_se_borra_el_manifiesto_previo(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    (out / MANIFEST_NAME).write_text("[]", encoding="utf-8")
    existia = []

    class Observador(FakeRunner):
        def __call__(self, args):
            existia.append((out / MANIFEST_NAME).exists())
            super().__call__(args)

    assert _generate(out, tmp_path, runner=Observador()) == 0

    assert existia and not any(existia)


def test_una_generacion_exitosa_conserva_todos_sus_archivos(tmp_path):
    out = tmp_path / "out"

    assert main(["--out", str(out), "--params", str(_params_file(tmp_path))], runner=FakeRunner()) == 0

    assert (out / MANIFEST_NAME).is_file()
    assert len(_files(out)) > 1
