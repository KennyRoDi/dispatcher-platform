from pathlib import Path

from src.adapters.hashing import sha256_de_archivo
from src.adapters.text_analyzer import cargar_ajustes_de_texto
from src.application.analyze_audio import Transcriber, analyze_audio
from src.application.analyze_text import TextModels, TextSettings
from src.domain.finding import Finding


class AudioAnalyzer:
    def __init__(self, transcriber: Transcriber, models: TextModels, ajustes_texto: TextSettings) -> None:
        self.transcriber = transcriber
        self.models = models
        self.ajustes_texto = ajustes_texto

    @classmethod
    def from_config(cls, transcriber: Transcriber, models: TextModels, ruta: Path) -> "AudioAnalyzer":
        return cls(transcriber, models, cargar_ajustes_de_texto(ruta))

    def analyze(self, path: Path) -> list[Finding]:
        sha256 = sha256_de_archivo(path)
        return analyze_audio(self.transcriber.transcribe(path), sha256, self.models, self.ajustes_texto)
