from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.adapters.text_analyzer import TextAnalyzer
from src.domain.chat_message import ChatMessage
from src.domain.finding import Severity
from src.domain.severity import SeverityRules
from src.domain.text_analysis import MessageAnalysis
from tests.dobles import FakeConversationParser

RAIZ = Path(__file__).resolve().parents[2]
REGLAS = {
    "severidad": [
        {"categoria": "amenaza", "umbral": 0.5, "nivel": "alta"},
        {"categoria": "ofensivo", "umbral": 0.5, "nivel": "media"},
    ]
}
AMENAZA = "pagas o vas a ver"
ANALISIS_AMENAZA = MessageAnalysis(("pagar",), "negativo", 0.9, 0.1, ("vas a ver",))


class ModelosQueMarcanTodoComoAmenaza:
    def analyze_messages(self, texts):
        return [ANALISIS_AMENAZA for _ in texts]


def test_regla_aplicada_por_encima_del_umbral():
    reglas = SeverityRules.from_dict(REGLAS)

    assert reglas.severity_for("amenaza", 0.9) is Severity.ALTA
    assert reglas.severity_for("ofensivo", 0.5) is Severity.MEDIA


def test_bajo_el_umbral_queda_en_baja():
    assert SeverityRules.from_dict(REGLAS).severity_for("amenaza", 0.49) is Severity.BAJA


@pytest.mark.parametrize("categoria", ["tema", "sin_ofensa", "inventada"])
def test_categoria_sin_regla_queda_en_baja(categoria):
    assert SeverityRules.from_dict(REGLAS).severity_for(categoria, 1.0) is Severity.BAJA


def test_nivel_desconocido_se_rechaza_al_cargar():
    with pytest.raises(ValueError):
        SeverityRules.from_dict({"severidad": [{"categoria": "amenaza", "umbral": 0.5, "nivel": "urgente"}]})


def escribir_config(ruta, nivel_amenaza):
    ruta.write_text(
        "tamano_lote = 50\n"
        "n_palabras_clave = 5\n\n"
        "[[severidad]]\n"
        'categoria = "amenaza"\n'
        "umbral = 0.5\n"
        f'nivel = "{nivel_amenaza}"\n\n'
        "[temas]\n"
        'conflicto = ["deuda", "pagar"]\n',
        encoding="utf-8",
    )
    return ruta


def severidad_de_amenaza(config, tmp_path):
    archivo = tmp_path / "chat.txt"
    archivo.write_bytes(b"conversacion sintetica")
    mensaje = ChatMessage(datetime(2026, 11, 3, tzinfo=timezone.utc), "Ana", AMENAZA, "chat.txt:1")
    parser = FakeConversationParser([mensaje])
    analizador = TextAnalyzer.from_config(parser, ModelosQueMarcanTodoComoAmenaza(), config)
    return {h.category: h.severity for h in analizador.analyze(archivo)}["amenaza"]


def test_cambiar_el_archivo_toml_cambia_la_severidad(tmp_path):
    config = tmp_path / "texto.toml"

    antes = severidad_de_amenaza(escribir_config(config, "alta"), tmp_path)
    despues = severidad_de_amenaza(escribir_config(config, "media"), tmp_path)

    assert (antes, despues) == (Severity.ALTA, Severity.MEDIA)


def test_configuracion_del_repositorio_marca_amenaza_como_alta(tmp_path):
    assert severidad_de_amenaza(RAIZ / "config" / "texto.toml", tmp_path) is Severity.ALTA


@pytest.mark.parametrize(
    "datos",
    [
        {},
        {"severidad": []},
        {"severidad": [{"categoria": "ofensivo", "umbral": 0.5, "nivel": "media"}]},
    ],
)
def test_configuracion_sin_regla_de_amenaza_se_rechaza(datos):
    with pytest.raises(ValueError, match="amenaza"):
        SeverityRules.from_dict(datos)


@pytest.mark.parametrize("umbral", [5, -0.1, 1.5, float("nan"), float("inf"), "0.5", "alto", True])
def test_umbral_de_regla_fuera_de_rango_se_rechaza(umbral):
    with pytest.raises(ValueError, match="umbral"):
        SeverityRules.from_dict({"severidad": [{"categoria": "amenaza", "umbral": umbral, "nivel": "alta"}]})


@pytest.mark.parametrize("umbral", [0, 0.0, 1, 1.0])
def test_umbral_en_los_extremos_se_acepta(umbral):
    reglas = SeverityRules.from_dict({"severidad": [{"categoria": "amenaza", "umbral": umbral, "nivel": "alta"}]})

    assert reglas.por_categoria["amenaza"].umbral == umbral


def test_dos_reglas_de_la_misma_categoria_se_rechazan():
    duplicadas = {
        "severidad": [
            {"categoria": "amenaza", "umbral": 0.5, "nivel": "alta"},
            {"categoria": "amenaza", "umbral": 0.9, "nivel": "media"},
        ]
    }

    with pytest.raises(ValueError, match="duplicada.*amenaza"):
        SeverityRules.from_dict(duplicadas)


@pytest.mark.parametrize("campo", ["categoria", "umbral", "nivel"])
def test_regla_sin_campo_obligatorio_se_rechaza_nombrando_el_campo(campo):
    regla = {"categoria": "amenaza", "umbral": 0.5, "nivel": "alta"}
    del regla[campo]

    with pytest.raises(ValueError, match=campo):
        SeverityRules.from_dict({"severidad": [regla]})


@pytest.mark.parametrize("severidad", [{"categoria": "amenaza", "umbral": 0.5, "nivel": "alta"}, "alta", 3])
def test_severidad_que_no_es_lista_se_rechaza(severidad):
    with pytest.raises(ValueError, match="severidad"):
        SeverityRules.from_dict({"severidad": severidad})


@pytest.mark.parametrize("regla", ["amenaza", 0.5, ["amenaza", 0.5, "alta"]])
def test_regla_que_no_es_tabla_se_rechaza(regla):
    with pytest.raises(ValueError, match="regla"):
        SeverityRules.from_dict({"severidad": [regla]})


@pytest.mark.parametrize("categoria", [5, "", None])
def test_categoria_que_no_es_texto_se_rechaza(categoria):
    with pytest.raises(ValueError, match="categoria"):
        SeverityRules.from_dict({"severidad": [{"categoria": categoria, "umbral": 0.5, "nivel": "alta"}]})
