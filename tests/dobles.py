import io
import os
from collections import defaultdict
from datetime import datetime, timezone

from src.application.ports import KeyUnavailable
from src.domain.alert_policy import StoredAlert
from src.domain.custody_chain import GENESIS_HASH, make_anchor, seal
from src.domain.resources import ResourceUsage
from src.domain.subtask import QueueFull
from src.domain.text_analysis import MessageAnalysis

ANALISIS_NEUTRAL = MessageAnalysis(
    lemmas=("hola",), sentiment_label="neutral", sentiment_score=0.8, offense_score=0.0, threat_patterns=()
)


class FakeClock:
    def __init__(self, inicio=None):
        self._ahora = inicio or datetime(2026, 11, 3, tzinfo=timezone.utc)

    def now(self):
        return self._ahora

    def advance(self, delta):
        self._ahora += delta


class FakeAnalyzer:
    def __init__(self, hallazgos=()):
        self.hallazgos = list(hallazgos)

    def analyze(self, path):
        return list(self.hallazgos)


class FakeConversationParser:
    def __init__(self, mensajes=()):
        self.mensajes = list(mensajes)

    def parse(self, path):
        return list(self.mensajes)


class FakeTextModels:
    def __init__(self, por_texto=None):
        self.por_texto = por_texto or {}
        self.llamadas = []

    def analyze_messages(self, texts):
        self.llamadas.append(list(texts))
        return [self.por_texto.get(texto, ANALISIS_NEUTRAL) for texto in texts]


class FakeObjectStore:
    def __init__(self):
        self.objetos = {}

    def exists(self, sha256):
        return sha256 in self.objetos

    def put(self, sha256, content, size):
        self.objetos.setdefault(sha256, content.read())

    def open(self, sha256):
        return io.BytesIO(self.objetos[sha256])


class FakeKeyProvider:
    def __init__(self, kek=None):
        self._kek = kek

    def kek(self):
        if self._kek is None:
            raise KeyUnavailable("sin KEK")
        return self._kek


class FakeWorkQueue:
    def __init__(self, capacidad=100):
        self.capacidad = capacidad
        self.colas = defaultdict(list)
        self.tomadas = defaultdict(list)

    def has_capacity(self, queue):
        return len(self.colas[queue]) < self.capacidad

    def enqueue(self, queue, subtask):
        if not self.has_capacity(queue):
            raise QueueFull(queue)
        self.colas[queue].append(subtask)

    def take(self, queue, worker_id, timeout):
        if not self.colas[queue]:
            return None
        subtarea = self.colas[queue].pop(0)
        self.tomadas[worker_id].append(subtarea)
        return subtarea

    def in_flight(self, worker_id):
        return list(self.tomadas[worker_id])

    def acknowledge(self, worker_id, subtask):
        self.tomadas[worker_id].remove(subtask)


class FakeFindingStore:
    def __init__(self):
        self.hallazgos = defaultdict(list)

    def add(self, case_id, findings):
        self.hallazgos[case_id].extend(findings)

    def list(self, case_id):
        return list(self.hallazgos[case_id])


class FakeCustodyLog:
    def __init__(self, key=None, clock=None):
        self.key = key if key is not None else os.urandom(32)
        self.clock = clock or FakeClock()
        self.entradas = []

    def record(self, evidence_sha256, operation, result_sha256, actor):
        previo = self.entradas[-1].entry_hash if self.entradas else GENESIS_HASH
        campos = {
            "ts": self.clock.now().isoformat(),
            "evidence_sha256": evidence_sha256,
            "operation": operation,
            "result_sha256": result_sha256,
            "actor": actor,
        }
        self.entradas.append(seal(self.key, previo, len(self.entradas), campos))

    def leer(self):
        if not self.entradas:
            return [], None
        ultima = self.entradas[-1]
        return [e.line() for e in self.entradas], make_anchor(self.key, ultima.seq, ultima.entry_hash)


class FakeRoutingPolicy:
    def route(self, subtask, live_classes):
        return live_classes[0]


class FakeResourceReader:
    def __init__(self, uso=None):
        self.uso = uso or ResourceUsage("w1", memory_current=0, memory_max=1024)

    def read(self):
        return self.uso


class FakeAlertPublisher:
    def __init__(self, reloj=None):
        self.alertas = []
        self.marcas = []
        self._reloj = reloj

    def publish(self, kind, case_id, detail):
        self.alertas.append((kind, case_id, detail))
        self.marcas.append(self._reloj.now() if self._reloj else None)


class FakeAlertReader:
    """Lee lo que publicó un FakeAlertPublisher con reloj; las más recientes primero."""

    def __init__(self, publicador):
        self._publicador = publicador

    def recent(self, limit):
        alertas = [
            StoredAlert(str(numero), kind, case_id, detail, marca)
            for numero, ((kind, case_id, detail), marca) in enumerate(zip(self._publicador.alertas, self._publicador.marcas), 1)
        ]
        return list(reversed(alertas))[:limit]


class FakeCaseCatalog:
    def __init__(self, casos=()):
        self.casos = {caso.case_id: caso for caso in casos}

    def add(self, caso):
        self.casos[caso.case_id] = caso

    def case(self, case_id):
        return self.casos.get(case_id)


class FakeTokenVerifier:
    def __init__(self, identidades=None):
        self.identidades = dict(identidades or {})

    def verify(self, token):
        from src.application.ports import InvalidToken

        if token not in self.identidades:
            raise InvalidToken("token desconocido")
        return self.identidades[token]

class FakeChunkStaging:
    def __init__(self):
        self.manifiestos = {}
        self.chunks = defaultdict(dict)

    def save_manifest(self, upload_id, manifest):
        self.manifiestos[upload_id] = dict(manifest)

    def load_manifest(self, upload_id):
        return dict(self.manifiestos[upload_id])

    def put_chunk(self, upload_id, index, data):
        if upload_id not in self.manifiestos:
            raise KeyError(upload_id)
        self.chunks[upload_id][index] = bytes(data)

    def received(self, upload_id):
        return set(self.chunks.get(upload_id, {}))

    def open_chunk(self, upload_id, index):
        return io.BytesIO(self.chunks[upload_id][index])

    def discard(self, upload_id):
        self.manifiestos.pop(upload_id, None)
        self.chunks.pop(upload_id, None)


class FakeCaseStateStore:
    def __init__(self):
        self._reportes = defaultdict(dict)
        self._estados = {}
        self._historial = defaultdict(list)

    def mark_reported(self, case_id, subtask_id, outcome):
        if subtask_id in self._reportes[case_id]:
            return False
        self._reportes[case_id][subtask_id] = outcome
        return True

    def counts(self, case_id):
        resultados = list(self._reportes[case_id].values())
        return resultados.count("completed"), resultados.count("failed")

    def state(self, case_id):
        return self._estados.get(case_id)

    def set_state(self, case_id, nuevo, at):
        self._estados[case_id] = nuevo
        self._historial[case_id].append((nuevo, at))

    def history(self, case_id):
        return list(self._historial[case_id])


class FakeRetryScheduler:
    def __init__(self, clock):
        self._clock = clock
        self._vencimientos = {}
        self.programadas = []

    def schedule(self, subtask_id, delay_s):
        self.programadas.append((subtask_id, delay_s))
        self._vencimientos[subtask_id] = self._clock.now().timestamp() + delay_s

    def promote_due(self, now):
        vencidas = sorted(
            (vencimiento, subtask_id)
            for subtask_id, vencimiento in self._vencimientos.items()
            if vencimiento <= now.timestamp()
        )
        for _, subtask_id in vencidas:
            del self._vencimientos[subtask_id]
        return [subtask_id for _, subtask_id in vencidas]
