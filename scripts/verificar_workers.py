import argparse
import re
import sys
from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parents[1]
COMPOSES = ["deploy/docker-compose.worker.yml", "deploy/docker-compose.local.yml"]
UID_FIJO = "10001"
DIRECTORIO_TRABAJO = "/scratch"


def _es_worker(nombre: str, servicio: dict) -> bool:
    comando = servicio.get("command")
    texto = " ".join(comando) if isinstance(comando, list) else str(comando or "")
    # Sin `command`, la imagen del worker arranca el worker por defecto.
    hereda_cmd = "Dockerfile.worker" in str(servicio.get("build")) and not comando
    return "worker" in nombre.lower() or "worker_node" in texto or hereda_cmd


def _entorno(servicio: dict) -> dict:
    entorno = servicio.get("environment") or {}
    if isinstance(entorno, dict):
        return entorno
    return dict(entrada.partition("=")[::2] for entrada in entorno)


def _destino_volumen(volumen) -> tuple[str, str]:
    if isinstance(volumen, dict):
        return str(volumen.get("source", "")), str(volumen.get("target", ""))
    origen, _, resto = str(volumen).partition(":")
    return origen, resto.split(":")[0]


def _tmpfs_tiene_tamano(servicio: dict) -> bool:
    tmpfs = servicio.get("tmpfs") or []
    entradas = [tmpfs] if isinstance(tmpfs, str) else tmpfs
    return any(
        str(entrada).split(":")[0] == "/tmp" and "size=" in str(entrada) for entrada in entradas
    )


def _incumplimientos_worker(nombre: str, servicio: dict, volumenes: dict) -> list[str]:
    problemas = []
    if not re.fullmatch(r"[1-9]\d*(:\d+)?", str(servicio.get("user", ""))):
        problemas.append(f"{nombre}: user debe ser un UID numerico distinto de 0")
    if servicio.get("read_only") is not True:
        problemas.append(f"{nombre}: read_only debe ser true")
    if "ALL" not in [str(c).upper() for c in servicio.get("cap_drop") or []]:
        problemas.append(f"{nombre}: cap_drop debe incluir ALL")
    if servicio.get("cap_add"):
        problemas.append(f"{nombre}: cap_add no se permite")
    if "no-new-privileges:true" not in (servicio.get("security_opt") or []):
        problemas.append(f"{nombre}: security_opt debe incluir no-new-privileges:true")
    origenes = [o for o, destino in map(_destino_volumen, servicio.get("volumes") or [])
                if destino == DIRECTORIO_TRABAJO]
    if not origenes:
        problemas.append(f"{nombre}: falta un volumen en {DIRECTORIO_TRABAJO}")
    elif origenes[0] not in volumenes:
        problemas.append(f"{nombre}: el volumen {origenes[0]!r} de {DIRECTORIO_TRABAJO} no esta declarado")
    if not _tmpfs_tiene_tamano(servicio):
        problemas.append(f"{nombre}: falta tmpfs en /tmp con size=")
    if _entorno(servicio).get("WORK_DIR") != DIRECTORIO_TRABAJO:
        problemas.append(f"{nombre}: WORK_DIR debe ser {DIRECTORIO_TRABAJO}")
    return problemas


def incumplimientos_compose(compose: dict) -> list[str]:
    servicios = compose.get("services") or {}
    workers = {n: s for n, s in servicios.items() if _es_worker(n, s)}
    if not workers:
        return ["no hay servicios worker en el compose"]
    volumenes = compose.get("volumes") or {}
    return [p for n, s in workers.items() for p in _incumplimientos_worker(n, s, volumenes)]


def incumplimientos_dockerfile(texto: str) -> list[str]:
    problemas = []
    usuarios = re.findall(r"^\s*USER\s+(\S+)", texto, re.MULTILINE | re.IGNORECASE)
    if not usuarios or not re.fullmatch(r"[1-9]\d*(:\d+)?", usuarios[-1]):
        problemas.append("Dockerfile: la ultima instruccion USER debe ser un UID numerico distinto de 0")
    elif usuarios[-1].split(":")[0] != UID_FIJO:
        problemas.append(f"Dockerfile: USER debe usar el UID fijo {UID_FIJO}")
    if not re.search(rf"(?:--uid|-u)[ =]{UID_FIJO}\b", texto):
        problemas.append(f"Dockerfile: useradd debe fijar el UID {UID_FIJO}")
    if not re.search(rf"^\s*ENV\b.*\bWORK_DIR={DIRECTORIO_TRABAJO}\s*$", texto, re.MULTILINE):
        problemas.append(f"Dockerfile: WORK_DIR debe ser {DIRECTORIO_TRABAJO}")
    return problemas


def main(argv: list[str] | None = None) -> int:
    analizador = argparse.ArgumentParser(description="Verifica que los workers no tengan privilegios.")
    analizador.add_argument("--compose", action="append", type=Path)
    analizador.add_argument("--dockerfile", type=Path)
    args = analizador.parse_args(argv)
    composes = args.compose or [RAIZ / ruta for ruta in COMPOSES]
    dockerfile = args.dockerfile or RAIZ / "Dockerfile.worker"

    problemas = []
    try:
        for ruta in composes:
            contenido = yaml.safe_load(ruta.read_text(encoding="utf-8")) or {}
            problemas += [f"{ruta.name}: {p}" for p in incumplimientos_compose(contenido)]
        problemas += incumplimientos_dockerfile(dockerfile.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        problemas.append(f"no se pudo leer: {error}")
    for problema in problemas:
        print(problema, file=sys.stderr)
    return 1 if problemas else 0


if __name__ == "__main__":
    sys.exit(main())
