import io
from collections import defaultdict
from datetime import datetime, timezone

from src.domain.resources import ResourceUsage
from src.domain.subtask import QueueFull


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


class FakeObjectStore:
    def __init__(self):
        self.objetos = {}

    def exists(self, sha256):
        return sha256 in self.objetos

    def put(self, sha256, content, size):
        self.objetos.setdefault(sha256, content.read())

    def open(self, sha256):
        return io.BytesIO(self.objetos[sha256])


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
    def __init__(self):
        self.entradas = []

    def record(self, evidence_sha256, operation, result_sha256, actor):
        self.entradas.append((evidence_sha256, operation, result_sha256, actor))


class FakeRoutingPolicy:
    def route(self, subtask, live_classes):
        return live_classes[0]


class FakeResourceReader:
    def __init__(self, uso=None):
        self.uso = uso or ResourceUsage("w1", memory_current=0, memory_max=1024)

    def read(self):
        return self.uso


class FakeAlertPublisher:
    def __init__(self):
        self.alertas = []

    def publish(self, kind, case_id, detail):
        self.alertas.append((kind, case_id, detail))

class FakeChunkStaging:
    def __init__(self):
        self.manifiestos = {}
        self.chunks = defaultdict(dict)

    def save_manifest(self, upload_id, manifest):
        self.manifiestos[upload_id] = dict(manifest)

    def load_manifest(self, upload_id):
        return dict(self.manifiestos[upload_id])

    def put_chunk(self, upload_id, index, data):
        self.chunks[upload_id][index] = bytes(data)

    def received(self, upload_id):
        return set(self.chunks.get(upload_id, {}))

    def open_chunk(self, upload_id, index):
        return io.BytesIO(self.chunks[upload_id][index])

    def discard(self, upload_id):
        self.manifiestos.pop(upload_id, None)
        self.chunks.pop(upload_id, None)