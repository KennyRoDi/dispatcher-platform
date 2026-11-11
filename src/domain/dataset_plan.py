import random
from numbers import Integral
from dataclasses import dataclass
from enum import Enum

MIB = 1024 * 1024
IMAGE_CATEGORIES = ("objetos", "paisajes", "documentos", "personas")
AUDIO_SECONDS_RANGE = (5, 300)
MIN_LIGHT = 5
MIN_HEAVY = 5
MIN_HETEROGENEOUS = MIN_LIGHT + MIN_HEAVY
MIN_HEAVY_BYTES = 200 * MIB
MIN_CASES = 40
MIN_MESSAGES = 20_000
MIN_IMAGES = 300
MIN_AUDIOS = 150
MAX_CASES = 10_000
MAX_MESSAGES = 10_000_000
MAX_IMAGES = 100_000
MAX_AUDIOS = 100_000
# Con 4 GiB el video dura unos 15 minutos y ffmpeg lo codifica muy por debajo de FFMPEG_TIMEOUT_SECONDS (209 MiB en 1,1 s).
MAX_HEAVY_BYTES = 4 * 1024 * MIB
MAXIMUMS = {"cases": MAX_CASES, "messages": MAX_MESSAGES, "images": MAX_IMAGES, "audios": MAX_AUDIOS, "heavy_bytes": MAX_HEAVY_BYTES}


class Level(str, Enum):
    LIGHT = "liviano"
    HEAVY = "pesado"
    NONE = "no"


ALL_KINDS = ("texto", "imagen", "audio", "documento")
HEAVY_KINDS = ("texto", "imagen", "audio", "video", "documento")
SIMPLE_KINDS = ("texto", "imagen", "audio")


@dataclass(frozen=True)
class DatasetParams:
    cases: int = MIN_CASES
    light_heterogeneous: int = 5
    heavy_heterogeneous: int = 5
    messages: int = MIN_MESSAGES
    images: int = MIN_IMAGES
    audios: int = MIN_AUDIOS
    heavy_bytes: int = MIN_HEAVY_BYTES

    def __post_init__(self) -> None:
        for name, value in vars(self).items():
            if isinstance(value, bool) or not isinstance(value, Integral):
                raise ValueError(f"{name} debe ser un entero: {value!r}")
            object.__setattr__(self, name, int(value))
            if value < 0:
                raise ValueError(f"{name} no puede ser negativo: {value}")
            if value > MAXIMUMS.get(name, value):
                raise ValueError(f"{name} no puede superar {MAXIMUMS[name]}: {value}")
        if self.cases < 1:
            raise ValueError("cases debe ser al menos 1")


@dataclass(frozen=True)
class CasePlan:
    name: str
    heterogeneo: str
    kinds: tuple[str, ...]
    messages: int
    images: int
    audios: int
    heavy_bytes: int


@dataclass(frozen=True)
class DatasetPlan:
    seed: int
    cases: tuple[CasePlan, ...]
    image_positive_ratio: dict[str, float]
    audio_durations: tuple[int, ...]


def plan_dataset(seed: int, params: DatasetParams) -> DatasetPlan:
    rng = random.Random(seed)
    layout = _case_layout(params, rng)
    _ensure_kind_holders(layout, params)
    messages = _split(params.messages, "texto", layout, rng)
    images = _split(params.images, "imagen", layout, rng)
    audios = _split(params.audios, "audio", layout, rng)
    cases = tuple(
        CasePlan(
            name=f"caso-{index + 1:02d}",
            heterogeneo=level.value,
            kinds=kinds,
            messages=messages.get(index, 0),
            images=images.get(index, 0),
            audios=audios.get(index, 0),
            heavy_bytes=params.heavy_bytes if level is Level.HEAVY else 0,
        )
        for index, (level, kinds) in enumerate(layout)
    )
    total_audios = sum(case.audios for case in cases)
    return DatasetPlan(
        seed=seed,
        cases=cases,
        image_positive_ratio={c: round(rng.uniform(0.1, 0.5), 2) for c in IMAGE_CATEGORIES},
        audio_durations=tuple(rng.randint(*AUDIO_SECONDS_RANGE) for _ in range(total_audios)),
    )


# Un nombre con separadores, absoluto o ".." saldria del directorio de salida.
def checked_case_name(name: str) -> str:
    if name in ("", ".", "..") or "/" in name or "\\" in name or "\x00" in name:
        raise ValueError(f"nombre de caso invalido: {name!r}")
    return name


def check_minimums(plan: DatasetPlan) -> list[str]:
    cases = plan.cases
    light = [c for c in cases if c.heterogeneo == Level.LIGHT.value]
    heavy_heterogeneous = [c for c in cases if c.heterogeneo == Level.HEAVY.value]
    heavy = [c for c in heavy_heterogeneous if c.heavy_bytes >= MIN_HEAVY_BYTES]
    checks = [
        (len(cases), MIN_CASES, "casos"),
        (len(light), MIN_LIGHT, "casos heterogeneos livianos"),
        (len(heavy_heterogeneous), MIN_HEAVY, "casos heterogeneos pesados"),
        (len(heavy), MIN_HEAVY, "casos pesados de al menos 200 MiB"),
        (sum(c.messages for c in cases), MIN_MESSAGES, "mensajes"),
        (sum(c.images for c in cases), MIN_IMAGES, "imagenes"),
        (sum(c.audios for c in cases), MIN_AUDIOS, "audios"),
    ]
    return [f"{label}: {found} de al menos {minimum}" for found, minimum, label in checks if found < minimum]


def _case_layout(params: DatasetParams, rng: random.Random) -> list[tuple[Level, tuple[str, ...]]]:
    layout = [(Level.LIGHT, ALL_KINDS)] * params.light_heterogeneous
    layout += [(Level.HEAVY, HEAVY_KINDS)] * params.heavy_heterogeneous
    for _ in range(max(0, params.cases - len(layout))):
        layout.append((Level.NONE, _simple_kinds(rng)))
    return layout[: params.cases]


def _ensure_kind_holders(layout: list, params: DatasetParams) -> None:
    totals = {"texto": params.messages, "imagen": params.images, "audio": params.audios}
    for kind, total in totals.items():
        if total and not any(kind in kinds for _, kinds in layout):
            level, kinds = layout[0]
            layout[0] = (level, kinds + (kind,))


def _simple_kinds(rng: random.Random) -> tuple[str, ...]:
    count = rng.randint(1, 2)
    return tuple(rng.sample(SIMPLE_KINDS, count))


def _split(total: int, kind: str, layout: list, rng: random.Random) -> dict[int, int]:
    holders = [index for index, (_, kinds) in enumerate(layout) if kind in kinds]
    if not holders:
        return {}
    shares = {index: total // len(holders) for index in holders}
    for index in rng.sample(holders, total % len(holders)):
        shares[index] += 1
    return shares
