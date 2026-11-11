from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]


def _compose_services(relative_path: str) -> dict:
    path = ROOT / relative_path
    return yaml.safe_load(path.read_text(encoding="utf-8"))["services"]


def _effective_worker(compose_paths: list[str]) -> dict:
    worker = {}
    for compose_path in compose_paths:
        services = _compose_services(compose_path)
        worker.update(services["worker"])
    return worker


def test_worker_compose_declara_limites_de_memoria_iguales_sin_swap():
    worker = _effective_worker(["deploy/docker-compose.worker.yml"])

    memory_limit = worker.get("mem_limit")
    memory_and_swap_limit = worker.get("memswap_limit")
    assert memory_limit not in (None, "")
    assert memory_and_swap_limit not in (None, "")
    assert memory_and_swap_limit == memory_limit


def test_worker_compose_gpu_efectivo_declara_limites_de_memoria_iguales():
    worker = _effective_worker([
        "deploy/docker-compose.worker.yml",
        "deploy/docker-compose.worker-gpu.yml",
    ])

    memory_limit = worker.get("mem_limit")
    memory_and_swap_limit = worker.get("memswap_limit")
    assert memory_limit not in (None, "")
    assert memory_and_swap_limit not in (None, "")
    assert memory_and_swap_limit == memory_limit
