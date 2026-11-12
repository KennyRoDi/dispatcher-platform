import pytest

from src.adapters.chat_export_generator import generate_chat, render_telegram, render_whatsapp
from src.adapters.parser_por_extension import ExtensionSinParser, ParserPorExtension
from src.adapters.telegram_parser import TelegramParser
from src.adapters.whatsapp_parser import WhatsAppParser
from src.workers.fallos import es_transitorio
from tests.dobles import FakeConversationParser


def test_parser_por_extension_elige_whatsapp_para_txt_y_telegram_para_json(tmp_path):
    originales = generate_chat(seed=2, count=3)
    txt = tmp_path / "fuente.TXT"
    txt.write_text(render_whatsapp(originales), encoding="utf-8")
    js = tmp_path / "fuente.json"
    js.write_text(render_telegram(originales), encoding="utf-8")
    selector = ParserPorExtension()
    assert list(selector.parse(txt)) == WhatsAppParser().parse(txt)
    assert list(selector.parse(js)) == TelegramParser().parse(js)
    assert len(selector.parse(js)) == 3


def test_parser_por_extension_usa_los_parsers_inyectados(tmp_path):
    selector = ParserPorExtension({".txt": FakeConversationParser()})
    assert list(selector.parse(tmp_path / "x.txt")) == []


@pytest.mark.parametrize("nombre", ["fuente.csv", "fuente.xml", "fuente"])
def test_parser_por_extension_rechaza_csv_con_error_permanente(tmp_path, nombre):
    with pytest.raises(ExtensionSinParser, match="no hay parser") as error:
        ParserPorExtension().parse(tmp_path / nombre)
    assert isinstance(error.value, ValueError)
    assert not es_transitorio(error.value)
