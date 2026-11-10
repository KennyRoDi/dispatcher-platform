import argparse
import json
import math
import re
import sys
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from importlib import metadata
from pathlib import Path
from typing import Any

from src.adapters.audio_analyzer import AudioAnalyzer
from src.adapters.whisper_transcriber import ConfigWhisper, WhisperTranscriber, cargar_config_de_audio
from src.application.analyze_audio import Transcriber
from src.application.analyze_text import TextModels
from src.domain.finding import Finding
from src.domain.transcription import TranscriptSegment

RAIZ = Path(__file__).resolve().parents[1]
CONFIG_AUDIO = RAIZ / "config" / "audio.toml"
CONFIG_TEXTO = RAIZ / "config" / "texto.toml"
BIBLIOTECAS = ("faster-whisper", "ctranslate2")
CAMPOS_DE_TEXTO = ("archivo", "texto_esperado", "procedencia", "licencia")
NO_ALFANUMERICO = re.compile(r"[^\w\s]|_")


def normalizar(texto: str) -> str:
    # La ñ no se descompone: "año" y "ano" son palabras distintas.
    sin_tildes = "".join(
        letra if letra in "ñÑ" else "".join(c for c in unicodedata.normalize("NFD", letra) if not unicodedata.combining(c))
        for letra in texto
    )
    return " ".join(NO_ALFANUMERICO.sub(" ", sin_tildes.lower()).split())


def tasa_de_error_por_palabra(esperada: str, obtenida: str) -> float:
    referencia, hipotesis = normalizar(esperada).split(), normalizar(obtenida).split()
    if not referencia:
        return 0.0 if not hipotesis else math.inf
    return _distancia(referencia, hipotesis) / len(referencia)


def _distancia(a: Sequence[str], b: Sequence[str]) -> int:
    anterior = list(range(len(b) + 1))
    for i, palabra in enumerate(a, 1):
        actual = [i]
        for j, otra in enumerate(b, 1):
            costo = 0 if palabra == otra else 1
            actual.append(min(anterior[j] + 1, actual[j - 1] + 1, anterior[j - 1] + costo))
        anterior = actual
    return anterior[-1]


@dataclass(frozen=True)
class NotaAudio:
    archivo: str
    texto_esperado: str
    procedencia: str
    licencia: str


def leer_esperadas(ruta: Path, muestra: Path) -> list[NotaAudio]:
    try:
        datos = json.loads(Path(ruta).read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"{ruta} no es JSON válido: {error}") from error
    notas = datos.get("notas") if isinstance(datos, dict) else None
    if not isinstance(notas, list) or not notas:
        raise ValueError(f"{ruta} debe tener una lista de notas no vacía")
    leidas = [_nota(entrada, Path(muestra)) for entrada in notas]
    archivos = [n.archivo for n in leidas]
    repetidos = sorted({a for a in archivos if archivos.count(a) > 1})
    if repetidos:
        raise ValueError(f"notas repetidas: {repetidos}")
    return leidas


def _nota(entrada: Any, muestra: Path) -> NotaAudio:
    if not isinstance(entrada, dict):
        raise ValueError(f"la nota debe ser un objeto: {entrada!r}")
    invalidos = [c for c in CAMPOS_DE_TEXTO if not isinstance(entrada.get(c), str) or not entrada[c].strip()]
    if invalidos:
        raise ValueError(f"nota sin {', '.join(invalidos)} de texto no vacío: {entrada!r}")
    nota = NotaAudio(*(entrada[c] for c in CAMPOS_DE_TEXTO))
    if Path(nota.archivo).name != nota.archivo:
        raise ValueError(f"el archivo debe estar dentro de la muestra: {nota.archivo!r}")
    if not (muestra / nota.archivo).is_file():
        raise ValueError(f"no existe el audio {muestra / nota.archivo}")
    if not normalizar(nota.texto_esperado):
        raise ValueError(f"el texto esperado de {nota.archivo} no tiene palabras")
    return nota


@dataclass(frozen=True)
class ResultadoNota:
    archivo: str
    esperada: str
    segmentos: tuple[TranscriptSegment, ...]
    hallazgos: tuple[Finding, ...]
    wer: float


class _Registrador:
    def __init__(self, transcriptor: Transcriber) -> None:
        self.transcriptor = transcriptor
        self.segmentos: tuple[TranscriptSegment, ...] = ()

    def transcribe(self, path: Path) -> list[TranscriptSegment]:
        segmentos = self.transcriptor.transcribe(path)
        self.segmentos = tuple(segmentos)
        return segmentos


def evaluar(
    transcriptor: Transcriber, modelos: TextModels, config_texto: Path, muestra: Path, notas: Sequence[NotaAudio]
) -> list[ResultadoNota]:
    registrador = _Registrador(transcriptor)
    analizador = AudioAnalyzer.from_config(registrador, modelos, config_texto)
    resultados = []
    for nota in notas:
        hallazgos = tuple(analizador.analyze(Path(muestra) / nota.archivo))
        obtenida = " ".join(s.texto for s in registrador.segmentos)
        wer = tasa_de_error_por_palabra(nota.texto_esperado, obtenida)
        resultados.append(ResultadoNota(nota.archivo, nota.texto_esperado, registrador.segmentos, hallazgos, wer))
    return resultados


def generar_markdown(
    comando: str,
    config: ConfigWhisper,
    versiones: Mapping[str, str],
    notas: Sequence[NotaAudio],
    resultados: Sequence[ResultadoNota],
) -> str:
    procedencias = [f"- `{n.archivo}`: {n.procedencia}; licencia {n.licencia}" for n in notas]
    detalle = [linea for r in resultados for linea in _detalle(r)]
    return "\n".join(
        [
            "# F-09: transcripción del worker de audio",
            "",
            f"Comando: `{comando}`",
            "",
            *[f"- {biblioteca}: {versiones[biblioteca]}" for biblioteca in BIBLIOTECAS],
            f"- Modelo: `{config.nombre}`, revisión `{config.revision}`",
            f"- compute_type: {config.compute_type}",
            f"- Idioma: {config.idioma}",
            "",
            f"Muestra de {len(notas)} notas, con su procedencia y licencia:",
            "",
            *procedencias,
            "",
            "Tasa de error por palabra (WER) registrada sin umbral.",
            "",
            *detalle,
            *_limites(len(resultados)),
        ]
    )


def _detalle(r: ResultadoNota) -> list[str]:
    segmentos = [f"| {s.inicio:.2f}-{s.fin:.2f} | {s.texto} | {s.confianza:.2f} |" for s in r.segmentos]
    hallazgos = [f"| {h.category} | {h.severity.value} | {h.evidence.position} |" for h in r.hallazgos]
    return [
        f"## {r.archivo}",
        "",
        f"- Esperada: {r.esperada}",
        f"- WER: {r.wer * 100:.1f} %",
        "",
        "| Tramo (s) | Obtenida | Confianza |",
        "|---|---|---|",
        *segmentos,
        "",
        "| Categoría | Severidad | Posición |",
        "|---|---|---|",
        *hallazgos,
        "",
    ]


def _limites(cantidad: int) -> list[str]:
    return [
        "## Límites",
        "",
        f"- Muestra pequeña: {cantidad} notas, no representativa de otras voces, acentos ni ruido.",
        "- Las notas de amenaza son guiones sintéticos leídos, más limpios que una nota real.",
        "- La tabla prueba el funcionamiento de punta a punta, no la precisión de la transcripción.",
        "",
    ]


def _versiones_instaladas() -> dict[str, str]:
    return {biblioteca: metadata.version(biblioteca) for biblioteca in BIBLIOTECAS}


def _validar_salida(salida: Path) -> None:
    if salida.is_dir():
        raise ValueError(f"la salida es un directorio: {salida}")
    # Se valida antes de transcribir, sin crear nada: basta el primer ancestro existente.
    ancestro = next((padre for padre in salida.parents if padre.exists()), None)
    if ancestro is None or not ancestro.is_dir():
        raise ValueError(f"no se puede crear la salida {salida}")


def _argumentos(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compara la transcripción del worker de audio con la esperada.")
    parser.add_argument("--muestra", type=Path, required=True)
    parser.add_argument("--esperadas", type=Path, required=True)
    parser.add_argument("--salida", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=CONFIG_AUDIO)
    parser.add_argument("--config-texto", type=Path, default=CONFIG_TEXTO)
    return parser.parse_args(argv)


def _ejecutar(
    args: argparse.Namespace,
    comando: str,
    transcriptor: Transcriber | None,
    modelos: TextModels | None,
    versiones: Mapping[str, str] | None,
) -> None:
    _validar_salida(args.salida)
    config = cargar_config_de_audio(args.config)
    if not args.muestra.is_dir():
        raise ValueError(f"la muestra no es un directorio: {args.muestra}")
    notas = leer_esperadas(args.esperadas, args.muestra)
    if modelos is None:
        from src.adapters.spacy_hf_text_models import SpacyHfTextModels

        modelos = SpacyHfTextModels.from_config(args.config_texto)
    transcriptor = transcriptor or WhisperTranscriber.from_config(args.config)
    resultados = evaluar(transcriptor, modelos, args.config_texto, args.muestra, notas)
    texto = generar_markdown(comando, config, versiones or _versiones_instaladas(), notas, resultados)
    args.salida.parent.mkdir(parents=True, exist_ok=True)
    args.salida.write_text(texto, encoding="utf-8")


def main(
    argv: list[str] | None = None,
    transcriptor: Transcriber | None = None,
    modelos: TextModels | None = None,
    versiones: Mapping[str, str] | None = None,
) -> int:
    argv = sys.argv[1:] if argv is None else argv
    args = _argumentos(argv)
    try:
        _ejecutar(args, "python -m scripts.comparar_transcripcion " + " ".join(argv), transcriptor, modelos, versiones)
    except (ValueError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
