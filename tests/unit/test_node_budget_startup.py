from __future__ import annotations

import importlib
from pathlib import Path

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[2]


def _worker_compose() -> dict:
    return yaml.safe_load(
        (ROOT / "deploy/docker-compose.worker.yml").read_text(encoding="utf-8")
    )["services"]["worker"]


def test_worker_compose_configura_memoria_sin_swap():
    worker = _worker_compose()

    assert worker.get("mem_limit")
    assert worker.get("memswap_limit") == worker["mem_limit"]


def test_worker_compose_configura_replicas_explicitas():
    worker = _worker_compose()

    replicas = (worker.get("deploy") or {}).get("replicas")
    assert isinstance(replicas, int) and replicas > 0


@pytest.mark.parametrize("compose_file", [
    "deploy/docker-compose.worker.yml",
    "deploy/docker-compose.worker-gpu.yml",
])
def test_compose_no_permite_memoria_ausente_o_invalida(compose_file):
    services = yaml.safe_load((ROOT / compose_file).read_text(encoding="utf-8"))["services"]
    worker = services["worker"]

    assert worker.get("mem_limit"), f"{compose_file} debe exigir el limite por configuracion"
    assert worker.get("memswap_limit") == worker["mem_limit"]


def test_preflight_cli_rechaza_configuracion_invalida():
    cli = importlib.import_module("scripts.check_node_budget")

    assert cli.main([
        "--node-memory", "1000",
        "--worker-limit", "0",
        "--reserve", "100",
    ]) != 0


def test_arranque_no_invoca_compose_up_si_falla_el_preflight(monkeypatch):
    startup = importlib.import_module("scripts.start_worker")
    commands: list[list[str]] = []

    def run(command, **kwargs):
        commands.append(list(command))
        if command[:3] == ["docker", "compose", "config"]:
            return {"worker_limits": [900], "node_memory": 1000, "reserve": 200}
        raise AssertionError(f"no se esperaba ejecutar: {command}")

    with pytest.raises((ValueError, SystemExit)):
        startup.start(run=run)

    assert not any(command[:3] == ["docker", "compose", "up"] for command in commands)
