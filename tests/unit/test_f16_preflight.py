import subprocess
from unittest.mock import Mock

import pytest

import scripts.start_worker as start_worker
from scripts.preflight import _node_memory_bytes, validate_config


def _config(memory=4 * 1024**3, swap=4 * 1024**3):
    return {
        "services": {
            "worker": {
                "hostname": "node-b",
                "environment": {"NODE_IP": "100.64.0.2"},
                "mem_limit": memory,
                "memswap_limit": swap,
            }
        }
    }


def test_preflight_acepta_limite_dentro_del_presupuesto():
    validate_config(_config(), node_memory=16 * 1024**3)


def test_preflight_acepta_limites_normalizados_como_bytes_por_compose():
    config = _config(memory="4294967296", swap="4294967296")

    validate_config(config, node_memory=16 * 1024**3)


def test_preflight_acepta_node_ip_ipv6():
    config = _config()
    config["services"]["worker"]["environment"]["NODE_IP"] = "fd7a:115c:a1e0::1"

    validate_config(config, node_memory=16 * 1024**3)


@pytest.mark.parametrize(
    ("config", "node_memory"),
    [
        (_config(memory=None), 16 * 1024**3),
        (_config(memory=4 * 1024**3, swap=8 * 1024**3), 16 * 1024**3),
        (_config(memory="unknown"), 16 * 1024**3),
        (_config(memory="-1"), 16 * 1024**3),
        (_config(memory="4294967296", swap="8589934592"), 16 * 1024**3),
        (_config(), 4 * 1024**3),
        ({"services": {"worker": {"environment": {"NODE_IP": "100.64.0.2"}}}}, 16 * 1024**3),
        ({"services": {"worker": {"hostname": "node-b", "mem_limit": 1}}}, 16 * 1024**3),
    ],
)
def test_preflight_rechaza_configuracion_o_presupuesto_invalido(config, node_memory):
    with pytest.raises(ValueError):
        validate_config(config, node_memory=node_memory)


def test_preflight_rechaza_node_ip_que_no_es_una_direccion_ip():
    config = _config()
    config["services"]["worker"]["environment"]["NODE_IP"] = "not-an-ip"

    with pytest.raises(ValueError):
        validate_config(config, node_memory=16 * 1024**3)


def test_preflight_suma_limites_de_todos_los_workers():
    config = _config()
    config["services"]["worker-2"] = {
        "hostname": "node-b",
        "environment": {"NODE_IP": "100.64.0.2"},
        "mem_limit": 4 * 1024**3,
        "memswap_limit": 4 * 1024**3,
    }
    with pytest.raises(ValueError, match="excede"):
        validate_config(config, node_memory=8 * 1024**3)


def test_start_worker_no_invoca_compose_si_el_presupuesto_excede_ram(monkeypatch):
    compose_run = Mock()
    monkeypatch.setattr(start_worker, "_compose_config", lambda files: _config())
    monkeypatch.setattr(start_worker, "_node_memory_bytes", lambda: 4 * 1024**3)
    monkeypatch.setattr(start_worker.subprocess, "run", compose_run)

    assert start_worker.main() == 1
    compose_run.assert_not_called()


def test_memoria_del_nodo_se_lee_del_daemon_docker(monkeypatch):
    run = Mock(return_value=subprocess.CompletedProcess([], 0, stdout="17179869184\n"))
    monkeypatch.setattr("scripts.preflight.subprocess.run", run)

    assert _node_memory_bytes() == 16 * 1024**3
    run.assert_called_once_with(
        ["docker", "info", "--format", "{{.MemTotal}}"],
        cwd=start_worker.ROOT,
        check=True,
        capture_output=True,
        text=True,
    )


@pytest.mark.parametrize("output", ["", "unknown", "-1", "0", "１２"])
def test_memoria_del_daemon_rechaza_salida_ausente_o_invalida(monkeypatch, output):
    run = Mock(return_value=subprocess.CompletedProcess([], 0, stdout=output))
    monkeypatch.setattr("scripts.preflight.subprocess.run", run)

    with pytest.raises(ValueError, match="MemTotal"):
        _node_memory_bytes()


def test_memoria_del_daemon_propaga_error_de_docker(monkeypatch):
    run = Mock(side_effect=subprocess.CalledProcessError(1, ["docker", "info"]))
    monkeypatch.setattr("scripts.preflight.subprocess.run", run)

    with pytest.raises(subprocess.CalledProcessError):
        _node_memory_bytes()
