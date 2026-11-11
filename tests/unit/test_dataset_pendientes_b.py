import dataclasses
import json
import os
import signal
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pytest

from scripts import dataset_sintetico
from scripts.dataset_sintetico import MANIFEST_NAME, main, validate_manifest
from src.adapters import media_generator
from src.adapters.chat_export_generator import export_plan_chats, generate_chat, render_telegram, render_whatsapp
from src.domain import dataset_plan
from src.domain.chat_message import ChatMessage
from src.domain.dataset_plan import DatasetParams, plan_dataset
from tests.unit.test_dataset_parte6_qa import FailingAt
from tests.unit.test_dataset_sintetico import REDUCED, FakeRunner, _generate, _params_file, _rows

COSTA_RICA = timezone(timedelta(hours=-6))


def _mensaje(momento: datetime) -> ChatMessage:
    return ChatMessage(timestamp_utc=momento, sender="Alma", text="hola", source_ref="x")


def test_whatsapp_convierte_a_utc_un_mensaje_con_otra_zona():
    local = datetime(2025, 3, 4, 20, 30, tzinfo=COSTA_RICA)

    assert render_whatsapp([_mensaje(local)]).startswith("5/3/25, 02:30 - ")


def test_telegram_convierte_a_utc_un_mensaje_con_otra_zona():
    local = datetime(2025, 3, 4, 20, 30, tzinfo=COSTA_RICA)

    entrada = json.loads(render_telegram([_mensaje(local)]))["messages"][0]

    assert entrada["date"] == "2025-03-05T02:30:00"
    assert entrada["date_unixtime"] == str(int(local.timestamp()))


def test_export_plan_chats_rechaza_un_nombre_de_caso_que_sale_del_destino(tmp_path):
    plan = plan_dataset(1, DatasetParams(**REDUCED))
    casos = (dataclasses.replace(plan.cases[0], name="../escape"),) + plan.cases[1:]

    with pytest.raises(ValueError, match="nombre de caso"):
        export_plan_chats(dataclasses.replace(plan, cases=casos), tmp_path / "chats")

    assert not (tmp_path / "escape-chat.txt").exists()


@pytest.mark.parametrize("ratio", [-0.5, 1.5, float("nan")])
def test_threat_ratio_fuera_de_rango_da_un_error_claro(ratio):
    with pytest.raises(ValueError, match="threat_ratio"):
        generate_chat(1, 10, threat_ratio=ratio)


def test_export_plan_chats_borra_los_chats_de_ejecuciones_previas(tmp_path):
    plan = plan_dataset(1, DatasetParams(**REDUCED))
    destino = tmp_path / "chats"
    destino.mkdir()
    (destino / "caso-99-chat.txt").write_text("viejo", encoding="utf-8")
    (destino / "caso-01-chat.json").write_text("viejo", encoding="utf-8")
    (destino / "notas.txt").write_text("mio", encoding="utf-8")

    files = export_plan_chats(plan, destino)

    assert {p.name for p in destino.iterdir()} == {p.name for p in files.values()} | {"notas.txt"}


def test_los_minimos_del_validador_son_los_del_dominio_por_nivel():
    assert dataset_sintetico.MIN_LIGHT is dataset_plan.MIN_LIGHT
    assert not hasattr(dataset_sintetico, "MIN_HETEROGENEOUS")


def test_el_validador_no_exige_diez_heterogeneos_en_total(tmp_path):
    out = tmp_path / "out"
    assert _generate(out, tmp_path) == 0

    problemas = validate_manifest(out / MANIFEST_NAME)

    assert not any(p.startswith("casos heterogeneos: ") for p in problemas)
    assert any(p.startswith("casos heterogeneos livianos: ") for p in problemas)


def test_params_acepta_enteros_de_numpy_y_los_guarda_como_int():
    params = DatasetParams(cases=np.int64(40), messages=np.int32(20_000))

    assert type(params.cases) is int and type(params.messages) is int


@pytest.mark.parametrize(
    "campo", ["cases", "messages", "images", "audios", "heavy_bytes"]
)
def test_params_tiene_un_tope_superior(campo):
    tope = getattr(dataset_plan, f"MAX_{ {'cases': 'CASES', 'messages': 'MESSAGES', 'images': 'IMAGES', 'audios': 'AUDIOS', 'heavy_bytes': 'HEAVY_BYTES'}[campo] }")

    DatasetParams(**{campo: tope})
    with pytest.raises(ValueError, match=campo):
        DatasetParams(**{campo: tope + 1})


def test_la_cli_rechaza_un_params_fuera_de_tope_sin_traza(tmp_path):
    with pytest.raises(SystemExit) as salida:
        _generate(tmp_path / "out", tmp_path, params=_params_file(tmp_path, cases=10**9))

    assert salida.value.code == 2
    assert not (tmp_path / "out").exists()


@pytest.mark.parametrize(
    "campo, valor",
    [("heterogeneo", "medio"), ("kind", "holograma"), ("positivo", "si")],
)
def test_el_validador_reporta_valores_fuera_de_dominio(tmp_path, campo, valor):
    out = tmp_path / "out"
    assert _generate(out, tmp_path) == 0
    rows = _rows(out)
    rows[0][campo] = valor
    (out / MANIFEST_NAME).write_text(json.dumps(rows), encoding="utf-8")

    problemas = validate_manifest(out / MANIFEST_NAME)

    assert any(repr(valor) in p for p in problemas)


def test_un_cierre_de_ffmpeg_ausente_da_un_error_claro(monkeypatch):
    def sin_ffmpeg(args, **kwargs):
        raise FileNotFoundError(2, "No such file or directory", "ffmpeg")

    monkeypatch.setattr(subprocess, "run", sin_ffmpeg)

    with pytest.raises(RuntimeError, match="ffmpeg no esta instalado"):
        media_generator.run_ffmpeg(["ffmpeg"])


def test_la_cli_informa_el_timeout_de_ffmpeg_y_limpia(tmp_path, capsys):
    def lento(args):
        raise subprocess.TimeoutExpired(args, 300)

    out = tmp_path / "a" / "out"
    with pytest.raises(SystemExit) as salida:
        _generate(out, tmp_path, runner=lento)

    assert salida.value.code == 1
    assert "ffmpeg" in capsys.readouterr().err
    assert not (tmp_path / "a").exists()


def test_los_enlaces_en_out_se_rechazan_con_error_de_uso_y_sin_traza(tmp_path, capsys):
    out = tmp_path / "out"
    out.mkdir()
    (out / "notas").symlink_to(tmp_path)

    with pytest.raises(SystemExit) as salida:
        _generate(out, tmp_path)

    assert salida.value.code == 2
    assert "enlaces simbolicos" in capsys.readouterr().err


class IntrusoAl(FailingAt):
    def __init__(self, failing_call: int, intruso: Path):
        super().__init__(failing_call)
        self.intruso = intruso

    def __call__(self, args):
        if len(self.calls) + 1 == self.failing_call:
            self.intruso.write_text("ajeno", encoding="utf-8")
        super().__call__(args)


def test_un_padre_creado_que_dejo_de_estar_vacio_no_tapa_el_error_original(tmp_path):
    out = tmp_path / "a" / "out"

    with pytest.raises(RuntimeError, match="ffmpeg fallo"):
        _generate(out, tmp_path, runner=IntrusoAl(5, tmp_path / "a" / "intruso.txt"))

    assert not out.exists()
    assert (tmp_path / "a" / "intruso.txt").exists()


class TermAl(FakeRunner):
    def __call__(self, args):
        super().__call__(args)
        if len(self.calls) == 5:
            os.kill(os.getpid(), signal.SIGTERM)


def test_sigterm_sale_con_143_limpia_lo_creado_y_restaura_el_manejador(tmp_path):
    previo = signal.getsignal(signal.SIGTERM)
    out = tmp_path / "a" / "out"

    with pytest.raises(SystemExit) as salida:
        _generate(out, tmp_path, runner=TermAl())

    assert salida.value.code == 143
    assert not (tmp_path / "a").exists()
    assert signal.getsignal(signal.SIGTERM) is previo
