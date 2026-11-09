import argparse
import json
import sys
import tomllib
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from importlib import metadata
from pathlib import Path
from typing import Any

from src.adapters.image_analyzer import ImageAnalyzer
from src.adapters.yolo_detector import YoloDetector, es_nombre_de_archivo
from src.application.analyze_image import ObjectDetector
from src.application.ports import Analyzer
from src.domain.finding import Finding

RAIZ = Path(__file__).resolve().parents[1]
CONFIG = RAIZ / "config" / "imagen.toml"
BIBLIOTECAS = ("ultralytics", "torch")


@dataclass(frozen=True)
class EtiquetaImagen:
    archivo: str
    categoria: str | None
    procedencia: str
    licencia: str


def leer_etiquetas(ruta: Path, muestra: Path, categorias: Sequence[str]) -> list[EtiquetaImagen]:
    imagenes = json.loads(Path(ruta).read_text(encoding="utf-8")).get("imagenes")
    if not isinstance(imagenes, list) or not imagenes:
        raise ValueError(f"{ruta} debe tener una lista no vacía en imagenes")
    etiquetas = [_etiqueta(datos, Path(muestra), categorias) for datos in imagenes]
    repetidos = sorted(a for a, n in Counter(e.archivo for e in etiquetas).items() if n > 1)
    if repetidos:
        raise ValueError(f"archivos repetidos en las etiquetas: {', '.join(repetidos)}")
    return etiquetas


def _etiqueta(datos: Mapping[str, Any], muestra: Path, categorias: Sequence[str]) -> EtiquetaImagen:
    archivo = datos.get("archivo")
    if not es_nombre_de_archivo(archivo) or not (muestra / archivo).is_file():
        raise ValueError(f"la imagen {archivo!r} no es un archivo dentro de {muestra}")
    if "categoria" not in datos or not (datos["categoria"] is None or datos["categoria"] in categorias):
        raise ValueError(f"{archivo}: categoria debe ser null o una de {', '.join(categorias)}")
    # [B.3]: sin procedencia y licencia declaradas, la imagen no puede entrar a la muestra.
    for campo in ("procedencia", "licencia"):
        if not isinstance(datos.get(campo), str) or not datos[campo].strip():
            raise ValueError(f"{archivo}: falta {campo}")
    return EtiquetaImagen(archivo, datos["categoria"], datos["procedencia"], datos["licencia"])


@dataclass(frozen=True)
class ResultadoImagen:
    archivo: str
    esperada: str | None
    hallazgos: tuple[Finding, ...]


def evaluar(analizador: Analyzer, muestra: Path, etiquetas: Sequence[EtiquetaImagen]) -> list[ResultadoImagen]:
    return [
        ResultadoImagen(e.archivo, e.categoria, tuple(analizador.analyze(Path(muestra) / e.archivo)))
        for e in etiquetas
    ]


@dataclass(frozen=True)
class FilaAciertos:
    categoria: str
    verdaderos_positivos: int
    falsos_positivos: int
    falsos_negativos: int
    verdaderos_negativos: int


def tabla_aciertos(resultados: Sequence[ResultadoImagen], categorias: Sequence[str]) -> list[FilaAciertos]:
    return [_fila(categoria, resultados) for categoria in categorias]


def _fila(categoria: str, resultados: Sequence[ResultadoImagen]) -> FilaAciertos:
    pares = Counter((r.esperada == categoria, categoria in _obtenidas(r)) for r in resultados)
    return FilaAciertos(categoria, pares[True, True], pares[False, True], pares[True, False], pares[False, False])


def _obtenidas(resultado: ResultadoImagen) -> set[str]:
    return {hallazgo.category for hallazgo in resultado.hallazgos}


def categorias_de(config: Mapping[str, Any]) -> tuple[str, ...]:
    return tuple(sorted(set(config["clases"].values())))


def generar_markdown(
    comando: str,
    config: Mapping[str, Any],
    versiones: Mapping[str, str],
    etiquetas: Sequence[EtiquetaImagen],
    resultados: Sequence[ResultadoImagen],
) -> str:
    filas = tabla_aciertos(resultados, categorias_de(config))
    return "\n".join(
        [
            "# F-08: aciertos del worker de imagen",
            "",
            f"Comando: `{comando}`",
            "",
            *(f"- {biblioteca}: {version}" for biblioteca, version in versiones.items()),
            f"- Pesos: `{config['modelo']['pesos']}`, SHA-256 `{config['modelo']['sha256']}`",
            f"- Umbral mínimo: {config['umbral_minimo']}",
            "",
            *_muestra(etiquetas),
            "",
            "| Categoría | VP | FP | FN | VN |",
            "|---|---|---|---|---|",
            *(_fila_markdown(fila) for fila in filas),
            "",
            "| Imagen | Esperada | Obtenida (confianza) |",
            "|---|---|---|",
            *(f"| {r.archivo} | {r.esperada or 'ninguna'} | {_detalle(r.hallazgos)} |" for r in resultados),
            "",
            *_limites(config, resultados),
        ]
    )


def _muestra(etiquetas: Sequence[EtiquetaImagen]) -> list[str]:
    positivas = sum(e.categoria is not None for e in etiquetas)
    origenes = Counter((e.procedencia, e.licencia) for e in etiquetas)
    return [
        f"Muestra: {len(etiquetas)} imágenes, {positivas} positivas y {len(etiquetas) - positivas} negativas.",
        "",
        *(f"- {n} de «{procedencia}», licencia {licencia}" for (procedencia, licencia), n in origenes.items()),
    ]


def _fila_markdown(f: FilaAciertos) -> str:
    conteos = (f.verdaderos_positivos, f.falsos_positivos, f.falsos_negativos, f.verdaderos_negativos)
    return f"| {f.categoria} | " + " | ".join(map(str, conteos)) + " |"


def _detalle(hallazgos: Sequence[Finding]) -> str:
    return ", ".join(f"{h.category} ({h.confidence:.2f})" for h in hallazgos) or "ninguna"


def _limites(config: Mapping[str, Any], resultados: Sequence[ResultadoImagen]) -> list[str]:
    clases = ", ".join(sorted(config["clases"]))
    return [
        "## Límites",
        "",
        f"- Muestra pequeña: {len(resultados)} imágenes.",
        f"- Solo se buscan las clases de COCO {clases}; COCO no tiene armas de fuego.",
        "- La tabla prueba el funcionamiento de punta a punta, no la precisión del detector.",
        "",
    ]


def construir_analizador(config: Path, detector: ObjectDetector) -> ImageAnalyzer:
    return ImageAnalyzer.from_config(detector, config)


def _versiones_instaladas() -> dict[str, str]:
    return {biblioteca: metadata.version(biblioteca) for biblioteca in BIBLIOTECAS}


def main(
    argv: list[str] | None = None,
    detector: ObjectDetector | None = None,
    versiones: Mapping[str, str] | None = None,
) -> int:
    argv = sys.argv[1:] if argv is None else argv
    parser = argparse.ArgumentParser(description="Compara el analizador de imagen con una muestra etiquetada.")
    parser.add_argument("--muestra", type=Path, required=True)
    parser.add_argument("--etiquetas", type=Path, required=True)
    parser.add_argument("--salida", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=CONFIG)
    parser.add_argument("--pesos", type=Path, default=RAIZ, help="directorio con los pesos fijados en la config")
    args = parser.parse_args(argv)
    with open(args.config, "rb") as archivo:
        config = tomllib.load(archivo)
    try:
        if not args.muestra.is_dir():
            raise ValueError(f"la muestra no es un directorio: {args.muestra}")
        etiquetas = leer_etiquetas(args.etiquetas, args.muestra, categorias_de(config))
        detector = detector or YoloDetector.from_config(args.config, args.pesos)
        resultados = evaluar(construir_analizador(args.config, detector), args.muestra, etiquetas)
    except (ValueError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    comando = "python -m scripts.aciertos_imagen " + " ".join(argv)
    texto = generar_markdown(comando, config, versiones or _versiones_instaladas(), etiquetas, resultados)
    args.salida.parent.mkdir(parents=True, exist_ok=True)
    args.salida.write_text(texto, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
