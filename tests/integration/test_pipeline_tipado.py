"""Extremo a extremo del pipeline tipado (F-43, parte 5): coordinador, workers tipados y reaper sobre fakeredis."""
import json
import threading
from datetime import timedelta

import pytest

import src.coordinator.main as main
from src.coordinator import conexion, rutas_casos, rutas_reporte
from src.domain.resources import ResourceUsage
from src.domain.subtask import ContentKind, Subtask
from src.workers.cancelacion import escuchar_cancelaciones
from src.workers.multimedia_processor import ProcessingError
from tests.ayudas_pipeline_tipado import (
    FOTO_FALSA, ILEGIBLE, SIN_FOTOGRAMAS, TELEGRAM, VIDEO_FALSO, VOZ_FALSA, WHATSAPP, Pipeline, SupervisorFalso, sha256,
)

pytestmark = pytest.mark.integration

VIDEO, FOTO, VOZ = VIDEO_FALSO, FOTO_FALSA, VOZ_FALSA


@pytest.fixture
def pipe(tmp_path, monkeypatch, sin_autorizacion):
    pipeline = Pipeline(tmp_path, monkeypatch, conexion, main, rutas_casos, rutas_reporte)
    yield pipeline
    pipeline.cerrar()


def tres_workers(pipe):
    return pipe.worker("text"), pipe.worker("image"), pipe.worker("audio")


def caso_de_cuatro_fuentes(pipe):
    return pipe.crear_caso({"nota.txt": WHATSAPP, "chat.json": TELEGRAM, "foto.jpg": FOTO, "voz.mp3": VOZ, "clip.mp4": VIDEO})


def test_caso_multifuente_se_procesa_de_punta_a_punta_y_cierra_completed(pipe):
    case_id = caso_de_cuatro_fuentes(pipe)
    assert pipe.colas() == {"queue:text": 2, "queue:image": 2, "queue:audio": 2}

    assert pipe.drenar(*tres_workers(pipe)) == 6

    caso = pipe.caso(case_id)
    assert caso["status"] == "completed"
    assert int(caso["pending_subtasks"]) == 0
    assert {s["status"] for s in pipe.subtareas(case_id).values()} == {"completed"}
    hallazgos = pipe.hallazgos(case_id)
    assert pipe.redis.llen(f"case:{case_id}:findings") == len(hallazgos) > 0
    assert {"amenaza", "arma", "transcripcion", "palabras_clave"} <= {h.category for h in hallazgos}
    assert pipe.en_vuelo() == 0
    assert pipe.colas() == {"queue:text": 0, "queue:image": 0, "queue:audio": 0}
    assert not list(pipe.work_dir.rglob("*"))


def test_video_cierra_el_caso_solo_cuando_terminan_la_imagen_y_el_audio(pipe):
    case_id = pipe.crear_caso({"clip.mp4": VIDEO})
    imagen, audio = pipe.worker("image"), pipe.worker("audio")
    assert pipe.colas() == {"queue:text": 0, "queue:image": 1, "queue:audio": 1}

    assert pipe.drenar(imagen) == 1
    assert pipe.caso(case_id)["status"] == "processing"
    assert pipe.caso(case_id)["pending_subtasks"] == "1"
    assert ("caso_finalizado", case_id) not in pipe.alertas()

    assert pipe.drenar(audio) == 1
    assert pipe.caso(case_id)["status"] == "completed"
    assert ("caso_finalizado", case_id) in pipe.alertas()


def test_video_con_fotogramas_produce_hallazgos_con_posicion_de_tiempo(pipe):
    pipe.marcas = [0.0, 5.0]
    case_id = pipe.crear_caso({"clip.mp4": VIDEO})
    pipe.drenar(pipe.worker("image"), pipe.worker("audio"))

    armas = [h for h in pipe.hallazgos(case_id) if h.category == "arma"]
    assert [h.evidence.position for h in armas] == ["fotograma t=0s caja 10,20,30,40", "fotograma t=5s caja 10,20,30,40"]
    assert {h.evidence.object_sha256 for h in armas} == {sha256(VIDEO)}
    reporte = pipe.reporte(case_id)
    fotogramas = [h for h in reporte["hallazgos"] if h["categoria"] == "arma"]
    assert [h["evidencia"][0]["localizador"]["tipo"] for h in fotogramas] == ["fotograma", "fotograma"]
    assert {h["evidencia"][0]["fuente"]["file_path"] for h in fotogramas} == {"clip.mp4"}
    assert pipe.almacen.open(sha256(VIDEO)).read() == VIDEO


def test_video_sin_pista_de_audio_cierra_completed(pipe):
    pipe.transcriptor.segmentos = []
    case_id = pipe.crear_caso({"clip.mp4": VIDEO})

    pipe.drenar(pipe.worker("image"), pipe.worker("audio"))

    assert pipe.caso(case_id)["status"] == "completed"
    assert pipe.subtareas(case_id)[("audio", "clip.mp4")]["status"] == "completed"
    categorias = {h.category for h in pipe.hallazgos(case_id)}
    assert "arma" in categorias
    assert "transcripcion" not in categorias


def test_video_ilegible_cierra_partially_completed(pipe):
    contenido = SIN_FOTOGRAMAS + b" clip sin fotogramas legibles"
    case_id = pipe.crear_caso({"clip.mp4": contenido})

    pipe.drenar(pipe.worker("image"), pipe.worker("audio"))

    subtareas = pipe.subtareas(case_id)
    assert subtareas[("image", "clip.mp4")]["status"] == "failed"
    assert subtareas[("image", "clip.mp4")]["error_type"] == "CorruptInputError"
    assert subtareas[("image", "clip.mp4")]["attempts"] == "1"
    assert subtareas[("audio", "clip.mp4")]["status"] == "completed"
    assert pipe.caso(case_id)["status"] == "partially_completed"
    assert pipe.redis.zcard("retry:scheduled") == 0
    assert not list(pipe.work_dir.rglob("*"))


def test_video_ilegible_en_sus_dos_subtareas_junto_a_un_texto_valido_cierra_partially_completed(pipe):
    case_id = pipe.crear_caso({"nota.txt": WHATSAPP, "clip.mp4": ILEGIBLE + b" video roto"})

    pipe.drenar(*tres_workers(pipe))

    subtareas = pipe.subtareas(case_id)
    assert subtareas[("image", "clip.mp4")]["status"] == "failed"
    assert subtareas[("audio", "clip.mp4")]["status"] == "failed"
    assert subtareas[("text", "nota.txt")]["status"] == "completed"
    assert pipe.caso(case_id)["status"] == "partially_completed"


def test_video_ilegible_solo_cierra_failed(pipe):
    case_id = pipe.crear_caso({"clip.mp4": ILEGIBLE + b" video roto"})

    pipe.drenar(pipe.worker("image"), pipe.worker("audio"))

    assert pipe.caso(case_id)["status"] == "failed"
    assert pipe.hallazgos(case_id) == []


def test_texto_txt_y_json_se_analizan_con_su_parser(pipe):
    case_id = pipe.crear_caso({"nota.txt": WHATSAPP, "chat.json": TELEGRAM})

    pipe.drenar(pipe.worker("text"))

    assert pipe.caso(case_id)["status"] == "completed"
    por_fuente = {}
    for hallazgo in pipe.hallazgos(case_id):
        por_fuente.setdefault(hallazgo.evidence.object_sha256, []).append(hallazgo)
    assert set(por_fuente) == {sha256(WHATSAPP), sha256(TELEGRAM)}
    assert {h.evidence.position for h in por_fuente[sha256(WHATSAPP)]} == {"mensajes 0-1", "mensajes 1"}
    assert [h.category for h in por_fuente[sha256(WHATSAPP)] if h.evidence.position == "mensajes 1"] == ["ofensivo"]
    telegram = por_fuente[sha256(TELEGRAM)]
    amenaza = [h for h in telegram if h.category == "amenaza"]
    assert [h.evidence.position for h in amenaza] == ["mensajes 1"]
    assert "fuente.json:2" in amenaza[0].detail
    assert pipe.modelos_de_texto.llamadas == [
        ["hola, como estas", "bien, hay que pagar la deuda"],
        ["nos vemos en la plaza", "vas a ver lo que pasa"],
    ]


def test_texto_csv_falla_de_forma_permanente_y_legible(pipe):
    case_id = pipe.crear_caso({"datos.csv": b"a,b\n1,2\n", "foto.jpg": FOTO})

    pipe.drenar(pipe.worker("text"), pipe.worker("image"))

    csv = pipe.subtareas(case_id)[("text", "datos.csv")]
    assert csv["status"] == "failed"
    assert csv["error_type"] == "ExtensionSinParser"
    assert ".csv" in csv["error"]
    assert csv["attempts"] == "1"
    assert pipe.redis.zcard("retry:scheduled") == 0
    assert pipe.caso(case_id)["status"] == "partially_completed"


def test_extension_invalida_se_rechaza_al_crear_el_caso(pipe):
    sha = pipe.subir(b"MZ binario")

    respuesta = pipe.client.post("/cases", json={"sources": [{"sha256": sha, "name": "programa.exe"}]})

    assert respuesta.status_code == 422
    assert "programa.exe" in respuesta.text
    assert pipe.colas() == {"queue:text": 0, "queue:image": 0, "queue:audio": 0}
    assert pipe.redis.smembers("cases:registry") == set()
    assert pipe.redis.keys("subtask:*") == []


def test_utf8_invalido_falla_de_forma_permanente(pipe):
    case_id = pipe.crear_caso({"nota.txt": b"12/10/26, 09:00 - Ana: caf\xe9 \xff\xfe\n"})

    pipe.drenar(pipe.worker("text"))

    subtarea = pipe.subtareas(case_id)[("text", "nota.txt")]
    assert subtarea["status"] == "failed"
    assert subtarea["error_type"] == "FormatoDeChatInvalido"
    assert "UTF-8" in subtarea["error"]
    assert subtarea["attempts"] == "1"
    assert pipe.redis.zcard("retry:scheduled") == 0
    assert pipe.caso(case_id)["status"] == "failed"
    assert pipe.hallazgos(case_id) == []


def test_cancelacion_con_el_json_en_cola_no_procesa_la_subtarea(pipe):
    case_id = pipe.crear_caso({"nota.txt": WHATSAPP, "foto.jpg": FOTO})
    assert pipe.colas()["queue:text"] == 1

    assert pipe.client.post(f"/cases/{case_id}/cancel").status_code == 200
    texto, imagen = pipe.worker("text"), pipe.worker("image")

    assert pipe.drenar(texto, imagen) == 2

    assert pipe.modelos_de_texto.llamadas == []
    assert pipe.detector.rutas == []
    assert pipe.en_vuelo() == 0
    assert pipe.colas() == {"queue:text": 0, "queue:image": 0, "queue:audio": 0}
    assert pipe.caso(case_id)["status"] == "cancelled"
    assert pipe.hallazgos(case_id) == []
    assert pipe.sesion.payloads == []


def test_cancelacion_con_ffmpeg_en_curso_termina_el_subproceso_y_borra_los_fotogramas(pipe):
    pipe.supervisor = SupervisorFalso()
    en_ejecucion = threading.Event()

    def ffmpeg_en_curso(supervisor, out_dir):
        pid = supervisor.start(["ffmpeg", "-i", "fuente.mp4"], scratch=out_dir)
        (out_dir / "frame_0001.jpg").write_bytes(b"parcial")
        en_ejecucion.set()
        assert pipe.supervisor.cancelado.wait(5)
        raise ProcessingError(f"ffmpeg {pid} terminado por la cancelacion")

    pipe.al_extraer = ffmpeg_en_curso
    case_id = pipe.crear_caso({"clip.mp4": VIDEO})
    imagen = pipe.worker("image")
    escucha = escuchar_cancelaciones(pipe.redis, imagen.subprocesos, imagen.stop_event)
    hilo = threading.Thread(target=lambda: imagen.poll_once(timeout=0), daemon=True)
    hilo.start()
    try:
        assert en_ejecucion.wait(5)

        assert pipe.client.post(f"/cases/{case_id}/cancel").status_code == 200
        hilo.join(10)
    finally:
        pipe.supervisor.cancelado.set()
        imagen.stop_event.set()
        escucha.join(5)

    assert not hilo.is_alive()
    assert pipe.supervisor.cancelados == [4000]
    assert not list(pipe.work_dir.rglob("*"))
    assert pipe.en_vuelo() == 0
    assert imagen.subprocesos._pids == {}
    assert pipe.caso(case_id)["status"] == "cancelled"


def test_fallo_transitorio_se_reintenta_con_espera_y_vuelve_a_la_cola_con_formato_subtask(pipe):
    pipe.modelos_de_texto.fallos = [TimeoutError("modelo ocupado")]
    case_id = pipe.crear_caso({"nota.txt": WHATSAPP})
    texto, reaper = pipe.worker("text"), pipe.reaper()

    assert pipe.drenar(texto) == 1

    sid = f"{case_id}:{sha256(WHATSAPP)}:text"
    assert pipe.caso(case_id)["status"] == "retrying"
    assert pipe.subtareas(case_id)[("text", "nota.txt")]["status"] == "pending"
    assert pipe.redis.zscore("retry:scheduled", sid) is not None
    assert pipe.en_vuelo() == 0
    assert pipe.colas()["queue:text"] == 0
    assert pipe.sesion.payloads == []

    reaper.run_once()
    assert pipe.colas()["queue:text"] == 0

    pipe.reloj.advance(timedelta(seconds=1))
    reaper.run_once()

    crudo = pipe.redis.lindex("queue:text", 0)
    reencolada = Subtask.from_dict(json.loads(crudo))
    assert (reencolada.id, reencolada.kind, reencolada.source_sha256) == (sid, ContentKind.TEXT, sha256(WHATSAPP))
    assert pipe.redis.zcard("retry:scheduled") == 0

    assert pipe.drenar(texto) == 1

    assert pipe.caso(case_id)["status"] == "completed"
    assert pipe.subtareas(case_id)[("text", "nota.txt")]["attempts"] == "2"
    assert len(pipe.sesion.payloads) == 1
    assert pipe.redis.llen(f"case:{case_id}:findings") == 4
    assert pipe.en_vuelo() == 0


def test_reintentos_agotados_cierran_el_caso_con_el_estado_correcto(pipe):
    pipe.modelos_de_texto.fallos = [TimeoutError("modelo ocupado")] * 3
    case_id = pipe.crear_caso({"nota.txt": WHATSAPP, "foto.jpg": FOTO})
    texto, reaper = pipe.worker("text"), pipe.reaper()
    pipe.drenar(pipe.worker("image"))

    for _ in range(3):
        assert pipe.drenar(texto) == 1
        pipe.reloj.advance(timedelta(seconds=40))
        reaper.run_once()

    subtarea = pipe.subtareas(case_id)[("text", "nota.txt")]
    assert subtarea["status"] == "failed"
    assert subtarea["attempts"] == "3"
    assert subtarea["error_type"] == "TimeoutError"
    assert pipe.caso(case_id)["status"] == "partially_completed"
    assert pipe.redis.zcard("retry:scheduled") == 0
    assert pipe.colas()["queue:text"] == 0
    assert pipe.en_vuelo() == 0
    assert {h.category for h in pipe.hallazgos(case_id)} == {"arma"}


def reclamar_y_morir(pipe, worker_id, kind="text"):
    """El worker toma y reclama la sub-tarea y desaparece sin reportar ni confirmar: queda en su inflight."""
    muerto = pipe.worker(kind, worker_id)
    subtask = muerto.queue.take(muerto.queue_name, worker_id, 0)
    assert subtask is not None
    assert muerto._claim_subtask(subtask.id)[0] == "claimed"
    pipe.redis.sadd("workers:registry", worker_id)
    return muerto, subtask


def test_worker_muerto_su_inflight_lo_recupera_el_reaper_y_otro_worker_cierra_el_caso(pipe):
    case_id = pipe.crear_caso({"chat.json": TELEGRAM})
    _, subtask = reclamar_y_morir(pipe, "w-muerto")
    assert pipe.redis.llen("inflight:w-muerto") == 1
    assert pipe.colas()["queue:text"] == 0

    resultado = pipe.reaper().run_once()

    assert resultado["requeued"] == 1
    assert pipe.redis.llen("inflight:w-muerto") == 0
    assert "w-muerto" not in pipe.redis.smembers("workers:registry")
    assert pipe.caso(case_id)["status"] == "retrying"
    assert Subtask.from_dict(json.loads(pipe.redis.lindex("queue:text", 0))).id == subtask.id

    assert pipe.drenar(pipe.worker("text", "w-vivo")) == 1

    assert pipe.caso(case_id)["status"] == "completed"
    assert pipe.subtareas(case_id)[("text", "chat.json")]["attempts"] == "2"
    assert pipe.redis.llen(f"case:{case_id}:findings") == 4
    assert pipe.en_vuelo() == 0


def test_subtarea_veneno_agota_los_intentos_y_falla_sin_bucle(pipe):
    case_id = pipe.crear_caso({"chat.json": TELEGRAM})

    for intento in range(1, 4):
        reclamar_y_morir(pipe, f"w-veneno-{intento}")
        pipe.reaper().run_once()

    subtarea = pipe.subtareas(case_id)[("text", "chat.json")]
    assert subtarea["status"] == "failed"
    assert subtarea["error_type"] == "WorkerLostError"
    assert subtarea["attempts"] == "3"
    assert "abandonada tras 3 intentos" in subtarea["error"]
    assert pipe.colas()["queue:text"] == 0
    assert pipe.en_vuelo() == 0
    assert pipe.caso(case_id)["status"] == "failed"
    assert pipe.drenar(pipe.worker("text", "w-sano")) == 0


def test_subtarea_con_los_intentos_ya_gastados_no_se_procesa_otra_vez(pipe):
    case_id = pipe.crear_caso({"chat.json": TELEGRAM})
    sid = f"{case_id}:{sha256(TELEGRAM)}:text"
    pipe.redis.hset(f"subtask:{sid}", "attempts", 3)

    assert pipe.drenar(pipe.worker("text")) == 1

    subtarea = pipe.subtareas(case_id)[("text", "chat.json")]
    assert (subtarea["status"], subtarea["error_type"]) == ("failed", "WorkerLostError")
    assert pipe.modelos_de_texto.llamadas == []


def test_admision_de_memoria_deja_en_cola_a_los_tres_tipos(pipe):
    case_id = pipe.crear_caso({"nota.txt": WHATSAPP, "foto.jpg": FOTO, "voz.mp3": VOZ})
    escaso = ResourceUsage("nodo", memory_current=800, memory_max=1000)
    sin_memoria = [pipe.worker(kind, uso=escaso) for kind in ("text", "image", "audio")]

    assert [worker.poll_once(timeout=0) for worker in sin_memoria] == [False, False, False]

    assert pipe.colas() == {"queue:text": 1, "queue:image": 1, "queue:audio": 1}
    assert pipe.en_vuelo() == 0
    assert pipe.caso(case_id)["status"] == "queued"
    assert pipe.modelos_de_texto.llamadas == [] and pipe.detector.rutas == []

    holgado = ResourceUsage("nodo", memory_current=100, memory_max=1000)
    con_memoria = [pipe.worker(kind, uso=holgado) for kind in ("text", "image", "audio")]

    assert pipe.drenar(*con_memoria) == 3
    assert pipe.caso(case_id)["status"] == "completed"


def test_hallazgos_sin_duplicados_tras_reintento_y_doble_entrega(pipe):
    case_id = pipe.crear_caso({"chat.json": TELEGRAM})
    muerto, subtask = reclamar_y_morir(pipe, "w-muerto")
    muerto.analyze.execute(subtask, "chat.json")
    escritos = pipe.redis.llen(f"case:{case_id}:findings")
    assert escritos == 4
    assert [tipo for tipo, _ in pipe.alertas()] == ["incidencia_alta"]

    pipe.reaper().run_once()
    vivo = pipe.worker("text", "w-vivo")
    assert pipe.drenar(vivo) == 1

    assert pipe.caso(case_id)["status"] == "completed"
    assert pipe.redis.llen(f"case:{case_id}:findings") == escritos
    assert [tipo for tipo, _ in pipe.alertas()].count("incidencia_alta") == 1

    vivo.queue.enqueue("queue:text", subtask)
    assert pipe.drenar(vivo) == 1

    assert pipe.redis.llen(f"case:{case_id}:findings") == escritos
    assert [tipo for tipo, _ in pipe.alertas()].count("incidencia_alta") == 1
    assert [tipo for tipo, _ in pipe.alertas()].count("caso_finalizado") == 1
    assert len(pipe.sesion.payloads) == 1
    assert pipe.en_vuelo() == 0


def test_reporte_consolidado_resuelve_evidencias_con_almacen_cifrado(pipe):
    contenidos = {"nota.txt": WHATSAPP, "chat.json": TELEGRAM, "foto.jpg": FOTO, "voz.mp3": VOZ, "clip.mp4": VIDEO}
    case_id = pipe.crear_caso(contenidos)
    pipe.drenar(*tres_workers(pipe))
    assert all(pipe.almacen._inner.objetos[sha256(c)] != c for c in contenidos.values())

    reporte = pipe.reporte(case_id)

    assert reporte["status"] == "completed"
    assert reporte["hallazgos"] and reporte["categorias"] and reporte["linea_temporal"] and reporte["incidencias"]
    fuentes = {f["evidencia"][0]["fuente"]["file_path"] for f in reporte["hallazgos"] if f["evidencia"]}
    assert fuentes == set(contenidos)
    for hallazgo in reporte["hallazgos"]:
        for evidencia in hallazgo["evidencia"]:
            sha = evidencia["fuente"]["sha256"]
            assert pipe.almacen.exists(sha)
            assert pipe.almacen.open(sha).read() == contenidos[evidencia["fuente"]["file_path"]]
    assert {"amenaza", "arma"} <= {i["categoria"] for i in reporte["incidencias"] if i["categoria"]}


def test_incidencia_alta_publica_alerta_antes_del_cierre(pipe):
    case_id = pipe.crear_caso({"chat.json": TELEGRAM, "foto.jpg": FOTO})

    pipe.drenar(pipe.worker("text"))
    assert pipe.caso(case_id)["status"] == "processing"
    assert pipe.alertas() == [("incidencia_alta", case_id)]

    pipe.drenar(pipe.worker("image"))

    assert pipe.caso(case_id)["status"] == "completed"
    assert pipe.alertas() == [("incidencia_alta", case_id), ("incidencia_alta", case_id), ("caso_finalizado", case_id)]
    detalles = [json.loads(campos["detail"]) for _, campos in pipe.redis.xrange("alerts") if campos["kind"] == "incidencia_alta"]
    assert {d["categoria"] for d in detalles} == {"amenaza", "arma"}


def test_cierre_del_caso_publica_la_alerta_de_cierre(pipe):
    case_id = pipe.crear_caso({"nota.txt": WHATSAPP})

    pipe.drenar(pipe.worker("text"))

    alertas = pipe.redis.xrange("alerts")
    assert [(campos["kind"], campos["case_id"]) for _, campos in alertas] == [("caso_finalizado", case_id)]
    assert json.loads(alertas[0][1]["detail"]) == {"estado": "completed"}
