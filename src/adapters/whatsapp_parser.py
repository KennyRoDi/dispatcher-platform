"""Adaptador ConversationParser para exportaciones de WhatsApp (F-02).

Formato: una linea por mensaje, "D/M/AA, HH:MM - Remitente: Texto"; una
linea que no empieza con esa cabecera es continuacion del mensaje anterior.
Ver AD-48: timestamps sin huso se interpretan como UTC.
"""
import re
from datetime import datetime, timezone
from pathlib import Path

from src.domain.chat_export import FormatoDeChatInvalido
from src.domain.chat_message import ChatMessage

_CABECERA = re.compile(r"^(\d{1,2})/(\d{1,2})/(\d{2}), (\d{2}):(\d{2}) - ([^:]+): (.*)$")


class WhatsAppParser:
    def parse(self, path: Path) -> list[ChatMessage]:
        try:
            texto = path.read_text(encoding="utf-8")
        except UnicodeDecodeError as error:
            raise FormatoDeChatInvalido(path, f"no es UTF-8 válido: {error}") from error

        mensajes: list[ChatMessage] = []
        for numero, linea in enumerate(texto.splitlines(), start=1):
            coincidencia = _CABECERA.match(linea)
            if coincidencia:
                dia, mes, anio, hora, minuto, remitente, cuerpo = coincidencia.groups()
                momento = datetime(2000 + int(anio), int(mes), int(dia), int(hora), int(minuto), tzinfo=timezone.utc)
                mensajes.append(ChatMessage(momento, remitente.strip(), cuerpo, f"{path.name}:{numero}"))
            elif mensajes:
                anterior = mensajes[-1]
                mensajes[-1] = ChatMessage(
                    anterior.timestamp_utc, anterior.sender, f"{anterior.text}\n{linea}", anterior.source_ref
                )

        if not mensajes:
            raise FormatoDeChatInvalido(path, "ninguna línea coincide con el formato de WhatsApp")
        return mensajes
