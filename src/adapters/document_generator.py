import random
from dataclasses import dataclass
from pathlib import Path

from src.adapters.chat_export_generator import CONTINUATION_PHRASES, NEUTRAL_PHRASES, SEED_STRIDE
from src.adapters.media_generator import LICENSE_NAME, ORIGIN
from src.domain.dataset_plan import DatasetPlan, Level, checked_case_name

DOCUMENT_KIND = "documento"
DOCUMENTS_PER_CASE = 2
DOCUMENT_SUFFIXES = (".txt", ".md")
SENTENCES_RANGE = (4, 9)
TITLE = "Notas del equipo"


@dataclass(frozen=True)
class DocumentFile:
    case: str
    kind: str
    path: Path
    origen: str
    licencia: str
    semilla: int


def generate_documents(plan: DatasetPlan, out_dir: Path) -> list[DocumentFile]:
    files: list[DocumentFile] = []
    for index, case in enumerate(plan.cases):
        if case.heterogeneo != Level.LIGHT.value:
            continue
        case_dir = out_dir / checked_case_name(case.name)
        rng = random.Random(plan.seed * SEED_STRIDE + index)
        for number in range(DOCUMENTS_PER_CASE):
            path = case_dir / f"{case.name}-documento-{number + 1:03d}{DOCUMENT_SUFFIXES[number % len(DOCUMENT_SUFFIXES)]}"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(_text(rng).encode("utf-8"))
            files.append(DocumentFile(case.name, DOCUMENT_KIND, path, ORIGIN, LICENSE_NAME, plan.seed))
    return files


def _text(rng: random.Random) -> str:
    count = rng.randint(*SENTENCES_RANGE)
    sentences = [rng.choice(NEUTRAL_PHRASES + CONTINUATION_PHRASES) for _ in range(count)]
    return f"# {TITLE}\n\n" + "\n\n".join(f"{sentence}." for sentence in sentences) + "\n"
