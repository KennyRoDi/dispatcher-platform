"""Selector de ConversationParser por extensión de la fuente (F-43, SUP-47)."""
from collections.abc import Iterable, Mapping
from pathlib import Path

from src.adapters.telegram_parser import TelegramParser
from src.adapters.whatsapp_parser import WhatsAppParser
from src.application.ports import ConversationParser
from src.domain.chat_message import ChatMessage


class ExtensionSinParser(ValueError):
    pass


class ParserPorExtension:
    def __init__(self, parsers: Mapping[str, ConversationParser] | None = None) -> None:
        self._parsers = dict(parsers) if parsers is not None else {".txt": WhatsAppParser(), ".json": TelegramParser()}

    def parse(self, path: Path) -> Iterable[ChatMessage]:
        extension = Path(path).suffix.lower()
        parser = self._parsers.get(extension)
        if parser is None:
            admitidas = ", ".join(sorted(self._parsers))
            raise ExtensionSinParser(f"no hay parser para la extensión {extension or '(sin extensión)'}; se admiten {admitidas}")
        return parser.parse(path)
