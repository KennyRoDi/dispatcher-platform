import json

import fakeredis
import pytest
import responses

from scenarios import burst
from scripts import run_load as rl
from tests.test_run_load import FakeClock, args_for, make_dataset, mock_api, settings

pytestmark = pytest.mark.integration

CASOS = 20
HOSTS = ("nodo-a", "nodo-b", "nodo-c")


def redis_con_tres_nodos():
    cliente = fakeredis.FakeRedis(decode_responses=True)
    for i, host in enumerate(HOSTS):
        cliente.sadd("workers:registry", f"w{i}")
        cliente.hset(f"worker:w{i}", mapping={"host": host, "cpu_percent": str(30 + 20 * i),
                                              "mem_percent": "25", "active_subtasks": str(i + 1)})
    return cliente


def test_veinte_casos_concurrentes_llegan_a_estado_final_con_tres_nodos(tmp_path):
    dataset = make_dataset(tmp_path, n_cases=CASOS)
    reloj = FakeClock()
    cliente = redis_con_tres_nodos()

    def ejecutor(args):
        codigo, _ = rl.run_load(args, settings(), redis_client=cliente, sleep=reloj.sleep, clock=reloj,
                                stamp="rafaga")
        assert codigo == 0
        return json.loads((args.out / "carga_rafaga.json").read_text())

    args = args_for(dataset, limit=CASOS, concurrency=CASOS)
    with responses.RequestsMock() as rsps:
        contadores = mock_api(rsps)
        resultado = burst.ejecutar_rafaga(args, ejecutor)

    assert len(contadores) == CASOS
    assert resultado["metrics"]["cases"] == CASOS
    assert resultado["metrics"]["case_status_counts"] == {"partially_completed": CASOS}
    assert burst.evaluar(resultado) == {"cumple": True, "problemas": []}
    assert len(burst.filas_latencia(resultado)) == CASOS
    assert {f["host"] for f in burst.filas_recursos(resultado)} == set(HOSTS)
