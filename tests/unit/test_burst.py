import csv
from argparse import Namespace
from copy import deepcopy

import pytest

from scenarios import burst

HOSTS = ("nodo-a", "nodo-b", "nodo-c")


def caso(i, estado="completed", duracion=12.5, prioridad="normal"):
    return {"name": f"caso{i:02d}", "kind": "homogeneous", "priority": prioridad, "case_id": f"id{i}",
            "status": estado, "subtasks": 4, "duration_s": duracion, "error": None}


def trabajador(host, cpu=40.0, mem=30.0, activas=2):
    return {"host": host, "cpu_percent": cpu, "mem_percent": mem, "active_subtasks": activas,
            "completed_count": 0.0, "failed_count": 0.0}


def muestra(t, hosts=HOSTS, cpu=40.0):
    return {"t": t, "cases": {"processing": 20}, "active_total": 2 * len(hosts), "stats": None,
            "workers": {f"w-{h}": trabajador(h, cpu=cpu) for h in hosts}}


def resultado(casos=20, hosts=HOSTS, con_series=True):
    return {
        "timed_out": False,
        "config": {"casos": casos, "concurrencia": casos},
        "metrics": {
            "cases": casos,
            "case_status_counts": {"completed": casos},
            "throughput_subtasks_per_min": 96.0,
            "subtasks_per_host": {h: 10 for h in hosts},
            "peak_cpu_by_host": {h: 55.5 for h in hosts},
            "peak_active_by_host": {h: 3 for h in hosts},
            "per_case": [caso(i) for i in range(casos)],
        },
        "series": [muestra(0.0, hosts), muestra(5.0, hosts)] if con_series else [],
    }


def problemas(res, **kw):
    veredicto = burst.evaluar(res, **kw)
    assert veredicto["cumple"] is False
    return " | ".join(veredicto["problemas"]).lower()


def test_una_rafaga_completa_cumple():
    assert burst.evaluar(resultado()) == {"cumple": True, "problemas": []}


def test_menos_de_20_casos_no_cumple():
    res = resultado(casos=19)
    assert "20" in problemas(res)


def test_el_minimo_de_casos_se_puede_cambiar():
    assert burst.evaluar(resultado(casos=5), minimo_casos=5)["cumple"] is True


@pytest.mark.parametrize("estado", ["processing", "pending", "submit_error", "unknown", "submitted"])
def test_un_caso_sin_estado_final_no_cumple(estado):
    res = resultado()
    res["metrics"]["per_case"][3]["status"] = estado
    res["metrics"]["case_status_counts"] = {"completed": 19, estado: 1}
    assert "estado final" in problemas(res)


@pytest.mark.parametrize("estado", ["completed", "partially_completed", "failed", "cancelled"])
def test_los_estados_finales_de_run_load_cuentan_como_finales(estado):
    res = resultado()
    res["metrics"]["per_case"][0]["status"] = estado
    res["metrics"]["case_status_counts"] = {"completed": 19, estado: 1} if estado != "completed" else {"completed": 20}
    assert burst.evaluar(res)["cumple"] is True


def test_un_caso_failed_cumple_pero_se_reporta_aparte():
    res = resultado()
    res["metrics"]["per_case"][0]["status"] = "failed"
    res["metrics"]["case_status_counts"] = {"completed": 19, "failed": 1}
    veredicto = burst.evaluar(res)
    assert veredicto["cumple"] is True
    assert veredicto["problemas"] == []


def test_timed_out_no_cumple():
    res = resultado()
    res["timed_out"] = True
    assert "timed_out" in problemas(res)


def test_un_envio_fallido_no_cumple():
    res = resultado()
    res["metrics"]["per_case"][0].update(status="submit_error", case_id=None, error="HTTP 429")
    assert "submit_error" in problemas(res)


def test_solo_dos_hosts_no_cumple():
    assert "nodos" in problemas(resultado(hosts=HOSTS[:2]))


def test_se_puede_exigir_otro_numero_de_nodos():
    assert burst.evaluar(resultado(hosts=HOSTS[:2]), minimo_nodos=2)["cumple"] is True


def test_tres_hosts_solo_en_las_muestras_cumplen():
    res = resultado()
    res["metrics"]["subtasks_per_host"] = {}
    assert burst.evaluar(res)["cumple"] is True


def test_los_hosts_de_metricas_y_muestras_se_unen():
    res = resultado(hosts=HOSTS[:2])
    res["series"].append(muestra(10.0, hosts=HOSTS[2:]))
    assert burst.evaluar(res)["cumple"] is True


def test_el_mismo_host_con_varios_workers_cuenta_una_vez():
    res = resultado(hosts=HOSTS[:2])
    res["series"][0]["workers"]["w-extra"] = trabajador("nodo-a")
    assert "nodos" in problemas(res)


def test_sin_throughput_no_cumple():
    res = resultado()
    del res["metrics"]["throughput_subtasks_per_min"]
    assert "throughput" in problemas(res)


def test_throughput_nulo_no_cumple():
    res = resultado()
    res["metrics"]["throughput_subtasks_per_min"] = None
    assert "throughput" in problemas(res)


def test_sin_duracion_en_ningun_caso_no_cumple():
    res = resultado()
    for c in res["metrics"]["per_case"]:
        c["duration_s"] = None
    assert "latencia" in problemas(res)


@pytest.mark.parametrize("clave", ["peak_cpu_by_host", "peak_active_by_host"])
def test_sin_recursos_por_nodo_no_cumple(clave):
    res = resultado()
    res["metrics"][clave] = {}
    assert "recursos" in problemas(res)


def test_varios_incumplimientos_se_reportan_todos():
    res = resultado(casos=19, hosts=HOSTS[:2])
    res["timed_out"] = True
    texto = problemas(res)
    assert "20" in texto and "nodos" in texto and "timed_out" in texto


def test_evaluar_no_modifica_el_resultado():
    res = resultado(casos=19)
    copia = deepcopy(res)
    burst.evaluar(res)
    assert res == copia


def test_filas_latencia_tiene_una_fila_por_caso_con_las_columnas_del_spec():
    filas = burst.filas_latencia(resultado(casos=3))
    assert len(filas) == 3
    assert filas[0] == {"caso": "caso00", "tipo": "homogeneous", "prioridad": "normal", "estado": "completed",
                        "subtareas": 4, "duracion_s": 12.5}


def test_filas_latencia_conserva_el_orden_y_la_prioridad():
    res = resultado(casos=3)
    res["metrics"]["per_case"][1]["priority"] = "high"
    filas = burst.filas_latencia(res)
    assert [f["caso"] for f in filas] == ["caso00", "caso01", "caso02"]
    assert [f["prioridad"] for f in filas] == ["normal", "high", "normal"]


def test_filas_latencia_incluye_los_casos_sin_duracion():
    res = resultado(casos=2)
    res["metrics"]["per_case"][1].update(duration_s=None, status="processing")
    filas = burst.filas_latencia(res)
    assert len(filas) == 2
    assert filas[1]["duracion_s"] is None and filas[1]["estado"] == "processing"


def test_filas_recursos_tiene_una_fila_por_muestra_y_por_worker():
    res = resultado(hosts=HOSTS)
    filas = burst.filas_recursos(res)
    assert len(filas) == len(res["series"]) * len(HOSTS)
    primera = filas[0]
    assert set(primera) == {"instante", "host", "cpu_percent", "mem_percent", "subtareas_activas"}
    assert primera["instante"] == 0.0 and primera["host"] in HOSTS
    assert (primera["cpu_percent"], primera["mem_percent"], primera["subtareas_activas"]) == (40.0, 30.0, 2)


def test_filas_recursos_toma_los_valores_de_cada_muestra():
    res = resultado(hosts=HOSTS[:1])
    res["series"][1] = muestra(5.0, HOSTS[:1], cpu=88.0)
    filas = burst.filas_recursos(res)
    assert [(f["instante"], f["cpu_percent"]) for f in filas] == [(0.0, 40.0), (5.0, 88.0)]


def test_filas_recursos_omite_las_muestras_sin_workers():
    res = resultado(hosts=HOSTS[:1])
    res["series"].append({"t": 10.0, "cases": {}, "active_total": 0, "workers": {}, "stats": None})
    assert len(burst.filas_recursos(res)) == 2


def test_filas_recursos_sin_series_es_vacia():
    assert burst.filas_recursos(resultado(con_series=False)) == []


def test_escribir_csv_guarda_encabezado_y_filas(tmp_path):
    ruta = tmp_path / "latencia_por_caso.csv"
    filas = burst.filas_latencia(resultado(casos=3))
    burst.escribir_csv(filas, ruta)
    with ruta.open(encoding="utf-8", newline="") as archivo:
        leidas = list(csv.DictReader(archivo))
    assert list(leidas[0]) == ["caso", "tipo", "prioridad", "estado", "subtareas", "duracion_s"]
    assert [f["caso"] for f in leidas] == ["caso00", "caso01", "caso02"]
    assert leidas[0]["duracion_s"] == "12.5"


def test_escribir_csv_deja_vacia_la_duracion_ausente(tmp_path):
    res = resultado(casos=1)
    res["metrics"]["per_case"][0]["duration_s"] = None
    ruta = tmp_path / "latencia_por_caso.csv"
    burst.escribir_csv(burst.filas_latencia(res), ruta)
    with ruta.open(encoding="utf-8", newline="") as archivo:
        assert list(csv.DictReader(archivo))[0]["duracion_s"] == ""


def test_escribir_csv_de_recursos_tiene_una_fila_por_muestra_y_worker(tmp_path):
    ruta = tmp_path / "recursos_por_nodo.csv"
    burst.escribir_csv(burst.filas_recursos(resultado()), ruta)
    with ruta.open(encoding="utf-8", newline="") as archivo:
        leidas = list(csv.DictReader(archivo))
    assert len(leidas) == 6
    assert set(leidas[0]) == {"instante", "host", "cpu_percent", "mem_percent", "subtareas_activas"}


class EjecutorFalso:
    def __init__(self, devuelve=None):
        self.llamadas = []
        self.devuelve = devuelve if devuelve is not None else resultado()

    def __call__(self, args):
        self.llamadas.append(args)
        return self.devuelve


def argumentos(**kw):
    base = dict(dataset="dataset", limit=20, concurrency=20, timeout=1800.0, poll=5.0, out="salida")
    base.update(kw)
    return Namespace(**base)


def test_ejecutar_rafaga_devuelve_el_json_del_ejecutor_y_lo_llama_una_vez():
    ejecutor = EjecutorFalso()
    assert burst.ejecutar_rafaga(argumentos(), ejecutor) is ejecutor.devuelve
    assert len(ejecutor.llamadas) == 1


def test_ejecutar_rafaga_pasa_limite_y_concurrencia_al_ejecutor():
    ejecutor = EjecutorFalso()
    burst.ejecutar_rafaga(argumentos(limit=40, concurrency=40, timeout=900.0), ejecutor)
    enviados = ejecutor.llamadas[0]
    assert (enviados.limit, enviados.concurrency, enviados.timeout) == (40, 40, 900.0)


@pytest.mark.parametrize("limite", [19, 1, 0, None])
def test_ejecutar_rafaga_rechaza_menos_de_20_casos_sin_ejecutar(limite):
    ejecutor = EjecutorFalso()
    with pytest.raises(ValueError):
        burst.ejecutar_rafaga(argumentos(limit=limite), ejecutor)
    assert ejecutor.llamadas == []


@pytest.mark.parametrize("concurrencia", [19, 1, 0])
def test_ejecutar_rafaga_rechaza_concurrencia_menor_que_los_casos(concurrencia):
    ejecutor = EjecutorFalso()
    with pytest.raises(ValueError):
        burst.ejecutar_rafaga(argumentos(limit=20, concurrency=concurrencia), ejecutor)
    assert ejecutor.llamadas == []
