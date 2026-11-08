import json
import random
import re
import tomllib
from datetime import datetime, timezone
from pathlib import Path

import pytest

from scripts.aciertos_texto import (
    ConversacionSinteticaParser,
    EtiquetaLote,
    FilaAciertos,
    ResultadoLote,
    agrupar_por_lote,
    comparar,
    construir_analizador,
    generar_markdown,
    leer_etiquetas,
    main,
    tabla_aciertos,
)
from src.application.ports import ConversationParser
from src.domain.finding import EvidenceRef, Finding, Severity
from src.domain.text_analysis import MessageAnalysis

RAIZ = Path(__file__).resolve().parents[2]
CONFIG = RAIZ / "config" / "texto.toml"
CONVERSACION = RAIZ / "tests" / "datos" / "aciertos_texto_conversacion.json"
ETIQUETAS = RAIZ / "tests" / "datos" / "aciertos_texto_etiquetas.json"
SHA = "a" * 64
NEUTRAL = MessageAnalysis(("informe",), "neutral", 0.8, 0.0, ())
CON_DEUDA = MessageAnalysis(("deuda",), "negativo", 0.9, 0.0, ())


class FakeTextModels:
    def __init__(self, analisis=NEUTRAL):
        self.analisis = analisis
        self.llamadas = []

    def analyze_messages(self, texts):
        self.llamadas.append(list(texts))
        return [self.analisis for _ in texts]


def escribir_json(ruta, datos):
    ruta.write_text(json.dumps(datos, ensure_ascii=False), encoding="utf-8")
    return ruta


def mensaje(texto="hola", timestamp="2026-11-01T20:00:00Z", autor="Ana Sintética"):
    return {"timestamp": timestamp, "autor": autor, "texto": texto}


def etiqueta(mensajes="0-9", tema="conflicto", sentimiento="negativo", ofensa="amenaza"):
    return {"mensajes": mensajes, "tema": tema, "sentimiento": sentimiento, "ofensa": ofensa}


def finding(categoria, posicion, detalle=""):
    return Finding(categoria, Severity.BAJA, 1.0, EvidenceRef(SHA, posicion), detalle)


def lote(rango, tema="conflicto", sentimiento="negativo", ofensa=("sin_ofensa", None)):
    categoria_ofensa, posicion_ofensa = ofensa
    return [
        finding("palabras_clave", f"mensajes {rango}", "deuda"),
        finding("tema", f"mensajes {rango}", tema),
        finding("sentimiento", f"mensajes {rango}", sentimiento),
        finding(categoria_ofensa, posicion_ofensa or f"mensajes {rango}"),
    ]


def test_parser_cumple_el_puerto():
    assert isinstance(ConversacionSinteticaParser(), ConversationParser)


def test_parser_lee_mensajes_en_orden_y_normaliza_a_utc(tmp_path):
    ruta = escribir_json(
        tmp_path / "conv.json",
        {"mensajes": [mensaje("primero", "2026-11-01T08:00:00-06:00"), mensaje("segundo", "2026-11-01T14:05:00Z", "Beto Ficticio")]},
    )

    leidos = list(ConversacionSinteticaParser().parse(ruta))

    assert [m.text for m in leidos] == ["primero", "segundo"]
    assert leidos[0].timestamp_utc == datetime(2026, 11, 1, 14, 0, tzinfo=timezone.utc)
    assert leidos[0].timestamp_utc.utcoffset().total_seconds() == 0
    assert leidos[1].sender == "Beto Ficticio"
    assert len({m.source_ref for m in leidos}) == 2
    assert all("conv.json" in m.source_ref for m in leidos)


def test_parser_normaliza_el_texto_a_nfc(tmp_path):
    ruta = escribir_json(tmp_path / "conv.json", {"mensajes": [mensaje("café en la plaza")]})

    assert [m.text for m in ConversacionSinteticaParser().parse(ruta)] == ["café en la plaza"]


def test_parser_rechaza_hora_sin_zona(tmp_path):
    ruta = escribir_json(tmp_path / "conv.json", {"mensajes": [mensaje(timestamp="2026-11-01T20:00:00")]})

    with pytest.raises(ValueError):
        list(ConversacionSinteticaParser().parse(ruta))


def test_parser_rechaza_mensaje_sin_texto(tmp_path):
    ruta = escribir_json(tmp_path / "conv.json", {"mensajes": [{"timestamp": "2026-11-01T20:00:00Z", "autor": "Ana"}]})

    with pytest.raises(ValueError, match="texto"):
        list(ConversacionSinteticaParser().parse(ruta))


def test_lee_etiquetas_con_tamano_de_lote(tmp_path):
    ruta = escribir_json(
        tmp_path / "etiquetas.json",
        {"tamano_lote": 10, "lotes": [etiqueta(), etiqueta("10-19", "reunion", "positivo", "sin_ofensa")]},
    )

    etiquetas = leer_etiquetas(ruta)

    assert etiquetas.tamano_lote == 10
    assert etiquetas.lotes == (
        EtiquetaLote("0-9", "conflicto", "negativo", "amenaza"),
        EtiquetaLote("10-19", "reunion", "positivo", "sin_ofensa"),
    )


@pytest.mark.parametrize(
    "datos",
    [
        {"tamano_lote": 10, "lotes": [etiqueta(sentimiento="furioso")]},
        {"tamano_lote": 10, "lotes": [etiqueta(ofensa="grosero")]},
        {"tamano_lote": 0, "lotes": [etiqueta()]},
        {"tamano_lote": True, "lotes": [etiqueta()]},
        {"lotes": [etiqueta()]},
        {"tamano_lote": 10, "lotes": []},
        {"tamano_lote": 10, "lotes": [{"mensajes": "0-9", "tema": "conflicto", "sentimiento": "negativo"}]},
    ],
)
def test_etiquetas_mal_formadas_se_rechazan(tmp_path, datos):
    with pytest.raises(ValueError):
        leer_etiquetas(escribir_json(tmp_path / "etiquetas.json", datos))


def test_agrupa_las_cuatro_salidas_por_posicion_y_no_por_orden():
    hallazgos = (
        lote("0-9", ofensa=("ofensivo", "mensajes 3,5"))
        + lote("10-19", ofensa=("amenaza", "mensajes 16"))
        + lote("20", ofensa=("sin_ofensa", "mensajes 20"))
    )
    random.Random(7).shuffle(hallazgos)

    grupos = agrupar_por_lote(hallazgos)

    assert [grupo["tema"].evidence.position for grupo in grupos] == ["mensajes 0-9", "mensajes 10-19", "mensajes 20"]
    assert all(set(grupo) == {"palabras_clave", "tema", "sentimiento", "ofensa"} for grupo in grupos)
    assert [grupo["ofensa"].category for grupo in grupos] == ["ofensivo", "amenaza", "sin_ofensa"]


def test_lote_sin_alguna_salida_se_rechaza():
    hallazgos = [h for h in lote("0-9") if h.category != "sentimiento"]

    with pytest.raises(ValueError, match="sentimiento"):
        agrupar_por_lote(hallazgos)


def test_ofensa_fuera_de_todo_lote_se_rechaza():
    with pytest.raises(ValueError):
        agrupar_por_lote(lote("0-9", ofensa=("amenaza", "mensajes 12")))


def test_compara_cada_lote_con_su_etiqueta(tmp_path):
    etiquetas = leer_etiquetas(
        escribir_json(
            tmp_path / "etiquetas.json",
            {"tamano_lote": 10, "lotes": [etiqueta(), etiqueta("10-19", "reunion", "positivo", "sin_ofensa")]},
        )
    )
    hallazgos = lote("0-9", ofensa=("amenaza", "mensajes 6")) + lote("10-19", "sin_tema", "neutral")

    resultados = comparar(hallazgos, etiquetas)

    assert resultados == [
        ResultadoLote(
            EtiquetaLote("0-9", "conflicto", "negativo", "amenaza"),
            EtiquetaLote("0-9", "conflicto", "negativo", "amenaza"),
        ),
        ResultadoLote(
            EtiquetaLote("10-19", "reunion", "positivo", "sin_ofensa"),
            EtiquetaLote("10-19", "sin_tema", "neutral", "sin_ofensa"),
        ),
    ]


def test_numero_de_lotes_distinto_se_rechaza(tmp_path):
    etiquetas = leer_etiquetas(escribir_json(tmp_path / "etiquetas.json", {"tamano_lote": 10, "lotes": [etiqueta()]}))

    with pytest.raises(ValueError, match="lotes"):
        comparar(lote("0-9") + lote("10-19"), etiquetas)


def test_rango_de_etiqueta_distinto_al_del_lote_se_rechaza(tmp_path):
    etiquetas = leer_etiquetas(escribir_json(tmp_path / "etiquetas.json", {"tamano_lote": 10, "lotes": [etiqueta("0-4")]}))

    with pytest.raises(ValueError, match="mensajes"):
        comparar(lote("0-9"), etiquetas)


def resultados_de_ejemplo():
    return [
        ResultadoLote(EtiquetaLote("0-9", "conflicto", "negativo", "amenaza"), EtiquetaLote("0-9", "conflicto", "negativo", "ofensivo")),
        ResultadoLote(EtiquetaLote("10-19", "conflicto", "negativo", "ofensivo"), EtiquetaLote("10-19", "conflicto", "neutral", "ofensivo")),
        ResultadoLote(EtiquetaLote("20-29", "reunion", "positivo", "sin_ofensa"), EtiquetaLote("20-29", "sin_tema", "positivo", "sin_ofensa")),
    ]


def test_tabla_de_aciertos_y_errores_por_categoria():
    assert tabla_aciertos(resultados_de_ejemplo()) == [
        FilaAciertos("tema", lotes=3, aciertos=2, errores=1),
        FilaAciertos("sentimiento", lotes=3, aciertos=2, errores=1),
        FilaAciertos("amenaza", lotes=1, aciertos=0, errores=1),
        FilaAciertos("ofensivo", lotes=1, aciertos=1, errores=0),
        FilaAciertos("sin_ofensa", lotes=1, aciertos=1, errores=0),
    ]


def test_markdown_de_evidencia_declara_comando_modelos_lote_y_tabla():
    with open(CONFIG, "rb") as archivo:
        config = tomllib.load(archivo)
    comando = "python -m scripts.aciertos_texto --conversacion c.json --etiquetas e.json --salida s.md"

    texto = generar_markdown(comando, config, 10, resultados_de_ejemplo())

    assert comando in texto
    for clave in ("spacy", "sentimiento", "ofensa"):
        assert config["modelos"][clave]["nombre"] in texto
        assert config["modelos"][clave]["revision"] in texto
    assert re.search(r"[Tt]amaño de lote\D*10\b", texto)
    assert "| Categoría | Lotes | Aciertos | Errores |" in texto
    assert "| tema | 3 | 2 | 1 |" in texto
    assert "| amenaza | 1 | 0 | 1 |" in texto
    for posicion in ("mensajes 0-9", "mensajes 10-19", "mensajes 20-29"):
        assert posicion in texto


def test_analizador_usa_la_configuracion_y_el_tamano_de_lote_dado():
    modelos = FakeTextModels(CON_DEUDA)

    hallazgos = construir_analizador(CONFIG, modelos, tamano_lote=10).analyze(CONVERSACION)

    assert [len(llamada) for llamada in modelos.llamadas] == [10, 10, 10, 10]
    assert len(hallazgos) == 16
    assert {h.detail for h in hallazgos if h.category == "tema"} == {"conflicto"}


def test_main_escribe_la_evidencia_con_el_comando_exacto(tmp_path):
    salida = tmp_path / "F-07_aciertos.md"
    argv = ["--conversacion", str(CONVERSACION), "--etiquetas", str(ETIQUETAS), "--salida", str(salida)]

    assert main(argv, modelos=FakeTextModels()) == 0

    texto = salida.read_text(encoding="utf-8")
    assert "python -m scripts.aciertos_texto " + " ".join(argv) in texto
    assert "| Categoría | Lotes | Aciertos | Errores |" in texto


def test_main_con_lotes_que_no_cuadran_falla_sin_escribir(tmp_path, capsys):
    etiquetas = escribir_json(tmp_path / "etiquetas.json", {"tamano_lote": 10, "lotes": [etiqueta()]})
    salida = tmp_path / "F-07_aciertos.md"
    argv = ["--conversacion", str(CONVERSACION), "--etiquetas", str(etiquetas), "--salida", str(salida)]

    assert main(argv, modelos=FakeTextModels()) == 1

    assert "lotes" in capsys.readouterr().err
    assert not salida.exists()


def test_conversacion_etiquetada_es_sintetica_y_cubre_las_categorias():
    datos = json.loads(CONVERSACION.read_text(encoding="utf-8"))
    etiquetas = leer_etiquetas(ETIQUETAS)
    with open(CONFIG, "rb") as archivo:
        temas = set(tomllib.load(archivo)["temas"])

    assert "sintética" in datos["origen"] and "IA" in datos["origen"]
    assert len(list(ConversacionSinteticaParser().parse(CONVERSACION))) == 40
    assert (etiquetas.tamano_lote, len(etiquetas.lotes)) == (10, 4)
    assert {e.ofensa for e in etiquetas.lotes} == {"amenaza", "ofensivo", "sin_ofensa"}
    assert {e.sentimiento for e in etiquetas.lotes} == {"positivo", "neutral", "negativo"}
    assert temas <= {e.tema for e in etiquetas.lotes} <= temas | {"sin_tema"}


def test_solo_el_lote_de_amenaza_contiene_el_patron_explicito():
    textos = [m.text.lower() for m in ConversacionSinteticaParser().parse(CONVERSACION)]
    etiquetas = leer_etiquetas(ETIQUETAS).lotes

    for indice, etiqueta_lote in enumerate(etiquetas):
        lote_textos = " ".join(textos[indice * 10 : (indice + 1) * 10])
        assert ("vas a ver" in lote_textos) == (etiqueta_lote.ofensa == "amenaza")


def seccion_limites(texto):
    assert "## Límites" in texto
    return texto.split("## Límites", 1)[1].lower()


def test_markdown_declara_sus_limites_con_el_tamano_de_muestra_calculado():
    with open(CONFIG, "rb") as archivo:
        config = tomllib.load(archivo)

    limites = seccion_limites(generar_markdown("cmd", config, 10, resultados_de_ejemplo()))

    assert re.search(r"\b3 lotes\b", limites)
    assert re.search(r"\b30 mensajes\b", limites)
    assert "sintética" in limites and "ia" in re.findall(r"\w+", limites)
    assert "léxico de temas" in limites and "patrones de amenaza" in limites
    assert "explícitas" in limites and "implícitas" in limites
    assert "punta a punta" in limites and "precisión" in limites


def test_tamano_de_muestra_de_los_limites_sale_de_los_resultados():
    with open(CONFIG, "rb") as archivo:
        config = tomllib.load(archivo)
    amenaza = EtiquetaLote("0-9", "conflicto", "negativo", "amenaza")
    tranquilo = EtiquetaLote("10-14", "reunion", "neutral", "sin_ofensa")
    resultados = [ResultadoLote(amenaza, amenaza), ResultadoLote(tranquilo, tranquilo)]

    limites = seccion_limites(generar_markdown("cmd", config, 10, resultados))

    assert re.search(r"\b2 lotes\b", limites)
    assert re.search(r"\b15 mensajes\b", limites)
