import tomllib
from pathlib import Path

from src.domain.routing import RoutingTable
from src.domain.subtask import ContentKind

RUTA_POR_DEFECTO = Path(__file__).resolve().parents[2] / "config" / "routing.toml"


def cargar_tabla(ruta: Path) -> RoutingTable:
    with open(ruta, "rb") as archivo:
        rutas = tomllib.load(archivo).get("rutas", {})
    kinds = {kind.value: kind for kind in ContentKind}
    desconocidos = set(rutas) - set(kinds)
    if desconocidos:
        raise ValueError(f"tipos de contenido desconocidos: {sorted(desconocidos)}")
    return RoutingTable({kinds[nombre]: clases for nombre, clases in rutas.items()})
