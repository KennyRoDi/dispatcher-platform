"""Valida el presupuesto de memoria antes de iniciar workers con Compose."""

import ipaddress
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.domain.node_budget import validate_node_budget


COMPOSE_FILES = ["deploy/docker-compose.worker.yml"]
GIB = 1024**3


def _node_memory_bytes() -> int:
    result = subprocess.run(
        ["docker", "info", "--format", "{{.MemTotal}}"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    output = result.stdout.strip()
    if not output.isascii() or not output.isdigit() or int(output) <= 0:
        raise ValueError("Docker no devolvió un MemTotal válido en bytes")
    return int(output)


def _reserve_bytes(node_memory: int) -> int:
    fifteen_percent_ceil = (node_memory * 15 + 99) // 100
    return max(GIB, fifteen_percent_ceil)


def _compose_config(compose_files: list[str]) -> dict:
    command = ["docker", "compose", "--env-file", ".env"]
    for compose_file in compose_files:
        command.extend(["-f", compose_file])
    command.extend(["config", "--format", "json"])
    result = subprocess.run(
        command,
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def validate_config(config: dict, node_memory: int) -> None:
    services = config.get("services")
    if not isinstance(services, dict) or not services:
        raise ValueError("Compose no contiene servicios")
    limits = []
    for name, service in services.items():
        if not isinstance(service, dict):
            raise ValueError(f"Servicio {name} inválido")
        environment = service.get("environment") or {}
        if "worker" in name.lower():
            if not service.get("hostname"):
                raise ValueError(f"Servicio {name} no define NODE_NAME como hostname")
            for variable in ("NODE_NAME", "NODE_IP"):
                value = service.get("hostname") if variable == "NODE_NAME" else environment.get(variable)
                if not value:
                    raise ValueError(f"{variable} es obligatorio para el worker")
                if variable == "NODE_IP":
                    try:
                        ipaddress.ip_address(value)
                    except ValueError as error:
                        raise ValueError("NODE_IP debe ser una dirección IPv4 o IPv6 válida") from error
        else:
            continue
        memory = service.get("mem_limit")
        swap = service.get("memswap_limit")
        if not isinstance(memory, int) or memory <= 0:
            raise ValueError(f"Servicio {name} no tiene mem_limit válido")
        if memory != swap:
            raise ValueError(f"Servicio {name} permite swap o tiene límites distintos")
        limits.append(memory)
    if not limits:
        raise ValueError("Compose no contiene servicios worker con límites")
    validate_node_budget(
        worker_limits=limits,
        node_memory=node_memory,
        reserve=_reserve_bytes(node_memory),
    )


def main() -> int:
    compose_files = COMPOSE_FILES.copy()
    if "--gpu" in os.sys.argv[1:]:
        compose_files.append("deploy/docker-compose.worker-gpu.yml")
    try:
        config = _compose_config(compose_files)
        memory = _node_memory_bytes()
        validate_config(config, memory)
    except (OSError, ValueError, subprocess.CalledProcessError, json.JSONDecodeError) as error:
        print(f"Preflight rechazado: {error}")
        return 1
    print("Preflight aprobado: presupuesto de memoria dentro de la RAM del nodo")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
