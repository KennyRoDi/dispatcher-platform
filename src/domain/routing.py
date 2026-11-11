from collections.abc import Mapping, Sequence

from src.domain.subtask import ContentKind, Subtask


class NoLiveNodeClass(ValueError):
    pass


class RoutingTable:
    def __init__(self, rules: Mapping[ContentKind, Sequence[str]]) -> None:
        validated: dict[ContentKind, tuple[str, ...]] = {}
        for kind in ContentKind:
            classes = tuple(rules.get(kind, ()))
            if not classes or any(not name for name in classes) or len(set(classes)) != len(classes):
                raise ValueError(f"ruta invalida para {kind.value}: {classes}")
            validated[kind] = classes
        unknown = set(rules) - set(ContentKind)
        if unknown:
            raise ValueError(f"tipos de contenido desconocidos: {sorted(map(str, unknown))}")
        self._rules = validated

    def route(self, subtask: Subtask, live_classes: Sequence[str]) -> str:
        preferred = self._rules[subtask.kind]
        for name in preferred:
            if name in live_classes:
                return name
        raise NoLiveNodeClass(
            f"sin clase viva para {subtask.kind.value}: se requiere una de {list(preferred)}"
        )
