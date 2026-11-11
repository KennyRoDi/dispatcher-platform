import requests
import responses

from scripts import run_load as rl
from scripts import submit_case as sc

URL = "http://coord:8000"


def test_sin_variable_la_sesion_no_lleva_authorization():
    assert "Authorization" not in sc.resolve_session(URL, env={}).headers
    assert "Authorization" not in sc.resolve_session(URL, env={"API_TOKEN": "   "}).headers


def test_con_variable_la_sesion_manda_bearer():
    sesion = sc.resolve_session(URL, env={"API_TOKEN": " abc.def.ghi "})
    assert sesion.headers["Authorization"] == "Bearer abc.def.ghi"


def test_una_sesion_explicita_se_respeta_sin_tocarla():
    propia = requests.Session()
    assert sc.resolve_session(URL, propia, env={"API_TOKEN": "tok"}) is propia
    assert "Authorization" not in propia.headers


@responses.activate
def test_submit_case_con_token_en_el_entorno_envia_la_cabecera(monkeypatch):
    monkeypatch.setenv("API_TOKEN", "tok")
    responses.add(responses.POST, f"{URL}/cases", json={"case_id": "c1"})
    sc.submit_case(URL, [("p/a.jpg", "auto")])
    assert responses.calls[0].request.headers["Authorization"] == "Bearer tok"


@responses.activate
def test_run_load_con_token_en_el_entorno_resuelve_sesion_con_bearer(monkeypatch):
    monkeypatch.setenv("API_TOKEN", "tok")
    assert rl.resolve_session(URL).headers["Authorization"] == "Bearer tok"


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
