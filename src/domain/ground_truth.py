from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from src.domain.finding import Finding


@dataclass(frozen=True)
class GroundTruthItem:
    item_id: str
    expected: frozenset[str]


@dataclass(frozen=True)
class ObservedItem:
    item_id: str
    observed: frozenset[str]


def observed_from_findings(item_id: str, findings: Iterable[Finding]) -> ObservedItem:
    return ObservedItem(item_id, frozenset(finding.category for finding in findings))


@dataclass(frozen=True)
class CategoryScore:
    category: str
    tp: int
    fp: int
    fn: int
    tn: int

    @property
    def hits(self) -> int:
        return self.tp + self.tn

    @property
    def errors(self) -> int:
        return self.fp + self.fn

    @property
    def precision(self) -> float | None:
        return _ratio(self.tp, self.tp + self.fp)

    @property
    def recall(self) -> float | None:
        return _ratio(self.tp, self.tp + self.fn)


@dataclass(frozen=True)
class Comparison:
    scores: tuple[CategoryScore, ...]
    total: int
    exact_matches: int

    @property
    def accuracy(self) -> float | None:
        return _ratio(self.exact_matches, self.total)


def _ratio(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def _require_unique(ids: Sequence[str], label: str) -> None:
    repeated = [item_id for item_id, n in Counter(ids).items() if n > 1]
    if repeated:
        raise ValueError(f"{label} repetidos: {sorted(repeated, key=repr)}")


def _score(category: str, pairs: Sequence[tuple[frozenset[str], frozenset[str]]]) -> CategoryScore:
    tp = sum(category in expected and category in seen for expected, seen in pairs)
    fp = sum(category not in expected and category in seen for expected, seen in pairs)
    fn = sum(category in expected and category not in seen for expected, seen in pairs)
    return CategoryScore(category, tp, fp, fn, len(pairs) - tp - fp - fn)


def compare(
    truth: Sequence[GroundTruthItem],
    observed: Sequence[ObservedItem],
    categories: Iterable[str] | None = None,
) -> Comparison:
    if not truth:
        raise ValueError("la muestra etiquetada está vacía")
    _require_unique([item.item_id for item in truth], "item_id de etiquetas")
    _require_unique([item.item_id for item in observed], "item_id de salidas")
    seen_by_id = {item.item_id: item.observed for item in observed}
    if seen_by_id.keys() != {item.item_id for item in truth}:
        raise ValueError("las etiquetas y las salidas no cubren los mismos elementos")
    pairs = [(item.expected, seen_by_id[item.item_id]) for item in truth]
    names = set(categories) if categories is not None else set().union(*(p[0] | p[1] for p in pairs))
    scores = tuple(_score(name, pairs) for name in sorted(names))
    return Comparison(scores, len(pairs), sum(expected == seen for expected, seen in pairs))
