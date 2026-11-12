import re
import subprocess
from pathlib import Path
from unittest.mock import Mock

import pytest
import yaml

import scripts.start_worker as start_worker
from scripts.preflight import _node_memory_bytes, compose_files_for, validate_config

COMPOSE_ANALISIS = Path(__file__).resolve().parents[2] / "deploy/docker-compose.analisis.yml"
VALORES = {
    "NODE_NAME": "node-b",
    "NODE_IP": "100.64.0.2",
    "ADMISSION_MARGIN_BYTES": "268435456",
    "WORKER_MEM_LIMIT_TEXT": "2147483648",
    "WORKER_MEM_LIMIT_IMAGE": "2147483648",
    "WORKER_MEM_LIMIT_AUDIO": "2147483648",
    "FOOTPRINT_TEXT_BYTES": "1073741824",
    "FOOTPRINT_IMAGE_BYTES": "1073741824",
    "FOOTPRINT_AUDIO_BYTES": "1073741824",
}


def _compose_de_analisis(valores: dict[str, str]) -> dict:
    texto = COMPOSE_ANALISIS.read_text(encoding="utf-8")
    resuelto = re.sub(r"\$\{(\w+)[^}]*\}", lambda m: valores.get(m[1], ""), texto)
    return yaml.safe_load(resuelto)


def _config(memory=4 * 1024**3, swap=4 * 1024**3):
    return {
        "services": {
            "worker": {
                "hostname": "node-b",
                "environment": {"NODE_NAME": "node-b", "NODE_IP": "100.64.0.2"},
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


def test_preflight_rechaza_node_name_distinto_del_hostname():
    config = _config()
    config["services"]["worker"]["environment"]["NODE_NAME"] = "node-other"

    with pytest.raises(ValueError, match="NODE_NAME"):
        validate_config(config, node_memory=16 * 1024**3)


def test_preflight_suma_limites_de_todos_los_workers():
    config = _config()
    config["services"]["worker-2"] = {
        "hostname": "node-b",
        "environment": {"NODE_NAME": "node-b", "NODE_IP": "100.64.0.2"},
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


def test_preflight_acepta_los_servicios_de_analisis():
    config = _compose_de_analisis(VALORES)

    assert set(config["services"]) == {"worker-texto", "worker-imagen", "worker-audio"}
    validate_config(config, node_memory=16 * 1024**3)


@pytest.mark.parametrize("variable", ["ADMISSION_MARGIN_BYTES", "FOOTPRINT_TEXT_BYTES"])
def test_preflight_rechaza_un_servicio_de_analisis_sin_huella_medida(variable):
    config = _compose_de_analisis({**VALORES, variable: ""})

    with pytest.raises(ValueError, match=variable):
        validate_config(config, node_memory=16 * 1024**3)


def test_preflight_suma_los_limites_de_los_servicios_de_analisis():
    with pytest.raises(ValueError, match="excede"):
        validate_config(_compose_de_analisis(VALORES), node_memory=6 * 1024**3)


def test_compose_files_for_agrega_o_reemplaza_con_el_compose_de_analisis():
    assert compose_files_for([]) == ["deploy/docker-compose.worker.yml"]
    assert compose_files_for(["--analisis"]) == [
        "deploy/docker-compose.worker.yml", "deploy/docker-compose.analisis.yml"]
    assert compose_files_for(["--solo-analisis"]) == ["deploy/docker-compose.analisis.yml"]
