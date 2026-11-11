import hashlib
import hmac
import json
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass

GENESIS_HASH = "0" * 64
FIELDS = ("ts", "evidence_sha256", "operation", "result_sha256", "actor")
LINE_KEYS = frozenset(("seq", *FIELDS, "prev_hash", "entry_hash"))


@dataclass(frozen=True)
class CustodyEntry:
    seq: int
    ts: str
    evidence_sha256: str
    operation: str
    result_sha256: str
    actor: str
    prev_hash: str
    entry_hash: str

    def line(self) -> str:
        return _canonical(asdict(self))


@dataclass(frozen=True)
class Anchor:
    seq: int
    entry_hash: str
    mac: str


@dataclass(frozen=True)
class Violation:
    position: int
    kind: str
    detail: str


def seal(key: bytes, prev_hash: str, seq: int, fields: Mapping[str, str]) -> CustodyEntry:
    content = {"seq": seq, **{name: fields[name] for name in FIELDS}}
    if not _is_seq(seq) or not all(_is_text(content[name]) for name in FIELDS) or not _is_text(prev_hash):
        raise ValueError("seq debe ser un entero no negativo y los demás campos, texto UTF-8")
    return CustodyEntry(**content, prev_hash=prev_hash, entry_hash=_entry_mac(key, prev_hash, content))


def make_anchor(key: bytes, seq: int, entry_hash: str) -> Anchor:
    return Anchor(seq=seq, entry_hash=entry_hash, mac=_anchor_mac(key, seq, entry_hash))


def verify_chain(lines: Sequence[str], key: bytes, anchor: Anchor | None) -> list[Violation]:
    previous_hash = GENESIS_HASH
    hashes: list[str] = []
    for position, line in enumerate(lines, start=1):
        entry = _parse(line)
        broken = _invalid_entry() if entry is None else _broken_link(key, entry, position - 1, previous_hash)
        if broken:
            return [Violation(position, *broken)]
        previous_hash = entry["entry_hash"]
        hashes.append(previous_hash)
    return _check_anchor(key, hashes, anchor)


def _invalid_entry() -> tuple[str, str]:
    return "entrada", "la línea no es una entrada de custodia válida"


def _broken_link(key: bytes, entry: dict, expected_seq: int, previous_hash: str) -> tuple[str, str] | None:
    if entry["seq"] != expected_seq or not _same(entry["prev_hash"], previous_hash):
        return "enlace", f"se esperaba seq {expected_seq} enlazada a la entrada anterior"
    content = {name: entry[name] for name in ("seq", *FIELDS)}
    if not _same(entry["entry_hash"], _entry_mac(key, entry["prev_hash"], content)):
        return "sello", "el HMAC de la entrada no coincide"
    return None


def _parse(line: str) -> dict | None:
    try:
        entry = json.loads(line, object_pairs_hook=_without_duplicates)
    except (ValueError, RecursionError):
        return None
    if not isinstance(entry, dict) or set(entry) != LINE_KEYS:
        return None
    if not _is_seq(entry["seq"]):
        return None
    if not all(_is_text(value) for name, value in entry.items() if name != "seq"):
        return None
    return entry


def _without_duplicates(pairs: list[tuple[str, object]]) -> dict:
    keys = [name for name, _ in pairs]
    if len(set(keys)) != len(keys):
        raise ValueError("clave duplicada")
    return dict(pairs)


def _is_seq(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _is_text(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        return False
    return True


def _check_anchor(key: bytes, hashes: list[str], anchor: Anchor | None) -> list[Violation]:
    if anchor is None:
        return [Violation(len(hashes), "ancla", "falta el ancla del último eslabón")] if hashes else []
    if not (_is_seq(anchor.seq) and _is_text(anchor.entry_hash) and _is_text(anchor.mac)):
        return [Violation(max(len(hashes), 1), "ancla", "el ancla está mal formada")]
    position = anchor.seq + 1
    if not _same(anchor.mac, _anchor_mac(key, anchor.seq, anchor.entry_hash)):
        return [Violation(position, "ancla", "el sello del ancla no coincide")]
    if anchor.seq >= len(hashes):
        return [Violation(position, "truncado", "el log termina antes del último eslabón anclado")]
    if anchor.seq < len(hashes) - 2:
        return [Violation(position, "ancla", "el ancla está atrasada más de una entrada")]
    if not _same(hashes[anchor.seq], anchor.entry_hash):
        return [Violation(position, "ancla", "el ancla no coincide con el eslabón de su posición")]
    return []


def _canonical(content: Mapping) -> str:
    text = json.dumps(content, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    # str.splitlines() también parte en estos separadores, que ensure_ascii=False deja sin escapar.
    return text.replace("\u2028", "\\u2028").replace("\u2029", "\\u2029").replace("\x85", "\\u0085")


def _entry_mac(key: bytes, prev_hash: str, content: Mapping) -> str:
    message = prev_hash.encode() + _canonical(content).encode("utf-8")
    return hmac.new(key, message, hashlib.sha256).hexdigest()


def _anchor_mac(key: bytes, seq: int, entry_hash: str) -> str:
    return hmac.new(key, f"head:{seq}:{entry_hash}".encode(), hashlib.sha256).hexdigest()


def _same(left: str, right: str) -> bool:
    return hmac.compare_digest(left.encode("utf-8"), right.encode("utf-8"))
