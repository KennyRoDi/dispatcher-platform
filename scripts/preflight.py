"""Valida el presupuesto de memoria antes de iniciar workers con Compose."""

import ipaddress
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.domain.node_budget import validate_node_budget


COMPOSE_FILES = ["deploy/docker-compose.worker.yml"]
ANALYSIS_COMPOSE = "deploy/docker-compose.analisis.yml"
GPU_COMPOSE = "deploy/docker-compose.worker-gpu.yml"
ANALYSIS_KINDS = ("text", "image", "audio")
GIB = 1024**3


def compose_files_for(argv: list[str]) -> list[str]:
    files = [] if "--solo-analisis" in argv else COMPOSE_FILES.copy()
    if "--analisis" in argv or "--solo-analisis" in argv:
        files.append(ANALYSIS_COMPOSE)
    if "--gpu" in argv:
        files.append(GPU_COMPOSE)
    return files


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


def _memory_limit_bytes(value: object, service_name: str, variable: str) -> int:
    if isinstance(value, int) and not isinstance(value, bool):
        limit = value
    elif isinstance(value, str) and value.isascii() and value.isdigit():
        limit = int(value)
    else:
        raise ValueError(f"Servicio {service_name} no tiene {variable} válido")
    if limit <= 0:
        raise ValueError(f"Servicio {service_name} no tiene {variable} válido")
    return limit


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


def _validate_analysis_footprints(name: str, environment: dict) -> None:
    kind = environment.get("WORKER_KIND")
    if kind is None:
        return
    if kind not in ANALYSIS_KINDS:
        raise ValueError(f"Servicio {name} tiene un WORKER_KIND inválido")
    for variable in ("ADMISSION_MARGIN_BYTES", f"FOOTPRINT_{kind.upper()}_BYTES"):
        _memory_limit_bytes(environment.get(variable), name, variable)


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
            hostname = service.get("hostname")
            node_name = environment.get("NODE_NAME")
            if not hostname or not node_name:
                raise ValueError(f"Servicio {name} no define NODE_NAME como hostname")
            if hostname != node_name:
                raise ValueError(f"NODE_NAME debe coincidir con hostname en el servicio {name}")
            for variable in ("NODE_IP",):
                value = environment.get(variable)
                if not value:
                    raise ValueError(f"{variable} es obligatorio para el worker")
                if variable == "NODE_IP":
                    try:
                        ipaddress.ip_address(value)
                    except ValueError as error:
                        raise ValueError("NODE_IP debe ser una dirección IPv4 o IPv6 válida") from error
            _validate_analysis_footprints(name, environment)
        else:
            continue
        memory = _memory_limit_bytes(service.get("mem_limit"), name, "mem_limit")
        swap = _memory_limit_bytes(service.get("memswap_limit"), name, "memswap_limit")
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
    try:
        config = _compose_config(compose_files_for(sys.argv[1:]))
        memory = _node_memory_bytes()
        validate_config(config, memory)
    except (OSError, ValueError, subprocess.CalledProcessError, json.JSONDecodeError) as error:
        print(f"Preflight rechazado: {error}")
        return 1
    print("Preflight aprobado: presupuesto de memoria dentro de la RAM del nodo")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
