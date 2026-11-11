"""Ejecuta el preflight antes de levantar el worker de un nodo."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.preflight import COMPOSE_FILES, ROOT, _compose_config, _node_memory_bytes, validate_config


def main() -> int:
    compose_files = COMPOSE_FILES.copy()
    if "--gpu" in sys.argv[1:]:
        compose_files.append("deploy/docker-compose.worker-gpu.yml")
    try:
        validate_config(_compose_config(compose_files), _node_memory_bytes())
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f"Preflight rechazado; no se inicia Compose: {error}")
        return 1
    command = ["docker", "compose", "--env-file", ".env"]
    for compose_file in compose_files:
        command.extend(["-f", compose_file])
    command.extend(["up", "-d", "--build"])
    return subprocess.run(command, cwd=ROOT).returncode


if __name__ == "__main__":
    raise SystemExit(main())
