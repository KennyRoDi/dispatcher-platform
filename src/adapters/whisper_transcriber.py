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
# Copiado de _LANGUAGE_CODES en faster_whisper/tokenizer.py v1.2.1 (SYSTRAN, MIT): un código ajeno a este
# conjunto hace que Tokenizer lance ValueError al transcribir, y ese error se confundiría con un audio ilegible.
IDIOMAS_DE_WHISPER = frozenset(
    (
        "af", "am", "ar", "as", "az", "ba", "be", "bg", "bn", "bo", "br", "bs", "ca", "cs", "cy", "da", "de",
        "el", "en", "es", "et", "eu", "fa", "fi", "fo", "fr", "gl", "gu", "ha", "haw", "he", "hi", "hr", "ht",
        "hu", "hy", "id", "is", "it", "ja", "jw", "ka", "kk", "km", "kn", "ko", "la", "lb", "ln", "lo", "lt",
        "lv", "mg", "mi", "mk", "ml", "mn", "mr", "ms", "mt", "my", "ne", "nl", "nn", "no", "oc", "pa", "pl",
        "ps", "pt", "ro", "ru", "sa", "sd", "si", "sk", "sl", "sn", "so", "sq", "sr", "su", "sv", "sw", "ta",
        "te", "tg", "th", "tk", "tl", "tr", "tt", "uk", "ur", "uz", "vi", "yi", "yo", "zh", "yue",
    )
)


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
    def from_config(cls, ruta_config: Path, num_workers: int = 1) -> "WhisperTranscriber":
        config = cargar_config_de_audio(ruta_config)
        # Importación diferida: las unitarias y el resto del worker no cargan faster-whisper, CTranslate2 ni PyAV.
        from faster_whisper import WhisperModel

        modelo = WhisperModel(
            config.nombre,
            device="cpu",
            compute_type=config.compute_type,
            cpu_threads=config.hilos,
            num_workers=num_workers,
            revision=config.revision,
        )
        return cls(modelo, config)

    def transcribe(self, path: Path) -> list[TranscriptSegment]:
        try:
            segmentos, _ = self.modelo.transcribe(
                str(path), language=self.config.idioma, beam_size=self.config.beam_size
            )
            # decode_audio corre al llamar a transcribe(); lo perezoso del generador es la inferencia de CTranslate2.
            crudos = list(segmentos)
        except _errores_de_decodificacion() as error:
            if isinstance(error, ERRORES_TRANSITORIOS):
                raise
            raise ValueError(f"no es un audio legible: {path}") from error
        try:
            convertidos = [_segmento(crudo) for crudo in crudos]
        except ValueError as error:
            raise ValueError(f"Whisper devolvió un segmento inválido para {path}: {error}") from error
        return sorted(convertidos, key=lambda segmento: segmento.inicio)


# PyAV 19.0.2 (av/error.py) mapea ENOMEM, ETIMEDOUT, EAGAIN/EINTR y EACCES/EPERM a estas clases junto con
# FFmpegError: no dicen nada del archivo y un reintento puede funcionar, así que se propagan tal cual.
ERRORES_TRANSITORIOS = (MemoryError, TimeoutError, BlockingIOError, InterruptedError, PermissionError)


def _errores_de_decodificacion() -> tuple[type[BaseException], ...]:
    # Según el código fuente de PyAV 19.0.2: InvalidDataError hereda de ValueError y los errores de errno de
    # OSError; el resto de av.error.FFmpegError no hereda de ninguno de los dos. Un archivo sin pista de audio
    # da IndexError en StreamContainer._get_streams al hacer container.decode(audio=0).
    errores: tuple[type[BaseException], ...] = (OSError, ValueError, IndexError)
    try:
        from av.error import FFmpegError
    except ImportError:
        return errores
    return (*errores, FFmpegError)


def _segmento(crudo: Any) -> TranscriptSegment:
    return TranscriptSegment(float(crudo.start), float(crudo.end), crudo.text, _confianza(crudo.avg_logprob))


def _confianza(avg_logprob: Any) -> float:
    logprob = float(avg_logprob)
    # min(0.0, nan) da 0.0 porque toda comparación con NaN es falsa: sin esto, NaN saldría como confianza 1.0.
    if math.isnan(logprob):
        raise ValueError(f"avg_logprob no es un número: {avg_logprob!r}")
    # Acotar antes de exp evita el desbordamiento y deja la confianza en [0, 1].
    return math.exp(min(0.0, logprob))


def cargar_config_de_audio(ruta: Path) -> ConfigWhisper:
    with open(ruta, "rb") as archivo:
        modelo = tomllib.load(archivo).get("modelo")
    if not isinstance(modelo, dict):
        raise ValueError(f"falta la tabla [modelo] en {ruta}")
    return ConfigWhisper(
        nombre=_texto(modelo, "nombre"),
        revision=_revision(modelo),
        idioma=_idioma(modelo),
        compute_type=_compute_type(modelo),
        beam_size=_entero(modelo, "beam_size", minimo=1),
        hilos=_entero(modelo, "hilos", minimo=0),
    )


def _texto(modelo: dict, clave: str) -> str:
    valor = modelo.get(clave)
    if not isinstance(valor, str) or not valor.strip():
        raise ValueError(f"[modelo] {clave} debe ser un texto no vacío: {valor!r}")
    return valor


def _idioma(modelo: dict) -> str:
    idioma = modelo.get("idioma")
    if not isinstance(idioma, str) or idioma not in IDIOMAS_DE_WHISPER:
        raise ValueError(f"[modelo] idioma debe ser un código de idioma de Whisper, como \"es\": {idioma!r}")
    return idioma


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
