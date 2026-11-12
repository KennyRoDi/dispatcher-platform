import fakeredis
import pytest
from fastapi.testclient import TestClient

import src.coordinator.main as main
from src.adapters.redis_backpressure import transaccion_acotada
from src.coordinator import conexion
from src.domain.backpressure import CaseTooLarge, QueueLimit
from src.domain.subtask import QueueFull

COLA = "queue:transcode_video"
OTRA = "queue:extract_audio"


@pytest.mark.parametrize("env, esperado", [
    ({}, (1000, 5)),
    ({"QUEUE_MAX_DEPTH": "50", "QUEUE_RETRY_AFTER": "2"}, (50, 2)),
    ({"QUEUE_MAX_DEPTH": " 0 "}, (0, 5)),
])
def test_limite_se_lee_del_entorno(env, esperado):
    limite = QueueLimit.from_env(env)
    assert (limite.max_depth, limite.retry_after) == esperado


@pytest.mark.parametrize("env", [
    {"QUEUE_MAX_DEPTH": "-1"}, {"QUEUE_MAX_DEPTH": "mil"},
    {"QUEUE_RETRY_AFTER": "0"}, {"QUEUE_RETRY_AFTER": "1.5"},
])
def test_configuracion_invalida_se_rechaza(env):
    with pytest.raises(ValueError):
        QueueLimit.from_env(env)


def test_limite_desactivable():
    limite = QueueLimit(max_depth=0, retry_after=5)
    assert limite.desactivado
    assert limite.admite(10**9, 10**6)


@pytest.mark.parametrize("profundidad, entrantes, admite", [(7, 3, True), (8, 3, False), (10, 0, True), (11, 0, False)])
def test_admite_hasta_el_borde_exacto(profundidad, entrantes, admite):
    assert QueueLimit(max_depth=10, retry_after=5).admite(profundidad, entrantes) is admite


@pytest.fixture
def fake():
    return fakeredis.FakeRedis(decode_responses=True)


def llenar(r, cola, n):
    if n:
        r.rpush(cola, *[f"x{i}" for i in range(n)])


def test_transaccion_con_espacio_ejecuta_los_comandos(fake):
    llenar(fake, COLA, 2)
    transaccion_acotada(fake, {COLA: 3}, QueueLimit(5, 5), lambda pipe: pipe.rpush(COLA, "a", "b", "c"))
    assert fake.llen(COLA) == 5


def test_transaccion_sin_espacio_rechaza_y_no_escribe(fake):
    llenar(fake, COLA, 4)
    with pytest.raises(QueueFull):
        transaccion_acotada(fake, {COLA: 2}, QueueLimit(5, 5), lambda pipe: pipe.hset("caso", mapping={"a": 1}))
    assert fake.llen(COLA) == 4
    assert not fake.exists("caso")


def test_basta_una_cola_llena_para_rechazar_todo(fake):
    llenar(fake, OTRA, 5)
    with pytest.raises(QueueFull):
        transaccion_acotada(fake, {COLA: 1, OTRA: 1}, QueueLimit(5, 5), lambda pipe: pipe.rpush(COLA, "a"))
    assert fake.llen(COLA) == 0


class RedisQueNoDebeEvaluar:
    """Con el límite desactivado se usa el pipeline de siempre, sin script ni vigilancia."""

    def __init__(self):
        self.ejecutados = 0

    def pipeline(self, transaction=True):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self):
        self.ejecutados += 1

    def eval(self, *_):
        raise AssertionError("con el límite desactivado no se evalúa el script")


def test_sin_limite_usa_el_pipeline_de_siempre():
    r = RedisQueNoDebeEvaluar()
    transaccion_acotada(r, {COLA: 1}, QueueLimit(0, 5), lambda pipe: None)
    assert r.ejecutados == 1


def test_caso_que_no_cabria_ni_con_la_cola_vacia_es_otro_error(fake):
    with pytest.raises(CaseTooLarge):
        transaccion_acotada(fake, {COLA: 6}, QueueLimit(5, 5), lambda pipe: pipe.rpush(COLA, "x"))
    assert fake.llen(COLA) == 0


def test_hset_con_valores_no_texto_se_escribe_igual(fake):
    transaccion_acotada(fake, {COLA: 1}, QueueLimit(5, 5),
                        lambda pipe: (pipe.hset("caso", mapping={"total": 3, "estado": "queued"}), pipe.rpush(COLA, "a")))
    assert fake.hgetall("caso") == {"total": "3", "estado": "queued"}


@pytest.fixture
def api(fake, monkeypatch, sin_autorizacion):
    monkeypatch.setattr(conexion, "redis_client", fake)
    monkeypatch.setenv("QUEUE_MAX_DEPTH", "3")
    monkeypatch.setenv("QUEUE_RETRY_AFTER", "7")
    return TestClient(main.app)


def crear(api, *rutas):
    return api.post("/cases", json={"subtasks": [{"task_type": "auto", "file_path": r} for r in rutas or ("videos/a.mp4",)]})


def test_cola_llena_rechaza_productor(api, fake):
    llenar(fake, COLA, 3)
    antes = sorted(fake.keys())
    respuesta = crear(api)
    assert respuesta.status_code == 503
    assert respuesta.headers["Retry-After"] == "7"
    assert sorted(fake.keys()) == antes
    assert fake.llen(COLA) == 3


def test_con_espacio_el_caso_se_crea_como_hoy(api, fake):
    llenar(fake, COLA, 2)
    respuesta = crear(api)
    assert respuesta.status_code == 201
    assert fake.llen(COLA) == 3
    assert fake.sismember("cases:registry", respuesta.json()["case_id"])


def test_caso_que_no_cabe_entero_se_rechaza(api, fake):
    llenar(fake, COLA, 2)
    respuesta = crear(api, "videos/a.mp4", "videos/b.mp4")
    assert respuesta.status_code == 503
    assert fake.llen(COLA) == 2
    assert fake.scard("cases:registry") == 0


def test_caso_en_dos_colas_se_rechaza_si_una_esta_llena(api, fake):
    llenar(fake, OTRA, 3)
    respuesta = api.post("/cases", json={"subtasks": [
        {"task_type": "transcode_video", "file_path": "videos/a.mp4"},
        {"task_type": "extract_audio", "file_path": "videos/a.mp4"},
    ]})
    assert respuesta.status_code == 503
    assert fake.llen(COLA) == 0


def test_sin_limite_admite_aunque_la_cola_este_muy_llena(api, fake, monkeypatch):
    monkeypatch.setenv("QUEUE_MAX_DEPTH", "0")
    llenar(fake, COLA, 500)
    assert crear(api).status_code == 201
    assert fake.llen(COLA) == 501


def test_caso_mas_grande_que_el_limite_responde_422(api, fake):
    respuesta = crear(api, "videos/a.mp4", "videos/b.mp4", "videos/c.mp4", "videos/d.mp4")
    assert respuesta.status_code == 422
    assert fake.llen(COLA) == 0


@pytest.mark.parametrize("env", [{"QUEUE_MAX_DEPTH": "abc"}, {"QUEUE_RETRY_AFTER": "0"}])
def test_configuracion_invalida_falla_al_arrancar(env):
    with pytest.raises(ValueError):
        main.crear_app({**env, "AUTH_ENABLED": "false"})
