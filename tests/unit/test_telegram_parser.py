"""Pruebas unitarias del parser de exportaciones de Telegram (F-02).

TDD: pruebas en rojo, sin implementacion aun.
"""
import json

import pytest

from src.adapters.chat_export_generator import generate_chat, render_telegram


class TestTelegramParser:
    def test_telegram_parser_produce_mensajes_utc_utf8(self, tmp_path):
        from src.adapters.telegram_parser import TelegramParser

        originales = generate_chat(seed=2, count=4)
        archivo = tmp_path / "chat.json"
        archivo.write_text(render_telegram(originales), encoding="utf-8")

        mensajes = TelegramParser().parse(archivo)

        assert len(mensajes) == 4
        for original, parseado in zip(originales, mensajes):
            assert parseado.timestamp_utc == original.timestamp_utc
            assert parseado.timestamp_utc.tzinfo is not None
            assert parseado.sender == original.sender
            assert parseado.text == original.text

    def test_telegram_parser_ignora_mensajes_de_servicio(self, tmp_path):
        from src.adapters.telegram_parser import TelegramParser

        export = {
            "name": "x", "type": "personal_chat",
            "messages": [
                {"id": 1, "type": "service", "date": "2026-01-01T00:00:00", "action": "create_group"},
                {"id": 2, "type": "message", "date": "2026-01-01T00:01:00",
                 "date_unixtime": "1", "from": "Ana", "text": "hola"},
            ],
        }
        archivo = tmp_path / "chat.json"
        archivo.write_text(json.dumps(export), encoding="utf-8")

        mensajes = TelegramParser().parse(archivo)

        assert len(mensajes) == 1
        assert mensajes[0].text == "hola"

    def test_telegram_parser_rechaza_json_sin_messages(self, tmp_path):
        from src.adapters.telegram_parser import TelegramParser
        from src.domain.chat_export import FormatoDeChatInvalido

        archivo = tmp_path / "chat.json"
        archivo.write_text(json.dumps({"name": "x", "type": "personal_chat"}), encoding="utf-8")

        with pytest.raises(FormatoDeChatInvalido):
            TelegramParser().parse(archivo)

    def test_telegram_parser_rechaza_json_invalido(self, tmp_path):
        from src.adapters.telegram_parser import TelegramParser
        from src.domain.chat_export import FormatoDeChatInvalido

        archivo = tmp_path / "chat.json"
        archivo.write_text("{ esto no es json valido ", encoding="utf-8")

        with pytest.raises(FormatoDeChatInvalido):
            TelegramParser().parse(archivo)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
