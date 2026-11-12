import csv
import json
from argparse import Namespace
from copy import deepcopy

import pytest

from scenarios import burst

HOSTS = ("nodo-a", "nodo-b", "nodo-c")


def caso(i, estado="completed", duracion=12.5):
    return {"name": f"caso{i:02d}", "kind": "homogeneous", "priority": "normal", "case_id": f"id{i}",
            "status": estado, "subtasks": 4, "duration_s": duracion, "error": None}


def trabajador(host):
    return {"host": host, "cpu_percent": 40.0, "mem_percent": 30.0, "active_subtasks": 2}


def resultado(casos=20, hosts=HOSTS):
    return {
        "timed_out": False,
        "metrics": {
            "cases": casos, "throughput_subtasks_per_min": 96.0,
            "subtasks_per_host": {h: 10 for h in hosts},
            "peak_cpu_by_host": {h: 55.5 for h in hosts},
            "peak_active_by_host": {h: 3 for h in hosts},
            "per_case": [caso(i) for i in range(casos)],
        },
        "series": [{"t": 0.0, "workers": {f"w-{h}": trabajador(h) for h in hosts}}],
    }


def test_limites_de_casos_19_y_20_y_de_hosts_2_y_3():
    assert burst.evaluar(resultado(casos=20))["cumple"] is True
    assert burst.evaluar(resultado(casos=19))["cumple"] is False
    assert burst.evaluar(resultado(hosts=HOSTS[:2]))["cumple"] is False
    assert burst.evaluar(resultado(hosts=HOSTS))["cumple"] is True


def test_series_vacias_y_sin_subtasks_per_host_no_cumplen():
    res = resultado()
    res["series"] = []
    res["metrics"]["subtasks_per_host"] = {}
    assert burst.evaluar(res)["cumple"] is False


def test_per_case_vacio_no_cumple():
    res = resultado()
    res["metrics"]["per_case"] = []
    assert burst.evaluar(res)["cumple"] is False


def test_duracion_none_en_algunos_casos_se_tolera_y_en_todos_no():
    res = resultado()
    res["metrics"]["per_case"][0]["duration_s"] = None
    assert burst.evaluar(res)["cumple"] is True
    for c in res["metrics"]["per_case"]:
        c["duration_s"] = None
    assert burst.evaluar(res)["cumple"] is False


def test_csv_con_valores_none_y_caracteres_especiales(tmp_path):
    filas = [{"caso": 'a,"b"\nc', "tipo": "ñ–é", "duracion_s": None}]
    ruta = tmp_path / "x.csv"
    burst.escribir_csv(filas, ruta)
    with ruta.open(encoding="utf-8", newline="") as f:
        leidas = list(csv.DictReader(f))
    assert leidas == [{"caso": 'a,"b"\nc', "tipo": "ñ–é", "duracion_s": ""}]


def test_csv_sobrescribe_un_archivo_previo(tmp_path):
    ruta = tmp_path / "x.csv"
    burst.escribir_csv([{"a": 1}, {"a": 2}], ruta)
    burst.escribir_csv([{"a": 9}], ruta)
    assert ruta.read_text(encoding="utf-8").splitlines() == ["a", "9"]


def test_filas_no_modifican_el_resultado():
    res = resultado()
    copia = deepcopy(res)
    burst.filas_latencia(res)
    burst.filas_recursos(res)
    assert res == copia


def test_ejecutar_rafaga_con_concurrencia_mayor_que_limite_pasa():
    args = Namespace(limit=20, concurrency=50)
    assert burst.ejecutar_rafaga(args, lambda a: "ok") == "ok"


def test_main_sin_limit_crea_la_salida_y_devuelve_1_si_no_cumple(tmp_path, monkeypatch, capsys):
    res = resultado(casos=20, hosts=HOSTS[:2])
    monkeypatch.setattr(burst, "_ejecutar_run_load", lambda args: res)
    salida = tmp_path / "nueva"
    salida.mkdir()
    assert burst.main(["--out", str(salida)]) == 1
    assert json.loads(capsys.readouterr().out)["cumple"] is False
    assert (salida / "latencia_por_caso.csv").exists()
    assert (salida / "recursos_por_nodo.csv").exists()


@pytest.mark.xfail(strict=True, raises=ValueError,
                   reason="main deja escapar ValueError con traza si --limit < 20 o --concurrency < --limit")
@pytest.mark.parametrize("argv", [["--limit", "5"], ["--limit", "40"]])
def test_main_con_limit_invalido_da_error_claro_sin_traza(argv, tmp_path, monkeypatch):
    monkeypatch.setattr(burst, "_ejecutar_run_load", lambda args: pytest.fail("no debe ejecutar"))
    try:
        codigo = burst.main(argv + ["--out", str(tmp_path)])
    except SystemExit as salida:
        codigo = salida.code
    assert codigo not in (0, None)


@pytest.mark.xfail(strict=True, reason="--out que es un archivo falla recien al terminar la corrida (run_load.py:402), "
                                       "tras perder la tanda; no se valida antes de ejecutar")
def test_main_con_out_invalido_falla_antes_de_ejecutar(tmp_path, monkeypatch):
    archivo = tmp_path / "es_archivo"
    archivo.write_text("x")
    llamadas = []
    monkeypatch.setattr(burst, "_ejecutar_run_load", lambda args: llamadas.append(args) or resultado())
    with pytest.raises((SystemExit, OSError, ValueError)):
        burst.main(["--out", str(archivo / "sub")])
    assert llamadas == []


@pytest.mark.xfail(strict=True, raises=KeyError, reason="evaluar({}) lanza KeyError en vez de reportar problemas")
def test_evaluar_resultado_sin_claves_reporta_problemas():
    veredicto = burst.evaluar({})
    assert veredicto["cumple"] is False


@pytest.mark.xfail(strict=True, reason="evaluar usa metrics['cases'] y no len(per_case): 20 declarados con 5 filas cumple")
def test_evaluar_detecta_per_case_menor_que_cases():
    res = resultado()
    res["metrics"]["per_case"] = res["metrics"]["per_case"][:5]
    assert burst.evaluar(res)["cumple"] is False


@pytest.mark.xfail(strict=True, reason="escribir_csv con filas vacias deja un archivo de 0 bytes sin encabezado")
def test_csv_de_filas_vacias_conserva_el_encabezado(tmp_path):
    res = resultado()
    res["series"] = []
    ruta = tmp_path / "recursos.csv"
    burst.escribir_csv(burst.filas_recursos(res), ruta)
    assert ruta.read_text(encoding="utf-8").strip() != ""


@pytest.mark.xfail(strict=True, reason="un caso failed cumple pero el veredicto no lo reporta aparte (SPEC pregunta 3)")
def test_el_veredicto_reporta_aparte_los_casos_failed():
    res = resultado()
    res["metrics"]["per_case"][0]["status"] = "failed"
    veredicto = burst.evaluar(res)
    assert veredicto["cumple"] is True
    assert "failed" in json.dumps(veredicto)
