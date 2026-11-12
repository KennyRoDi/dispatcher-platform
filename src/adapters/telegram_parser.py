"""Adaptador ConversationParser para exportaciones de Telegram Desktop (F-02).

Formato: {"messages": [{"type": "message", "date": "AAAA-MM-DDTHH:MM:SS",
"from": str, "text": str}, ...]}. Mensajes de servicio (type != "message")
se ignoran. Ver AD-48: timestamps sin huso se interpretan como UTC.
"""
import json
from datetime import timezone
from datetime import datetime as dt
from pathlib import Path

from src.domain.chat_export import FormatoDeChatInvalido
from src.domain.chat_message import ChatMessage


class TelegramParser:
    def parse(self, path: Path) -> list[ChatMessage]:
        try:
            texto = path.read_text(encoding="utf-8")
        except UnicodeDecodeError as error:
            raise FormatoDeChatInvalido(path, f"no es UTF-8 válido: {error}") from error

        try:
            datos = json.loads(texto)
        except json.JSONDecodeError as error:
            raise FormatoDeChatInvalido(path, f"JSON inválido: {error}") from error

        if not isinstance(datos, dict) or "messages" not in datos:
            raise FormatoDeChatInvalido(path, "falta la clave 'messages'")

        mensajes: list[ChatMessage] = []
        for entrada in datos["messages"]:
            if entrada.get("type") != "message":
                continue
            try:
                fecha = entrada["date"]
                remitente = entrada["from"]
                texto_msg = entrada["text"]
            except KeyError as error:
                raise FormatoDeChatInvalido(path, f"mensaje sin campo {error}") from error
            if not isinstance(texto_msg, str):
                raise FormatoDeChatInvalido(path, "el campo 'text' debe ser una cadena simple")
            try:
                momento = dt.fromisoformat(fecha).replace(tzinfo=timezone.utc)
            except ValueError as error:
                raise FormatoDeChatInvalido(path, f"fecha inválida: {error}") from error
            mensajes.append(ChatMessage(momento, remitente, texto_msg, f"{path.name}:{entrada.get('id', '?')}"))

        if not mensajes:
            raise FormatoDeChatInvalido(path, "no se encontró ningún mensaje válido")
        return mensajes
