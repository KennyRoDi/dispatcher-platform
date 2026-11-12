from __future__ import annotations

import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

from src.adapters.audio_analyzer import AudioAnalyzer
from src.adapters.image_analyzer import ImageAnalyzer
from src.adapters.parser_por_extension import ParserPorExtension
from src.adapters.text_analyzer import TextAnalyzer
from src.application.analyze_audio import Transcriber
from src.application.analyze_image import ObjectDetector
from src.application.analyze_text import TextModels
from src.application.ports import Analyzer

TIPOS = ("text", "image", "audio")
RAIZ = Path(__file__).resolve().parents[2]


def _modelos_de_texto(config: Path) -> TextModels:
    from src.adapters.spacy_hf_text_models import SpacyHfTextModels

    return SpacyHfTextModels.from_config(config)


def _detector(config: Path, pesos: Path) -> ObjectDetector:
    from src.adapters.yolo_detector import YoloDetector

    return YoloDetector.from_config(config, pesos)


def _transcriptor(config: Path) -> Transcriber:
    from src.adapters.whisper_transcriber import WhisperTranscriber

    return WhisperTranscriber.from_config(config)


@dataclass(frozen=True)
class ConstructoresDeModelos:
    textos: Callable[[Path], TextModels] = _modelos_de_texto
    detector: Callable[[Path, Path], ObjectDetector] = _detector
    transcriptor: Callable[[Path], Transcriber] = _transcriptor


def crear_analizador(
    kind: str,
    env: Mapping[str, str] | None = None,
    constructores: ConstructoresDeModelos | None = None,
) -> Analyzer:
    if kind not in TIPOS:
        raise ValueError(f"tipo de analizador desconocido: {kind!r}; se admiten {', '.join(TIPOS)}")
    env = os.environ if env is None else env
    constructores = constructores or ConstructoresDeModelos()
    config = Path(env.get("CONFIG_DIR", "").strip() or RAIZ / "config")
    if kind == "text":
        return TextAnalyzer.from_config(ParserPorExtension(), constructores.textos(config / "texto.toml"), config / "texto.toml")
    if kind == "image":
        pesos = Path(env.get("YOLO_WEIGHTS_DIR", "").strip() or RAIZ)
        return ImageAnalyzer.from_config(constructores.detector(config / "imagen.toml", pesos), config / "imagen.toml")
    return AudioAnalyzer.from_config(
        constructores.transcriptor(config / "audio.toml"), constructores.textos(config / "texto.toml"), config / "texto.toml"
    )
