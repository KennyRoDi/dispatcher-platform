import json
import random
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from pathlib import Path

from src.domain.chat_message import ChatMessage
from src.domain.dataset_plan import DatasetPlan, checked_case_name

SYNTHETIC_SENDERS = ("Alma Sintética", "Bruno Sintético", "Carla Sintética", "Dario Sintético")
ATTACHMENT_TEXT = "<Multimedia omitido>"
THREAT_RATIO = 0.05
THREAT_PHRASES = (
    "Te voy a arruinar la vida, esto no se queda así",
    "Más te vale callarte o vas a lamentarlo",
    "Voy a hacerte pagar por lo que hiciste",
    "Ya verás lo que te pasa si me delatas",
)
NEUTRAL_PHRASES = (
    "Buenos días, ¿cómo amaneció el equipo?",
    "Mañana revisamos el informe antes de la reunión",
    "Gracias por avisar, lo anoto en la lista",
    "¿Alguien tiene el enlace del calendario compartido?",
    "Ya terminé mi parte, la subo en un rato",
    "Me parece bien, sigamos con ese plan",
    "Llego unos minutos tarde, empiecen sin mí",
    "¿Quién se encarga de traer los materiales?",
    "Perfecto, quedamos así entonces",
    "Hoy hace mucho calor en el edificio",
    "Pásame la versión final cuando puedas",
    "Dejé las notas en la carpeta del grupo",
)
CONTINUATION_PHRASES = (
    "Te cuento los detalles más tarde",
    "Avísenme si algo no queda claro",
    "Es solo una idea, díganme qué opinan",
    "Lo dejamos pendiente para la próxima semana",
)
ATTACHMENT_PROBABILITY = 0.05
MULTILINE_PROBABILITY = 0.10
CHAT_START = datetime(2025, 1, 6, 8, 0, tzinfo=timezone.utc)
MAX_MINUTES_BETWEEN_MESSAGES = 7
SEED_STRIDE = 1_000_003
WHATSAPP_SUFFIX = ".txt"
TELEGRAM_SUFFIX = ".json"


def generate_chat(seed: int, count: int, threat_ratio: float = THREAT_RATIO) -> list[ChatMessage]:
    if not 0 <= threat_ratio <= 1:
        raise ValueError(f"threat_ratio debe estar entre 0 y 1, no {threat_ratio}")
    rng = random.Random(seed)
    threat_positions = set(rng.sample(range(count), round(count * threat_ratio)))
    instants = _increasing_minutes(rng, count)
    return [
        ChatMessage(
            timestamp_utc=instants[position],
            sender=rng.choice(SYNTHETIC_SENDERS),
            text=_threat_text(rng) if position in threat_positions else _regular_text(rng),
            source_ref=f"sintetico-{seed}-{position + 1}",
        )
        for position in range(count)
    ]


def render_whatsapp(messages: list[ChatMessage]) -> str:
    lines = [_whatsapp_entry(message) for message in messages]
    return "".join(f"{line}\n" for line in lines)


def render_telegram(messages: list[ChatMessage]) -> str:
    export = {
        "name": "Chat sintético",
        "type": "personal_chat",
        "messages": [_telegram_entry(index, message) for index, message in enumerate(messages, start=1)],
    }
    return json.dumps(export, ensure_ascii=False, indent=1)


def export_plan_chats(plan: DatasetPlan, destination: Path) -> dict[str, Path]:
    destination.mkdir(parents=True, exist_ok=True)
    files: dict[str, Path] = {}
    for index, case in enumerate(plan.cases):
        if case.messages == 0:
            continue
        messages = generate_chat(plan.seed * SEED_STRIDE + index, case.messages)
        suffix, render = _style_for(index)
        path = destination / f"{checked_case_name(case.name)}-chat{suffix}"
        path.write_bytes(render(messages).encode("utf-8"))
        files[case.name] = path
    return files


def _style_for(index: int) -> tuple[str, Callable[[list[ChatMessage]], str]]:
    if index % 2 == 0:
        return WHATSAPP_SUFFIX, render_whatsapp
    return TELEGRAM_SUFFIX, render_telegram


def _increasing_minutes(rng: random.Random, count: int) -> list[datetime]:
    instants, current = [], CHAT_START
    for _ in range(count):
        current += timedelta(minutes=rng.randint(0, MAX_MINUTES_BETWEEN_MESSAGES))
        instants.append(current)
    return instants


def _threat_text(rng: random.Random) -> str:
    return rng.choice(THREAT_PHRASES)


def _regular_text(rng: random.Random) -> str:
    roll = rng.random()
    if roll < ATTACHMENT_PROBABILITY:
        return ATTACHMENT_TEXT
    if roll < ATTACHMENT_PROBABILITY + MULTILINE_PROBABILITY:
        return f"{rng.choice(NEUTRAL_PHRASES)}\n{rng.choice(CONTINUATION_PHRASES)}"
    return rng.choice(NEUTRAL_PHRASES)


def _whatsapp_entry(message: ChatMessage) -> str:
    moment = message.timestamp_utc.astimezone(timezone.utc)
    header = f"{moment.day}/{moment.month}/{moment:%y}, {moment:%H:%M} - {message.sender}: "
    return header + message.text


def _telegram_entry(identifier: int, message: ChatMessage) -> dict:
    moment = message.timestamp_utc.astimezone(timezone.utc)
    return {
        "id": identifier,
        "type": "message",
        "date": moment.strftime("%Y-%m-%dT%H:%M:%S"),
        "date_unixtime": str(int(moment.timestamp())),
        "from": message.sender,
        "text": message.text,
    }
