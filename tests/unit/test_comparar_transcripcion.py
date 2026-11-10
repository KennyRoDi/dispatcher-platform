import json
import math
import re
from pathlib import Path

import pytest

from scripts.comparar_transcripcion import (
    NotaAudio,
    ResultadoNota,
    evaluar,
    generar_markdown,
    leer_esperadas,
    main,
    normalizar,
    tasa_de_error_por_palabra,
)
from src.adapters.whisper_transcriber import ConfigWhisper
from src.domain.finding import Severity
from src.domain.text_analysis import MessageAnalysis
from src.domain.transcription import TranscriptSegment
from tests.dobles import FakeTextModels

RAIZ = Path(__file__).resolve().parents[2]
CONFIG_TEXTO = RAIZ / "config" / "texto.toml"
CONFIG_AUDIO = RAIZ / "config" / "audio.toml"
VERSIONES = {"faster-whisper": "1.2.1", "ctranslate2": "4.7.1"}
PROPIA = {"procedencia": "Voz de José Andrés leyendo un guion sintético del equipo", "licencia": "CC BY 4.0"}
TEXTO_AMENAZA = "si no pagas la deuda vas a ver"
AMENAZA = MessageAnalysis(
    lemmas=("pagar", "deuda"),
    sentiment_label="negativo",
    sentiment_score=0.9,
    offense_score=0.1,
    threat_patterns=("vas a ver",),
)
RF06 = ("palabras_clave", "tema", "sentimiento")


def escribir_json(ruta, datos):
    ruta.write_text(json.dumps(datos, ensure_ascii=False), encoding="utf-8")
    return ruta


def nota(archivo, texto_esperado="nos vemos en la plaza", **cambios):
    return {"archivo": archivo, "texto_esperado": texto_esperado, **PROPIA, **cambios}


@pytest.fixture
def muestra(tmp_path):
    directorio = tmp_path / "audio"
    directorio.mkdir()
    for nombre in ("neutra_1.ogg", "amenaza_1.ogg"):
        (directorio / nombre).write_bytes(f"bytes sinteticos de {nombre}".encode())
    return directorio


def esperadas_de_muestra(muestra):
    return escribir_json(
        muestra / "transcripciones.json",
        {"notas": [nota("neutra_1.ogg"), nota("amenaza_1.ogg", "Si no pagas la deuda, vas a ver.")]},
    )


class FakeTranscriber:
    def __init__(self, por_archivo):
        self.por_archivo = por_archivo
        self.llamadas = []

    def transcribe(self, path):
        self.llamadas.append(Path(path))
        return list(self.por_archivo.get(Path(path).name, ()))


SEGMENTOS = {
    "neutra_1.ogg": [TranscriptSegment(0.0, 3.5, "Nos vemos en la plaza", 0.92)],
    "amenaza_1.ogg": [TranscriptSegment(0.0, 2.0, "hola", 0.9), TranscriptSegment(2.0, 6.25, TEXTO_AMENAZA, 0.81)],
}


def transcriptor_de_ejemplo():
    return FakeTranscriber(SEGMENTOS)


def modelos_de_ejemplo():
    return FakeTextModels({TEXTO_AMENAZA: AMENAZA})


def evaluar_muestra(muestra, transcriptor=None):
    notas = leer_esperadas(esperadas_de_muestra(muestra), muestra)
    return notas, evaluar(transcriptor or transcriptor_de_ejemplo(), modelos_de_ejemplo(), CONFIG_TEXTO, muestra, notas)


def test_normaliza_mayusculas_tildes_y_puntuacion():
    assert normalizar("¡Hola, Mundo! ¿Cómo estás? Él dijo: «sí».") == "hola mundo como estas el dijo si"


def test_normaliza_espacios_repetidos_y_saltos_de_linea():
    assert normalizar("  nos   vemos\n en la\tplaza  ") == "nos vemos en la plaza"


def test_normaliza_texto_sin_palabras_a_cadena_vacia():
    assert normalizar(" ¿?!... ") == ""


@pytest.mark.parametrize(
    ("esperada", "obtenida", "wer"),
    [
        ("nos vemos en la plaza", "nos vemos en la plaza", 0.0),
        ("nos vemos en la plaza", "nos vemos en la calle", 0.2),
        ("nos vemos en la plaza", "nos vemos en la plaza hoy", 0.2),
        ("nos vemos en la plaza", "nos vemos la plaza", 0.2),
        ("uno dos tres cuatro", "cuatro tres dos uno", 1.0),
        ("uno dos", "uno dos tres cuatro", 1.0),
        ("uno dos tres", "", 1.0),
        ("a b c d", "a x c", 0.5),
        ("", "", 0.0),
    ],
    ids=[
        "exacta",
        "sustitucion",
        "insercion",
        "borrado",
        "orden-invertido",
        "inserciones-superan-referencia",
        "obtenida-vacia",
        "mixta",
        "ambos-vacios",
    ],
)
def test_wer_de_casos_conocidos(esperada, obtenida, wer):
    assert tasa_de_error_por_palabra(esperada, obtenida) == pytest.approx(wer)


def test_wer_puede_superar_uno_porque_no_se_acota():
    assert tasa_de_error_por_palabra("hola", "hola que tal como estas") == pytest.approx(4.0)


def test_wer_normaliza_antes_de_comparar():
    esperada = "Si no pagas la deuda, vas a ver."

    assert tasa_de_error_por_palabra(esperada, "si NO pagás la deuda vas a ver") == 0.0
    assert tasa_de_error_por_palabra(esperada, "si NO pagás la deuda vas a ve") == pytest.approx(1 / 8)


def test_wer_con_esperado_vacio_y_obtenida_con_texto_es_infinito():
    assert tasa_de_error_por_palabra("", "texto inventado") == math.inf


def test_lee_notas_con_texto_esperado_procedencia_y_licencia(muestra):
    notas = leer_esperadas(esperadas_de_muestra(muestra), muestra)

    assert notas[0] == NotaAudio("neutra_1.ogg", "nos vemos en la plaza", PROPIA["procedencia"], PROPIA["licencia"])
    assert [n.archivo for n in notas] == ["neutra_1.ogg", "amenaza_1.ogg"]


@pytest.mark.parametrize(
    "entrada",
    [
        {"archivo": "neutra_1.ogg", "texto_esperado": "hola", "licencia": "CC BY 4.0"},
        {"archivo": "neutra_1.ogg", "texto_esperado": "hola", "procedencia": "Voz propia"},
        nota("neutra_1.ogg", procedencia=""),
        nota("neutra_1.ogg", licencia="   "),
        nota("neutra_1.ogg", texto_esperado=""),
        nota("neutra_1.ogg", texto_esperado="  ¿? "),
        {"archivo": "neutra_1.ogg", **PROPIA},
        nota("neutra_1.ogg", texto_esperado=7),
        nota("no_existe.ogg"),
        nota(""),
        nota("../audio/neutra_1.ogg"),
        {k: v for k, v in nota("x.ogg").items() if k != "archivo"},
    ],
    ids=[
        "sin-procedencia",
        "sin-licencia",
        "procedencia-vacia",
        "licencia-en-blanco",
        "texto-vacio",
        "texto-sin-palabras",
        "sin-texto",
        "texto-no-es-cadena",
        "audio-inexistente",
        "archivo-vacio",
        "ruta-fuera-de-la-muestra",
        "sin-archivo",
    ],
)
def test_nota_invalida_se_rechaza(muestra, entrada):
    ruta = escribir_json(muestra / "transcripciones.json", {"notas": [entrada]})

    with pytest.raises(ValueError):
        leer_esperadas(ruta, muestra)


@pytest.mark.parametrize(
    "datos",
    [
        {},
        {"notas": []},
        {"notas": "neutra_1.ogg"},
        {"notas": [nota("neutra_1.ogg"), nota("neutra_1.ogg")]},
        ["neutra_1.ogg"],
        {"notas": ["neutra_1.ogg"]},
        {"notas": [None]},
    ],
    ids=["sin-notas", "lista-vacia", "no-es-lista", "archivo-repetido", "raiz-es-lista", "elemento-es-texto", "elemento-nulo"],
)
def test_archivo_de_esperadas_mal_formado_se_rechaza(muestra, datos):
    with pytest.raises(ValueError):
        leer_esperadas(escribir_json(muestra / "transcripciones.json", datos), muestra)


def test_json_roto_se_rechaza_con_value_error(muestra):
    ruta = muestra / "transcripciones.json"
    ruta.write_text("{esto no es json", encoding="utf-8")

    with pytest.raises(ValueError):
        leer_esperadas(ruta, muestra)


def test_evalua_cada_nota_con_el_analizador_de_audio_y_calcula_el_wer(muestra):
    transcriptor = transcriptor_de_ejemplo()

    notas, resultados = evaluar_muestra(muestra, transcriptor)

    assert transcriptor.llamadas == [muestra / n.archivo for n in notas]
    assert [r.archivo for r in resultados] == ["neutra_1.ogg", "amenaza_1.ogg"]
    neutra, amenaza = resultados
    assert neutra.esperada == "nos vemos en la plaza"
    assert neutra.segmentos == tuple(SEGMENTOS["neutra_1.ogg"])
    assert neutra.wer == pytest.approx(0.0)
    assert amenaza.segmentos == tuple(SEGMENTOS["amenaza_1.ogg"])
    assert amenaza.wer == pytest.approx(1 / 8)


def test_los_hallazgos_de_cada_nota_traen_rf06_transcripcion_y_amenaza_alta(muestra):
    _, (neutra, amenaza) = evaluar_muestra(muestra)

    assert set(RF06) <= {h.category for h in amenaza.hallazgos}
    assert set(RF06) <= {h.category for h in neutra.hallazgos}
    (hallazgo,) = [h for h in amenaza.hallazgos if h.category == "amenaza"]
    assert hallazgo.severity is Severity.ALTA
    assert hallazgo.evidence.position.startswith("segmentos 1 t=")
    assert "amenaza" not in {h.category for h in neutra.hallazgos}


def test_la_transcripcion_se_pide_una_sola_vez_por_nota(muestra):
    transcriptor = transcriptor_de_ejemplo()

    evaluar_muestra(muestra, transcriptor)

    assert len(transcriptor.llamadas) == 2


def test_nota_sin_voz_da_wer_uno_sin_romper_la_evaluacion(muestra):
    _, (neutra, amenaza) = evaluar_muestra(muestra, FakeTranscriber({}))

    assert (neutra.segmentos, neutra.hallazgos, neutra.wer) == ((), (), 1.0)
    assert amenaza.wer == pytest.approx(1.0)


def config_whisper(**cambios):
    valores = {
        "nombre": "base",
        "revision": "ebe41f70d5b6dfa9166e2c581c45c9c0cfc57b66",
        "idioma": "es",
        "compute_type": "int8",
        "beam_size": 5,
        "hilos": 0,
    }
    return ConfigWhisper(**{**valores, **cambios})


def texto_de_evidencia(muestra, comando="python -m scripts.comparar_transcripcion --muestra m --esperadas e.json --salida s.md"):
    notas, resultados = evaluar_muestra(muestra)
    return generar_markdown(comando, config_whisper(), VERSIONES, notas, resultados)


def test_markdown_declara_comando_versiones_modelo_revision_compute_type_idioma_y_procedencia(muestra):
    comando = "python -m scripts.comparar_transcripcion --muestra m --esperadas e.json --salida s.md"

    texto = texto_de_evidencia(muestra, comando)

    assert comando in texto
    assert re.search(r"faster-whisper\D*1\.2\.1", texto)
    assert re.search(r"ctranslate2\D*4\.7\.1", texto, re.IGNORECASE)
    assert "base" in texto
    assert "ebe41f70d5b6dfa9166e2c581c45c9c0cfc57b66" in texto
    assert "int8" in texto
    assert re.search(r"[Ii]dioma\D*es\b", texto)
    assert PROPIA["procedencia"] in texto and PROPIA["licencia"] in texto


def test_markdown_muestra_por_nota_esperada_obtenida_con_timestamps_wer_y_hallazgos(muestra):
    texto = texto_de_evidencia(muestra)

    for archivo in ("neutra_1.ogg", "amenaza_1.ogg"):
        assert archivo in texto
    assert "nos vemos en la plaza" in texto
    assert "Si no pagas la deuda, vas a ver." in texto
    assert "0.00-3.50" in texto and "2.00-6.25" in texto
    assert TEXTO_AMENAZA in texto
    assert "0.0 %" in texto and "12.5 %" in texto
    for categoria in (*RF06, "amenaza"):
        assert categoria in texto
    assert "alta" in texto


def test_markdown_declara_el_tamano_de_la_muestra_y_sus_limites(muestra):
    texto = texto_de_evidencia(muestra)

    assert re.search(r"\b2 notas\b", texto)
    assert "## Límites" in texto
    limites = texto.split("## Límites", 1)[1].lower()
    assert re.search(r"\b2 notas\b", limites)
    assert "representativ" in limites
    assert "amenaza" in limites


def test_markdown_registra_el_wer_sin_umbral(muestra):
    texto = texto_de_evidencia(muestra).lower()

    assert "sin umbral" in texto
    assert "umbral" not in texto.replace("sin umbral", "")


def test_markdown_solo_contiene_lo_que_sale_de_los_resultados(muestra):
    notas, resultados = evaluar_muestra(muestra, FakeTranscriber({}))

    texto = generar_markdown("cmd", config_whisper(), VERSIONES, notas, resultados)

    assert "100.0 %" in texto
    assert "0.00-3.50" not in texto
    assert TEXTO_AMENAZA not in texto


def test_markdown_usa_la_configuracion_recibida(muestra):
    notas, resultados = evaluar_muestra(muestra)
    config = config_whisper(nombre="small", compute_type="float32", idioma="en")

    texto = generar_markdown("cmd", config, VERSIONES, notas, resultados)

    assert "small" in texto and "float32" in texto
    assert not re.search(r"\bint8\b", texto)


def argumentos(muestra, esperadas, salida):
    return ["--muestra", str(muestra), "--esperadas", str(esperadas), "--salida", str(salida)]


def llamar_main(argv, transcriptor=None):
    return main(argv, transcriptor=transcriptor or transcriptor_de_ejemplo(), modelos=modelos_de_ejemplo(), versiones=VERSIONES)


def test_main_escribe_la_evidencia_con_el_comando_exacto(muestra, tmp_path):
    salida = tmp_path / "evidencia" / "F-09_transcripcion.md"
    argv = argumentos(muestra, esperadas_de_muestra(muestra), salida)

    assert llamar_main(argv) == 0

    texto = salida.read_text(encoding="utf-8")
    assert "python -m scripts.comparar_transcripcion " + " ".join(argv) in texto
    assert "12.5 %" in texto
    assert "ebe41f70d5b6dfa9166e2c581c45c9c0cfc57b66" in texto


def test_main_lee_el_modelo_de_la_configuracion_indicada(muestra, tmp_path):
    config = tmp_path / "audio.toml"
    config.write_text(CONFIG_AUDIO.read_text(encoding="utf-8").replace('nombre = "base"', 'nombre = "tiny"'), encoding="utf-8")
    salida = tmp_path / "F-09.md"
    opciones = ["--config", str(config), "--config-texto", str(CONFIG_TEXTO)]

    assert llamar_main(argumentos(muestra, esperadas_de_muestra(muestra), salida) + opciones) == 0

    assert "tiny" in salida.read_text(encoding="utf-8")


def test_main_con_esperadas_invalidas_falla_sin_escribir(muestra, tmp_path, capsys):
    esperadas = escribir_json(muestra / "transcripciones.json", {"notas": [nota("neutra_1.ogg", licencia="")]})
    salida = tmp_path / "F-09.md"

    assert llamar_main(argumentos(muestra, esperadas, salida)) == 1

    assert "licencia" in capsys.readouterr().err
    assert not salida.exists()


def test_main_con_muestra_que_no_es_directorio_falla_sin_escribir(muestra, tmp_path, capsys):
    salida = tmp_path / "F-09.md"

    assert llamar_main(argumentos(tmp_path / "no_existe", esperadas_de_muestra(muestra), salida)) == 1

    assert "no_existe" in capsys.readouterr().err
    assert not salida.exists()


def test_main_con_audio_ilegible_falla_sin_escribir(muestra, tmp_path, capsys):
    class TranscriptorQueRechaza:
        def transcribe(self, path):
            raise ValueError(f"no es un audio legible: {path}")

    salida = tmp_path / "F-09.md"

    assert llamar_main(argumentos(muestra, esperadas_de_muestra(muestra), salida), TranscriptorQueRechaza()) == 1

    assert "legible" in capsys.readouterr().err
    assert not salida.exists()


class TranscriptorQueNoDebeLlamarse:
    def transcribe(self, path):
        raise AssertionError(f"se transcribió {path} con una salida no escribible")


@pytest.mark.parametrize("forma", ["directorio", "bajo-un-archivo"])
def test_main_valida_la_salida_antes_de_transcribir(muestra, tmp_path, capsys, forma):
    archivo = tmp_path / "ocupado"
    archivo.write_text("ocupa la ruta", encoding="utf-8")
    salida = {"directorio": tmp_path, "bajo-un-archivo": archivo / "sub" / "F-09.md"}[forma]

    codigo = llamar_main(argumentos(muestra, esperadas_de_muestra(muestra), salida), TranscriptorQueNoDebeLlamarse())

    assert codigo == 1
    assert str(salida) in capsys.readouterr().err


@pytest.mark.parametrize("opcion", ["--config", "--config-texto"])
@pytest.mark.parametrize("contenido", [None, "esto no es [toml"], ids=["inexistente", "toml-roto"])
def test_main_con_config_invalida_falla_sin_escribir(muestra, tmp_path, capsys, opcion, contenido):
    config = tmp_path / "config.toml"
    if contenido is not None:
        config.write_text(contenido, encoding="utf-8")
    salida = tmp_path / "F-09.md"
    argv = argumentos(muestra, esperadas_de_muestra(muestra), salida) + [opcion, str(config)]

    assert llamar_main(argv) == 1

    assert capsys.readouterr().err.startswith("error:")
    assert not salida.exists()


@pytest.mark.parametrize("faltante", ["--muestra", "--esperadas", "--salida"])
def test_main_exige_cada_argumento(muestra, tmp_path, faltante):
    argv = argumentos(muestra, esperadas_de_muestra(muestra), tmp_path / "s.md")
    indice = argv.index(faltante)
    del argv[indice : indice + 2]

    with pytest.raises(SystemExit) as salida:
        llamar_main(argv)

    assert salida.value.code == 2


def test_resultado_de_nota_es_inmutable():
    resultado = ResultadoNota("a.ogg", "hola", (), (), 0.0)

    with pytest.raises(AttributeError):
        resultado.wer = 1.0


def test_muestra_del_repositorio_declara_procedencia_y_licencia_con_notas_neutras_y_de_amenaza():
    # La muestra son notas que graba José Andrés en esta parte; sin ellas la parte no puede cerrar [B.3].
    muestra = RAIZ / "tests" / "datos" / "audio"
    esperadas = muestra / "transcripciones.json"
    assert esperadas.is_file(), "falta tests/datos/audio/transcripciones.json con la muestra"

    notas = leer_esperadas(esperadas, muestra)

    assert len(notas) >= 5
    assert any("amenaza" in n.archivo.lower() for n in notas)
    assert any("amenaza" not in n.archivo.lower() for n in notas)
