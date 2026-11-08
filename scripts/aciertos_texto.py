import argparse
import json
import sys
import tomllib
import unicodedata
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.adapters.text_analyzer import TextAnalyzer
from src.application.analyze_text import TextModels, exigir_entero_positivo
from src.domain.chat_message import ChatMessage
from src.domain.finding import Finding
from src.domain.text_analysis import ETIQUETAS_DE_SENTIMIENTO

RAIZ = Path(__file__).resolve().parents[1]
CONFIG = RAIZ / "config" / "texto.toml"
SALIDAS_DE_LOTE = ("palabras_clave", "tema", "sentimiento")
CUARTA_SALIDA = ("amenaza", "ofensivo", "sin_ofensa")
MODELOS = ("spacy", "sentimiento", "ofensa")


class ConversacionSinteticaParser:
    def parse(self, path: Path) -> Iterator[ChatMessage]:
        datos = json.loads(Path(path).read_text(encoding="utf-8"))
        for indice, mensaje in enumerate(datos["mensajes"]):
            yield ChatMessage(
                _a_utc(datetime.fromisoformat(_campo(mensaje, "timestamp", indice))),
                _nfc(_campo(mensaje, "autor", indice)),
                _nfc(_campo(mensaje, "texto", indice)),
                f"{Path(path).name}:mensaje {indice}",
            )


def _campo(mensaje: Mapping[str, Any], nombre: str, indice: int) -> str:
    valor = mensaje.get(nombre)
    if not isinstance(valor, str):
        raise ValueError(f"el mensaje {indice} no tiene {nombre} de texto: {valor!r}")
    return valor


def _a_utc(hora: datetime) -> datetime:
    # Una hora sin zona se deja intacta para que ChatMessage la rechace en vez de suponer la del equipo.
    return hora.astimezone(timezone.utc) if hora.tzinfo else hora


def _nfc(texto: str) -> str:
    return unicodedata.normalize("NFC", texto)


@dataclass(frozen=True)
class EtiquetaLote:
    mensajes: str
    tema: str
    sentimiento: str
    ofensa: str


@dataclass(frozen=True)
class Etiquetas:
    tamano_lote: int
    lotes: tuple[EtiquetaLote, ...]


def leer_etiquetas(ruta: Path) -> Etiquetas:
    datos = json.loads(Path(ruta).read_text(encoding="utf-8"))
    tamano_lote = datos.get("tamano_lote")
    exigir_entero_positivo(tamano_lote, "tamano_lote")
    lotes = tuple(_etiqueta(lote) for lote in datos.get("lotes", ()))
    if not lotes:
        raise ValueError("las etiquetas no tienen lotes")
    return Etiquetas(tamano_lote, lotes)


def _etiqueta(datos: Mapping[str, Any]) -> EtiquetaLote:
    campos = ("mensajes", "tema", "sentimiento", "ofensa")
    faltantes = [campo for campo in campos if not isinstance(datos.get(campo), str)]
    if faltantes:
        raise ValueError(f"etiqueta sin {', '.join(faltantes)}: {datos!r}")
    etiqueta = EtiquetaLote(*(datos[campo] for campo in campos))
    if etiqueta.sentimiento not in ETIQUETAS_DE_SENTIMIENTO:
        raise ValueError(f"sentimiento desconocido en la etiqueta: {etiqueta.sentimiento!r}")
    if etiqueta.ofensa not in CUARTA_SALIDA:
        raise ValueError(f"ofensa desconocida en la etiqueta: {etiqueta.ofensa!r}")
    return etiqueta


def agrupar_por_lote(hallazgos: Sequence[Finding]) -> list[dict[str, Finding]]:
    grupos: dict[str, dict[str, Finding]] = {}
    for hallazgo in (h for h in hallazgos if h.category in SALIDAS_DE_LOTE):
        _agregar(grupos.setdefault(hallazgo.evidence.position, {}), hallazgo.category, hallazgo)
    for hallazgo in (h for h in hallazgos if h.category not in SALIDAS_DE_LOTE):
        if hallazgo.category not in CUARTA_SALIDA:
            raise ValueError(f"categoría desconocida: {hallazgo.category!r}")
        _agregar(grupos[_lote_que_contiene(grupos, hallazgo.evidence.position)], "ofensa", hallazgo)
    for posicion, grupo in grupos.items():
        faltantes = [salida for salida in (*SALIDAS_DE_LOTE, "ofensa") if salida not in grupo]
        if faltantes:
            raise ValueError(f"el lote {posicion} no tiene {', '.join(faltantes)}")
    return [grupos[posicion] for posicion in sorted(grupos, key=lambda p: min(_indices(p)))]


def _agregar(grupo: dict[str, Finding], salida: str, hallazgo: Finding) -> None:
    if salida in grupo:
        raise ValueError(f"el lote {hallazgo.evidence.position} repite {salida}")
    grupo[salida] = hallazgo


def _lote_que_contiene(grupos: Mapping[str, Any], posicion: str) -> str:
    marcados = _indices(posicion)
    for rango in grupos:
        if marcados <= _indices(rango):
            return rango
    raise ValueError(f"{posicion} no cae dentro de ningún lote")


def _indices(posicion: str) -> set[int]:
    texto = posicion.removeprefix("mensajes ")
    if "-" in texto:
        primero, ultimo = texto.split("-")
        return set(range(int(primero), int(ultimo) + 1))
    return {int(indice) for indice in texto.split(",")}


@dataclass(frozen=True)
class ResultadoLote:
    esperado: EtiquetaLote
    obtenido: EtiquetaLote


def comparar(hallazgos: Sequence[Finding], etiquetas: Etiquetas) -> list[ResultadoLote]:
    grupos = agrupar_por_lote(hallazgos)
    if len(grupos) != len(etiquetas.lotes):
        raise ValueError(f"el análisis dio {len(grupos)} lotes y las etiquetas tienen {len(etiquetas.lotes)}")
    return [_resultado(esperado, grupo) for esperado, grupo in zip(etiquetas.lotes, grupos, strict=True)]


def _resultado(esperado: EtiquetaLote, grupo: Mapping[str, Finding]) -> ResultadoLote:
    rango = grupo["tema"].evidence.position.removeprefix("mensajes ")
    if rango != esperado.mensajes:
        raise ValueError(f"la etiqueta de mensajes {esperado.mensajes} no coincide con el lote mensajes {rango}")
    obtenido = EtiquetaLote(rango, grupo["tema"].detail, grupo["sentimiento"].detail, grupo["ofensa"].category)
    return ResultadoLote(esperado, obtenido)


@dataclass(frozen=True)
class FilaAciertos:
    categoria: str
    lotes: int
    aciertos: int
    errores: int


def tabla_aciertos(resultados: Sequence[ResultadoLote]) -> list[FilaAciertos]:
    filas = [_fila(campo, [(r.esperado, r.obtenido) for r in resultados], campo) for campo in ("tema", "sentimiento")]
    for clase in CUARTA_SALIDA:
        pares = [(r.esperado, r.obtenido) for r in resultados if r.esperado.ofensa == clase]
        filas.append(_fila(clase, pares, "ofensa"))
    return filas


def _fila(categoria: str, pares: Sequence[tuple[EtiquetaLote, EtiquetaLote]], campo: str) -> FilaAciertos:
    aciertos = sum(getattr(esperado, campo) == getattr(obtenido, campo) for esperado, obtenido in pares)
    return FilaAciertos(categoria, len(pares), aciertos, len(pares) - aciertos)


def generar_markdown(
    comando: str, config: Mapping[str, Any], tamano_lote: int, resultados: Sequence[ResultadoLote]
) -> str:
    modelos = [_linea_de_modelo(clave, config["modelos"][clave]) for clave in MODELOS]
    filas = [f"| {f.categoria} | {f.lotes} | {f.aciertos} | {f.errores} |" for f in tabla_aciertos(resultados)]
    detalle = [
        f"| mensajes {r.esperado.mensajes} | {r.esperado.tema} / {r.obtenido.tema} | "
        f"{r.esperado.sentimiento} / {r.obtenido.sentimiento} | {r.esperado.ofensa} / {r.obtenido.ofensa} |"
        for r in resultados
    ]
    return "\n".join(
        [
            "# F-07: aciertos del worker de texto",
            "",
            f"Comando: `{comando}`",
            "",
            "Modelos:",
            "",
            *modelos,
            "",
            f"Tamaño de lote: {tamano_lote} mensajes.",
            "",
            "| Categoría | Lotes | Aciertos | Errores |",
            "|---|---|---|---|",
            *filas,
            "",
            "Detalle por lote, esperado / obtenido:",
            "",
            "| Lote | Tema | Sentimiento | Ofensa |",
            "|---|---|---|---|",
            *detalle,
            "",
        ]
    )


def _linea_de_modelo(clave: str, modelo: Mapping[str, str]) -> str:
    return f"- {clave}: `{modelo['nombre']}`, revisión `{modelo['revision']}`"


def construir_analizador(config: Path, modelos: TextModels, tamano_lote: int) -> TextAnalyzer:
    analizador = TextAnalyzer.from_config(ConversacionSinteticaParser(), modelos, config)
    analizador.ajustes = replace(analizador.ajustes, tamano_lote=tamano_lote)
    return analizador


def main(argv: list[str] | None = None, modelos: TextModels | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    parser = argparse.ArgumentParser(description="Compara el analizador de texto con una conversación etiquetada.")
    parser.add_argument("--conversacion", type=Path, required=True)
    parser.add_argument("--etiquetas", type=Path, required=True)
    parser.add_argument("--salida", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=CONFIG)
    args = parser.parse_args(argv)
    if modelos is None:
        from src.adapters.spacy_hf_text_models import SpacyHfTextModels

        modelos = SpacyHfTextModels.from_config(args.config)
    with open(args.config, "rb") as archivo:
        config = tomllib.load(archivo)
    try:
        etiquetas = leer_etiquetas(args.etiquetas)
        hallazgos = construir_analizador(args.config, modelos, etiquetas.tamano_lote).analyze(args.conversacion)
        resultados = comparar(hallazgos, etiquetas)
    except ValueError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    comando = "python -m scripts.aciertos_texto " + " ".join(argv)
    args.salida.parent.mkdir(parents=True, exist_ok=True)
    args.salida.write_text(generar_markdown(comando, config, etiquetas.tamano_lote, resultados), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
