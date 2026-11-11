"""Genera JWT_SECRET, WORKER_TOKEN y API_TOKEN y los escribe en un .env sin imprimir ningún valor."""
from __future__ import annotations

import argparse
import secrets
import sys
from collections.abc import Sequence
from pathlib import Path

from src.adapters.jwt_tokens import UtcClock, issue_token
from src.application.ports import Clock
from src.domain.rbac import Role

MINUTOS_POR_DIA = 1440


def _leer(ruta: Path) -> list[str]:
    return ruta.read_text(encoding="utf-8").splitlines() if ruta.exists() else []


def _valor(lineas: list[str], nombre: str) -> str | None:
    for linea in lineas:
        clave, separador, valor = linea.partition("=")
        if separador and clave.strip() == nombre:
            return valor.strip() or None
    return None


def _escribir(ruta: Path, valores: dict[str, str]) -> None:
    lineas = _leer(ruta)
    pendientes = dict(valores)
    for indice, linea in enumerate(lineas):
        clave = linea.partition("=")[0].strip()
        if "=" in linea and clave in pendientes:
            lineas[indice] = f"{clave}={pendientes.pop(clave)}"
    lineas.extend(f"{clave}={valor}" for clave, valor in pendientes.items())
    ruta.write_text("\n".join(lineas) + "\n", encoding="utf-8")
    try:
        ruta.chmod(0o600)
    except OSError:
        pass


def generar(
    destino: Path, *, dias: int, rotar: bool, solo_worker: Path | None, clock: Clock
) -> list[str]:
    existente = _valor(_leer(destino), "JWT_SECRET")
    secreto = existente if existente and not rotar else secrets.token_hex(32)
    minutos = dias * MINUTOS_POR_DIA
    worker = issue_token(secreto, role=Role.SERVICIO, subject="worker", clock=clock, minutes=minutos)
    api = issue_token(secreto, role=Role.ADMINISTRADOR, subject="demo-admin", clock=clock, minutes=minutos)
    _escribir(destino, {"JWT_SECRET": secreto, "WORKER_TOKEN": worker, "API_TOKEN": api})
    escritos = ["JWT_SECRET", "WORKER_TOKEN", "API_TOKEN"]
    if solo_worker is not None:
        _escribir(solo_worker, {"WORKER_TOKEN": worker})
    return escritos


def _dias_positivos(valor: str) -> int:
    try:
        dias = int(valor)
    except ValueError:
        raise argparse.ArgumentTypeError(f"no es un entero: {valor!r}") from None
    if dias < 1:
        raise argparse.ArgumentTypeError("debe ser al menos 1")
    return dias


def main(argv: Sequence[str] | None = None, clock: Clock | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Escribe JWT_SECRET, WORKER_TOKEN (rol servicio) y API_TOKEN (rol administrador) en un .env."
    )
    parser.add_argument("--env", type=Path, default=Path(".env"), help="archivo a crear o actualizar")
    parser.add_argument("--dias", type=_dias_positivos, default=30, help="vigencia de los tokens")
    parser.add_argument("--rotar", action="store_true", help="genera un JWT_SECRET nuevo aunque ya exista")
    parser.add_argument(
        "--solo-worker",
        type=Path,
        help="archivo adicional con solo WORKER_TOKEN, para copiar a los nodos worker sin el secreto",
    )
    args = parser.parse_args(argv)
    try:
        escritos = generar(
            args.env, dias=args.dias, rotar=args.rotar, solo_worker=args.solo_worker, clock=clock or UtcClock()
        )
    except (OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(f"escritas en {args.env}: {', '.join(escritos)} (vigencia de los tokens: {args.dias} días)")
    if args.solo_worker is not None:
        print(f"escrita en {args.solo_worker}: WORKER_TOKEN")
    return 0


if __name__ == "__main__":
    sys.exit(main())
