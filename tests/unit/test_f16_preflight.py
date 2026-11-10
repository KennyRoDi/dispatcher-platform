import pytest

from scripts.preflight import validate_config


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


@pytest.mark.parametrize(
    ("config", "node_memory"),
    [
        (_config(memory=None), 16 * 1024**3),
        (_config(memory=4 * 1024**3, swap=8 * 1024**3), 16 * 1024**3),
        (_config(), 4 * 1024**3),
        ({"services": {"worker": {"environment": {"NODE_IP": "100.64.0.2"}}}}, 16 * 1024**3),
        ({"services": {"worker": {"hostname": "node-b", "mem_limit": 1}}}, 16 * 1024**3),
    ],
)
def test_preflight_rechaza_configuracion_o_presupuesto_invalido(config, node_memory):
    with pytest.raises(ValueError):
        validate_config(config, node_memory=node_memory)


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
