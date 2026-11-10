import tomllib
from collections.abc import Mapping, Sequence
from pathlib import Path

from src.adapters.hashing import sha256_de_archivo
from src.application.analyze_text import TextModels, TextSettings, analyze_conversation
from src.application.ports import ConversationParser
from src.domain.finding import Finding
from src.domain.severity import SeverityRules


class TextAnalyzer:
    def __init__(
        self,
        parser: ConversationParser,
        models: TextModels,
        reglas: SeverityRules,
        lexico: Mapping[str, Sequence[str]],
        tamano_lote: int = 50,
        n_palabras_clave: int = 5,
        umbral_ofensa: float = 0.5,
    ) -> None:
        self.parser = parser
        self.models = models
        self.ajustes = TextSettings(reglas, lexico, tamano_lote, n_palabras_clave, umbral_ofensa)

    @classmethod
    def from_config(cls, parser: ConversationParser, models: TextModels, ruta: Path) -> "TextAnalyzer":
        with open(ruta, "rb") as archivo:
            datos = tomllib.load(archivo)
        return cls(
            parser,
            models,
            SeverityRules.from_dict(datos),
            datos.get("temas", {}),
            tamano_lote=datos.get("tamano_lote", 50),
            n_palabras_clave=datos.get("n_palabras_clave", 5),
            umbral_ofensa=datos.get("umbral_ofensa", 0.5),
        )

    def analyze(self, path: Path) -> list[Finding]:
        return analyze_conversation(self.parser.parse(path), sha256_de_archivo(path), self.models, self.ajustes)
