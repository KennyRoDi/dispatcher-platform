"""Montaje de extremo a extremo del pipeline tipado (F-43, parte 5).

Coordinador real (TestClient sobre fakeredis), workers tipados reales con el Reporter real que llama al
coordinador, almacén cifrado en memoria y modelos falsos de tests/dobles.py: ningún modelo real, ni red ni reloj.
"""
import hashlib
import io
import json
import threading
from pathlib import Path

import fakeredis
from fastapi.testclient import TestClient

from scripts.reaper import Reaper
from src.adapters.encrypted_object_store import EncryptedObjectStore
from src.adapters.envelope_cipher import EnvelopeCipher
from src.adapters.redis_alert_stream import RedisAlertStream
from src.adapters.redis_finding_store import RedisFindingStore
from src.adapters.redis_retry_scheduler import RedisRetryScheduler
from src.adapters.redis_type_queue import RedisTypeQueue
from src.application.alerting import AlertingFindingStore
from src.domain.admission import FootprintTable
from src.domain.frame_sampling import Frame
from src.domain.image_detection import Detection
from src.domain.subtask import ContentKind
from src.domain.text_analysis import MessageAnalysis
from src.domain.transcription import TranscriptSegment
from src.infrastructure.analizadores import ConstructoresDeModelos, crear_analizador
from src.workers.config import Settings
from src.workers.multimedia_processor import CorruptInputError
from src.workers.reporter import Reporter
from src.workers.typed_worker import TypedWorker, caso_cancelado, crear_analisis
from tests.dobles import FakeClock, FakeKeyProvider, FakeObjectStore, FakeResourceReader, FakeTextModels

COORD = "http://coord"
ILEGIBLE = b"ILEGIBLE"
SIN_FOTOGRAMAS = b"SIN_FOTOGRAMAS"

VIDEO_FALSO = b"video falso mp4"
FOTO_FALSA = b"jpg falso"
VOZ_FALSA = b"mp3 falso"
WHATSAPP = (
    "12/10/26, 09:00 - Ana: hola, como estas\n"
    "12/10/26, 09:01 - Beto: bien, hay que pagar la deuda\n"
).encode()
TELEGRAM = json.dumps({"messages": [
    {"type": "message", "id": 1, "date": "2026-10-12T09:00:00", "from": "Ana", "text": "nos vemos en la plaza"},
    {"type": "message", "id": 2, "date": "2026-10-12T09:05:00", "from": "Beto", "text": "vas a ver lo que pasa"},
]}).encode()
AMENAZA = MessageAnalysis(
    lemmas=("ver",), sentiment_label="negativo", sentiment_score=0.9, offense_score=0.2, threat_patterns=("vas_a_ver",)
)
OFENSA = MessageAnalysis(
    lemmas=("deuda",), sentiment_label="negativo", sentiment_score=0.8, offense_score=0.9, threat_patterns=()
)
ARMA = Detection("knife", 0.9, (10, 20, 30, 40))
SEGMENTOS = [TranscriptSegment(0.0, 2.0, "hola a todos", 0.9), TranscriptSegment(2.0, 4.0, "hasta luego", 0.9)]


def sha256(contenido: bytes) -> str:
    return hashlib.sha256(contenido).hexdigest()


class SesionDelCoordinador:
    def __init__(self, client):
        self.client = client
        self.payloads = []

    def post(self, url, json=None, timeout=None):
        assert url.startswith(COORD)
        self.payloads.append(json)
        return self.client.post(url[len(COORD):], json=json)


class _Subidas:
    def __init__(self):
        self.guardadas = set()

    def already_stored(self, sha):
        return sha in self.guardadas


class ModelosDeTexto(FakeTextModels):
    def __init__(self, por_texto=None):
        super().__init__(por_texto)
        self.fallos = []

    def analyze_messages(self, texts):
        if self.fallos:
            raise self.fallos.pop(0)
        return super().analyze_messages(texts)


class DetectorFalso:
    def __init__(self, detecciones):
        self.detecciones = detecciones
        self.rutas = []

    def detect(self, path):
        self.rutas.append(Path(path))
        if Path(path).read_bytes().startswith(ILEGIBLE):
            raise CorruptInputError("imagen ilegible")
        return list(self.detecciones)


class TranscriptorFalso:
    def __init__(self, segmentos):
        self.segmentos = segmentos

    def transcribe(self, path):
        if Path(path).read_bytes().startswith(ILEGIBLE):
            raise CorruptInputError("audio ilegible")
        return list(self.segmentos)


class ExtractorFalso:
    """Reemplaza a FFmpeg: escribe un JPEG falso por marca de tiempo, o falla si el video es ilegible."""

    def __init__(self, pipeline, supervisor):
        self._pipeline = pipeline
        self._supervisor = supervisor

    def extract(self, path, out_dir):
        if Path(path).read_bytes().startswith((ILEGIBLE, SIN_FOTOGRAMAS)):
            raise CorruptInputError(f"{Path(path).name}: no se pudo leer el video")
        if self._pipeline.al_extraer is not None:
            self._pipeline.al_extraer(self._supervisor, out_dir)
        frames = []
        for indice, t_s in enumerate(self._pipeline.marcas):
            frame = Path(out_dir) / f"frame_{indice:04d}.jpg"
            frame.write_bytes(b"jpg")
            frames.append(Frame(frame, t_s))
        return frames


class Pipeline:
    def __init__(self, tmp_path, monkeypatch, conexion, main, rutas_casos, rutas_reporte):
        self.tmp_path = Path(tmp_path)
        self.work_dir = self.tmp_path / "work"
        self.redis = fakeredis.FakeRedis(decode_responses=True)
        monkeypatch.setattr(conexion, "redis_client", self.redis)
        self.reloj = FakeClock()
        self.client = TestClient(main.app)
        self.almacen = EncryptedObjectStore(FakeObjectStore(), EnvelopeCipher(FakeKeyProvider(bytes(range(32)))))
        self.subidas = _Subidas()
        self.sesion = SesionDelCoordinador(self.client)
        self._overrides = {
            rutas_casos._obtener_subidas_opcional: lambda: self.subidas,
            rutas_reporte.obtener_almacen: lambda: self.almacen,
        }
        main.app.dependency_overrides.update(self._overrides)
        self._main = main
        self.modelos_de_texto = ModelosDeTexto({"vas a ver lo que pasa": AMENAZA, "bien, hay que pagar la deuda": OFENSA})
        self.detector = DetectorFalso([ARMA])
        self.transcriptor = TranscriptorFalso(SEGMENTOS)
        self.marcas = [0.0, 5.0]
        self.al_extraer = None
        self.workers: dict[str, TypedWorker] = {}
        self.max_intentos = 3
        self.supervisor = None

    def cerrar(self):
        for override in self._overrides:
            self._main.app.dependency_overrides.pop(override, None)

    def subir(self, contenido: bytes) -> str:
        sha = sha256(contenido)
        self.almacen.put(sha, io.BytesIO(contenido), len(contenido))
        self.subidas.guardadas.add(sha)
        return sha

    def crear_caso(self, fuentes: dict[str, bytes], **extra):
        cuerpo = {"sources": [{"sha256": self.subir(contenido), "name": nombre} for nombre, contenido in fuentes.items()]}
        respuesta = self.client.post("/cases", json={**cuerpo, **extra})
        assert respuesta.status_code == 201, respuesta.text
        return respuesta.json()["case_id"]

    def worker(self, kind: str, worker_id: str | None = None, node: str = "nodo-a", uso=None, heartbeat=False) -> TypedWorker:
        worker_id = worker_id or f"w-{kind}"
        settings = Settings.from_env({
            "WORKER_ID": worker_id, "WORK_DIR": str(self.work_dir), "WORKER_KIND": kind,
            f"FOOTPRINT_{kind.upper()}_BYTES": "300", "NODE_NAME": node, "NODE_IP": "10.0.0.1",
            "MAX_ATTEMPTS": str(self.max_intentos), "COORDINATOR_URL": COORD,
        })
        redis = self.redis
        constructores = ConstructoresDeModelos(
            textos=lambda ruta: self.modelos_de_texto, detector=lambda ruta, pesos: self.detector,
            transcriptor=lambda ruta: self.transcriptor,
        )
        hallazgos = AlertingFindingStore(RedisFindingStore(redis), RedisAlertStream(redis, self.reloj))
        holder: dict[str, TypedWorker] = {}
        analisis = crear_analisis(
            ContentKind(kind), crear_analizador(kind, {}, constructores), self.almacen, hallazgos, self.work_dir,
            caso_cancelado(redis), {}, lambda: holder["w"].subprocesos,
            extractor=lambda muestreo, supervisor: ExtractorFalso(self, supervisor),
        )
        holder["w"] = TypedWorker(
            settings, analisis, RedisTypeQueue(redis, 0), redis_client=redis,
            reporter=Reporter(settings, redis, session=self.sesion, delays=()),
            resource_reader=FakeResourceReader(uso) if uso is not None else None,
            footprints=FootprintTable({kind: 300}), admission_margin=100,
            retry_scheduler=RedisRetryScheduler(redis, self.reloj), jitter=lambda: 0.0, clock=self.reloj,
            heartbeat_enabled=heartbeat, supervisor=self.supervisor,
        )
        self.workers[worker_id] = holder["w"]
        return holder["w"]

    def reaper(self) -> Reaper:
        settings = Settings.from_env({"MAX_ATTEMPTS": str(self.max_intentos), "COORDINATOR_URL": COORD})
        reporter = Reporter(settings, self.redis, session=self.sesion, delays=())
        return Reaper(
            settings, self.redis, reporter, clock=lambda: self.reloj.now().timestamp(),
            retry_scheduler=RedisRetryScheduler(self.redis, self.reloj),
        )

    def drenar(self, *workers, limite=50) -> int:
        procesadas = 0
        for _ in range(limite):
            avance = sum(1 for worker in workers if worker.poll_once(timeout=0))
            if not avance:
                break
            procesadas += avance
        return procesadas

    def caso(self, case_id: str) -> dict:
        return self.client.get(f"/cases/{case_id}").json()["case"]

    def subtareas(self, case_id: str) -> dict[tuple[str, str], dict]:
        lista = self.client.get(f"/cases/{case_id}").json()["subtasks"]
        return {(s["task_type"], s["file_path"]): s for s in lista}

    def hallazgos(self, case_id: str):
        return RedisFindingStore(self.redis).list(case_id)

    def alertas(self) -> list[tuple[str, str]]:
        return [(campos["kind"], campos["case_id"]) for _id, campos in self.redis.xrange("alerts")]

    def reporte(self, case_id: str) -> dict:
        respuesta = self.client.get(f"/cases/{case_id}/consolidated-report")
        assert respuesta.status_code == 200, respuesta.text
        return respuesta.json()

    def colas(self) -> dict[str, int]:
        return {cola: self.redis.llen(cola) for cola in ("queue:text", "queue:image", "queue:audio")}

    def en_vuelo(self) -> int:
        return sum(self.redis.llen(clave) for clave in self.redis.keys("inflight:*"))


class SupervisorFalso:
    def __init__(self):
        self.cancelados = []
        self.arrancados = {}
        self.cancelado = threading.Event()

    def start(self, argv, scratch):
        Path(scratch).mkdir(parents=True, exist_ok=True)
        pid = 4000 + len(self.arrancados)
        self.arrancados[pid] = argv
        return pid

    def poll(self, pid):
        return None

    def cancel(self, pid):
        self.cancelados.append(pid)
        self.cancelado.set()
