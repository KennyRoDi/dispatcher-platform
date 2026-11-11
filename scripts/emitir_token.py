from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Mapping, Sequence

from src.adapters.jwt_tokens import DEFAULT_MINUTES, UtcClock, issue_token, secreto_desde_entorno
from src.application.ports import Clock
from src.domain.rbac import Role


def emitir(env: Mapping[str, str], *, rol: str, sub: str, minutos: int, clock: Clock) -> str:
    secreto = secreto_desde_entorno(env)
    if not secreto:
        raise ValueError("define JWT_SECRET_FILE o JWT_SECRET")
    return issue_token(secreto, role=Role(rol), subject=sub, clock=clock, minutes=minutos)


def _minutos_positivos(valor: str) -> int:
    try:
        minutos = int(valor)
    except ValueError:
        raise argparse.ArgumentTypeError(f"no es un entero: {valor!r}") from None
    if minutos < 1:
        raise argparse.ArgumentTypeError("debe ser al menos 1")
    return minutos


def main(
    argv: Sequence[str] | None = None,
    env: Mapping[str, str] | None = None,
    clock: Clock | None = None,
) -> int:
    parser = argparse.ArgumentParser(description="Imprime un JWT de demo para el coordinador.")
    parser.add_argument("--rol", required=True, choices=[rol.value for rol in Role])
    parser.add_argument("--sub", required=True)
    parser.add_argument("--minutos", type=_minutos_positivos, default=DEFAULT_MINUTES)
    args = parser.parse_args(argv)
    try:
        token = emitir(
            os.environ if env is None else env,
            rol=args.rol,
            sub=args.sub,
            minutos=args.minutos,
            clock=clock or UtcClock(),
        )
    except ValueError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(token)
    return 0


if __name__ == "__main__":
    sys.exit(main())
