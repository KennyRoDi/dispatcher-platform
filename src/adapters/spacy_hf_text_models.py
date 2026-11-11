# Modelos de terceros, ya entrenados [B.1] (Parte I §9):
# - spaCy es_core_news_sm, Explosion AI, licencia GPL-3.0: https://spacy.io/models/es
# - pysentimiento/robertuito-sentiment-analysis y pysentimiento/robertuito-hate-speech,
#   Pérez et al., https://github.com/pysentimiento/pysentimiento; entrenados con datasets
#   de uso no comercial (non-commercial), válido solo para el uso académico de este proyecto.
import tomllib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from src.domain.text_analysis import MessageAnalysis

SENTIMIENTO_DEL_MODELO = {"POS": "positivo", "NEU": "neutral", "NEG": "negativo"}
# TR («dirigido») dice a quién va el mensaje, no si ofende; por eso no entra en el puntaje.
ETIQUETAS_DE_OFENSA = {"HS", "AG", "hateful", "aggressive"}
NOMBRES_DE_MODELO = ("spacy", "sentimiento", "ofensa")

Pipeline = Callable[..., list[list[dict[str, Any]]]]


@dataclass(frozen=True)
class ModeloFijado:
    nombre: str
    revision: str


@dataclass(frozen=True)
class PatronAmenaza:
    nombre: str
    tokens: tuple[Mapping[str, Any], ...]


@dataclass(frozen=True)
class ConfigModelos:
    spacy: ModeloFijado
    sentimiento: ModeloFijado
    ofensa: ModeloFijado
    patrones_amenaza: tuple[PatronAmenaza, ...]


class SpacyHfTextModels:
    def __init__(self, nlp: Any, matcher: Any, sentimiento: Pipeline, ofensa: Pipeline) -> None:
        self.nlp = nlp
        self.matcher = matcher
        self.sentimiento = sentimiento
        self.ofensa = ofensa

    @classmethod
    def from_config(cls, ruta: Path) -> "SpacyHfTextModels":
        with open(ruta, "rb") as archivo:
            config = leer_config_modelos(tomllib.load(archivo))
        import spacy
        from spacy.matcher import Matcher
        from transformers import pipeline

        nlp = spacy.load(config.spacy.nombre)
        instalada = nlp.meta.get("version")
        if instalada != config.spacy.revision:
            raise ValueError(f"{config.spacy.nombre} instalado es {instalada}, se fijó {config.spacy.revision}")
        matcher = Matcher(nlp.vocab)
        for patron in config.patrones_amenaza:
            matcher.add(patron.nombre, [[dict(token) for token in patron.tokens]])
        sentimiento, ofensa = (
            pipeline("text-classification", model=modelo.nombre, revision=modelo.revision)
            for modelo in (config.sentimiento, config.ofensa)
        )
        return cls(nlp, matcher, sentimiento, ofensa)

    def analyze_messages(self, texts: Sequence[str]) -> list[MessageAnalysis]:
        textos = list(texts)
        docs = list(self.nlp.pipe(textos))
        sentimientos = _clasificar(self.sentimiento, textos, "sentimiento", top_k=None, truncation=True)
        # El modelo de ofensa es multietiqueta: cada etiqueta es independiente, no suman 1.
        ofensas = _clasificar(self.ofensa, textos, "ofensa", top_k=None, truncation=True, function_to_apply="sigmoid")
        return [
            MessageAnalysis(_lemas(doc), *_sentimiento(sentimiento), _ofensa(ofensa), self._patrones(doc))
            for doc, sentimiento, ofensa in zip(docs, sentimientos, ofensas, strict=True)
        ]

    def _patrones(self, doc: Any) -> tuple[str, ...]:
        return tuple(dict.fromkeys(span.label_ for span in self.matcher(doc, as_spans=True)))


def _clasificar(pipeline: Pipeline, textos: list[str], nombre: str, **opciones: Any) -> list[dict[str, float]]:
    salidas = pipeline(textos, **opciones)
    if len(salidas) != len(textos):
        raise ValueError(f"el modelo de {nombre} devolvió {len(salidas)} resultados para {len(textos)} textos")
    return [_puntajes(salida, nombre) for salida in salidas]


def _puntajes(salida: Any, nombre: str) -> dict[str, float]:
    bien_formada = isinstance(salida, list) and salida and all(_es_puntaje(p) for p in salida)
    if not bien_formada:
        raise ValueError(f"el modelo de {nombre} devolvió una salida sin lista de label y score: {salida!r}")
    return {puntaje["label"]: puntaje["score"] for puntaje in salida}


def _es_puntaje(valor: Any) -> bool:
    return isinstance(valor, Mapping) and "label" in valor and "score" in valor


def _lemas(doc: Any) -> tuple[str, ...]:
    return tuple(t.lemma_.lower() for t in doc if not (t.is_stop or t.is_punct or t.is_space))


def _sentimiento(puntajes: dict[str, float]) -> tuple[str, float]:
    etiqueta = max(puntajes, key=puntajes.get)
    if etiqueta not in SENTIMIENTO_DEL_MODELO:
        raise ValueError(f"etiqueta de sentimiento desconocida del modelo: {etiqueta!r}")
    return SENTIMIENTO_DEL_MODELO[etiqueta], puntajes[etiqueta]


def _ofensa(puntajes: dict[str, float]) -> float:
    relevantes = [puntaje for etiqueta, puntaje in puntajes.items() if etiqueta in ETIQUETAS_DE_OFENSA]
    if not relevantes:
        raise ValueError(f"el modelo de ofensa no devolvió odio ni agresividad: {sorted(puntajes)}")
    return max(relevantes)


def leer_config_modelos(datos: Mapping[str, Any]) -> ConfigModelos:
    modelos = datos.get("modelos")
    if not isinstance(modelos, Mapping):
        raise ValueError(f"falta la tabla [modelos] con {', '.join(NOMBRES_DE_MODELO)}")
    fijados = [_modelo(modelos.get(nombre), nombre) for nombre in NOMBRES_DE_MODELO]
    return ConfigModelos(*fijados, _patrones(datos.get("patrones_amenaza")))


def _modelo(datos: Any, nombre: str) -> ModeloFijado:
    if not isinstance(datos, Mapping):
        raise ValueError(f"falta la tabla [modelos.{nombre}]")
    for campo in ("nombre", "revision"):
        if not _es_texto(datos.get(campo)):
            raise ValueError(f"modelos.{nombre}.{campo} debe ser texto no vacío: {datos.get(campo)!r}")
    return ModeloFijado(datos["nombre"], datos["revision"])


def _patrones(datos: Any) -> tuple[PatronAmenaza, ...]:
    if not isinstance(datos, list) or not datos:
        raise ValueError("se necesita al menos un [[patrones_amenaza]] (SUP-07)")
    return tuple(_patron(patron) for patron in datos)


def _patron(datos: Any) -> PatronAmenaza:
    if not isinstance(datos, Mapping) or not _es_texto(datos.get("nombre")):
        raise ValueError(f"cada patrón de amenaza necesita un nombre de texto: {datos!r}")
    tokens = datos.get("patron")
    tokens_validos = isinstance(tokens, list) and tokens and all(isinstance(t, Mapping) and t for t in tokens)
    if not tokens_validos:
        raise ValueError(f"el patrón «{datos['nombre']}» debe ser una lista de tokens de spaCy: {tokens!r}")
    return PatronAmenaza(datos["nombre"], tuple(tokens))


def _es_texto(valor: Any) -> bool:
    return isinstance(valor, str) and bool(valor)
