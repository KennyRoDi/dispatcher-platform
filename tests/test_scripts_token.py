from argparse import Namespace

import requests
import responses

from scripts import run_load as rl
from scripts import submit_case as sc

URL = "http://coord:8000"


def test_sin_variable_se_usa_requests_como_hasta_ahora():
    assert sc.sesion_autenticada({}) is requests
    assert sc.sesion_autenticada({"API_TOKEN": "   "}) is requests


def test_con_variable_la_sesion_manda_bearer():
    sesion = sc.sesion_autenticada({"API_TOKEN": " abc.def.ghi "})
    assert sesion.headers["Authorization"] == "Bearer abc.def.ghi"


@responses.activate
def test_submit_case_con_sesion_autenticada_envia_la_cabecera():
    responses.add(responses.POST, f"{URL}/cases", json={"case_id": "c1"})
    sesion = sc.sesion_autenticada({"API_TOKEN": "tok"})
    sc.submit_case(URL, [("p/a.jpg", "auto")], sesion)
    assert responses.calls[0].request.headers["Authorization"] == "Bearer tok"


@responses.activate
def test_main_de_run_load_pasa_la_sesion_con_token(monkeypatch):
    capturado = {}

    def falso_run_load(args, settings, session=requests, **_):
        capturado["session"] = session
        return 0, "ruta.md"

    monkeypatch.setattr(rl, "run_load", falso_run_load)
    monkeypatch.setenv("API_TOKEN", "tok")
    assert rl.main([]) == 0
    assert capturado["session"].headers["Authorization"] == "Bearer tok"


def test_main_de_run_load_sin_variable_usa_requests(monkeypatch):
    capturado = {}
    monkeypatch.setattr(
        rl, "run_load", lambda args, settings, session=requests, **_: capturado.update(s=session) or (0, "r")
    )
    monkeypatch.delenv("API_TOKEN", raising=False)
    rl.main([])
    assert capturado["s"] is requests


@responses.activate
def test_main_de_submit_case_envia_el_token_en_cada_llamada(tmp_path, monkeypatch, capsys):
    (tmp_path / "a.mp4").write_bytes(b"x")
    monkeypatch.setenv("COORDINATOR_URL", URL)
    monkeypatch.setenv("API_TOKEN", "tok-secreto")
    responses.add(responses.POST, f"{URL}/cases", json={"case_id": "c1"})
    responses.add(
        responses.GET,
        f"{URL}/cases/c1",
        json={"case": {"status": "completed", "total_subtasks": 1}, "subtasks": []},
    )
    responses.add(responses.GET, f"{URL}/cases/c1/report", json={})
    sc.main(["--dir", str(tmp_path), "--no-upload", "--poll", "0"])
    llamadas = responses.calls
    assert len(llamadas) >= 2
    assert all(c.request.headers["Authorization"] == "Bearer tok-secreto" for c in llamadas)
    assert "tok-secreto" not in capsys.readouterr().out
