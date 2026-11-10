# Transcripción con faster-whisper de SYSTRAN (https://github.com/SYSTRAN/faster-whisper), licencia MIT.
# Pesos de Whisper de OpenAI (https://github.com/openai/whisper), licencia MIT, convertidos a CTranslate2
# en https://huggingface.co/Systran/faster-whisper-base, también MIT.
import math
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.domain.transcription import TranscriptSegment

COMMIT_HEX = re.compile(r"[0-9a-f]{40}")
# Solo las variantes que compara M5; otra se agrega cuando se mida.
COMPUTE_TYPES = frozenset({"int8", "float32"})


@dataclass(frozen=True)
class ConfigWhisper:
    nombre: str
    revision: str
    idioma: str
    compute_type: str
    beam_size: int
    hilos: int


class WhisperTranscriber:
    def __init__(self, modelo: Any, config: ConfigWhisper) -> None:
        self.modelo = modelo
        self.config = config

    @classmethod
    def from_config(cls, ruta_config: Path) -> "WhisperTranscriber":
        config = cargar_config_de_audio(ruta_config)
        # Importación diferida: las unitarias y el resto del worker no cargan faster-whisper, CTranslate2 ni PyAV.
        from faster_whisper import WhisperModel

        modelo = WhisperModel(
            config.nombre,
            device="cpu",
            compute_type=config.compute_type,
            cpu_threads=config.hilos,
            revision=config.revision,
        )
        return cls(modelo, config)

    def transcribe(self, path: Path) -> list[TranscriptSegment]:
        try:
            segmentos, _ = self.modelo.transcribe(
                str(path), language=self.config.idioma, beam_size=self.config.beam_size
            )
            # El generador es perezoso: la decodificación puede fallar al recorrerlo, no solo al llamar.
            crudos = list(segmentos)
        # PyAV da InvalidDataError, subclase de ValueError, ante un archivo que no es audio.
        except (OSError, ValueError) as error:
            raise ValueError(f"no es un audio legible: {path}") from error
        return sorted((_segmento(crudo) for crudo in crudos), key=lambda segmento: segmento.inicio)


def _segmento(crudo: Any) -> TranscriptSegment:
    return TranscriptSegment(float(crudo.start), float(crudo.end), crudo.text, _confianza(crudo.avg_logprob))


def _confianza(avg_logprob: Any) -> float:
    # Acotar antes de exp evita el desbordamiento y deja la confianza en [0, 1].
    return math.exp(min(0.0, float(avg_logprob)))


def cargar_config_de_audio(ruta: Path) -> ConfigWhisper:
    with open(ruta, "rb") as archivo:
        modelo = tomllib.load(archivo).get("modelo")
    if not isinstance(modelo, dict):
        raise ValueError(f"falta la tabla [modelo] en {ruta}")
    return ConfigWhisper(
        nombre=_texto(modelo, "nombre"),
        revision=_revision(modelo),
        idioma=_texto(modelo, "idioma"),
        compute_type=_compute_type(modelo),
        beam_size=_entero(modelo, "beam_size", minimo=1),
        hilos=_entero(modelo, "hilos", minimo=0),
    )


def _texto(modelo: dict, clave: str) -> str:
    valor = modelo.get(clave)
    if not isinstance(valor, str) or not valor.strip():
        raise ValueError(f"[modelo] {clave} debe ser un texto no vacío: {valor!r}")
    return valor


def _revision(modelo: dict) -> str:
    revision = modelo.get("revision")
    if not isinstance(revision, str) or not COMMIT_HEX.fullmatch(revision):
        raise ValueError(f"[modelo] revision debe ser un commit de 40 dígitos hexadecimales en minúscula: {revision!r}")
    return revision


def _compute_type(modelo: dict) -> str:
    compute_type = modelo.get("compute_type")
    if compute_type not in COMPUTE_TYPES:
        raise ValueError(f"[modelo] compute_type debe ser uno de {sorted(COMPUTE_TYPES)}: {compute_type!r}")
    return compute_type


def _entero(modelo: dict, clave: str, minimo: int) -> int:
    valor = modelo.get(clave)
    # bool es subclase de int: sin excluirlo, `true` en el TOML pasaría como 1.
    if not isinstance(valor, int) or isinstance(valor, bool) or valor < minimo:
        raise ValueError(f"[modelo] {clave} debe ser un entero mayor o igual que {minimo}: {valor!r}")
    return valor
