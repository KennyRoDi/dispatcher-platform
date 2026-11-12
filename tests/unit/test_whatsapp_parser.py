"""Pruebas unitarias del parser de exportaciones de WhatsApp (F-02).

TDD: pruebas en rojo, sin implementacion aun.
"""
from datetime import datetime, timezone

import pytest

from src.adapters.chat_export_generator import generate_chat, render_whatsapp


class TestWhatsAppParser:
    def test_whatsapp_parser_produce_mensajes_utc_utf8(self, tmp_path):
        from src.adapters.whatsapp_parser import WhatsAppParser

        originales = generate_chat(seed=1, count=5)
        archivo = tmp_path / "chat.txt"
        archivo.write_text(render_whatsapp(originales), encoding="utf-8")

        mensajes = WhatsAppParser().parse(archivo)

        assert len(mensajes) == 5
        for original, parseado in zip(originales, mensajes):
            assert parseado.timestamp_utc == original.timestamp_utc
            assert parseado.timestamp_utc.tzinfo is not None
            assert parseado.sender == original.sender
            assert isinstance(parseado.text, str)
            assert parseado.text.encode("utf-8")  # no lanza, es UTF-8 valido

    def test_whatsapp_parser_agrupa_mensajes_multilinea(self, tmp_path):
        from src.adapters.whatsapp_parser import WhatsAppParser

        contenido = (
            "3/11/26, 08:15 - Ana Sintética: Hola, ¿ya revisaste el informe?\n"
            "3/11/26, 08:21 - Luis Sintético: Te aviso cuando termine.\n"
            "Esta línea continúa el mensaje anterior.\n"
        )
        archivo = tmp_path / "chat.txt"
        archivo.write_text(contenido, encoding="utf-8")

        mensajes = WhatsAppParser().parse(archivo)

        assert len(mensajes) == 2
        assert mensajes[1].text == "Te aviso cuando termine.\nEsta línea continúa el mensaje anterior."
        assert mensajes[1].timestamp_utc == datetime(2026, 11, 3, 8, 21, tzinfo=timezone.utc)

    def test_whatsapp_parser_rechaza_formato_no_reconocido(self, tmp_path):
        from src.adapters.whatsapp_parser import WhatsAppParser
        from src.domain.chat_export import FormatoDeChatInvalido

        archivo = tmp_path / "no_es_chat.txt"
        archivo.write_text("esto no tiene ninguna cabecera de WhatsApp\nni esta otra linea\n", encoding="utf-8")

        with pytest.raises(FormatoDeChatInvalido):
            WhatsAppParser().parse(archivo)

    def test_whatsapp_parser_rechaza_bytes_no_utf8(self, tmp_path):
        from src.adapters.whatsapp_parser import WhatsAppParser
        from src.domain.chat_export import FormatoDeChatInvalido

        archivo = tmp_path / "chat_roto.txt"
        archivo.write_bytes(b"3/11/26, 08:15 - Ana: hola \xff\xfe mundo\n")

        with pytest.raises(FormatoDeChatInvalido):
            WhatsAppParser().parse(archivo)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
