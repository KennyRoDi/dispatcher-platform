import pytest

from tests.acceptance.tres_nodos import problemas_de_reparto, problemas_de_workers, problemas_tres_nodos


def _worker(hostname, ip, alive=True, worker_id=None) -> dict:
    return {"worker_id": worker_id or f"worker-{hostname}", "hostname": hostname, "ip": ip, "alive": alive}


def _tres_workers() -> list[dict]:
    return [
        _worker("nodo-b", "100.64.0.2"),
        _worker("nodo-c", "100.64.0.3"),
        _worker("nodo-d", "100.64.0.4"),
    ]


def _subtareas(*hosts, status="completed") -> list[dict]:
    return [{"host": host, "status": status} for host in hosts]


def _run_load(*subtareas, timed_out=False) -> dict:
    return {
        "timed_out": timed_out,
        "reports": {"caso-1": {"subtasks_by_operation": {"transcode_video": list(subtareas)}}},
    }


def _texto(problemas: list[str]) -> str:
    return " | ".join(problemas)


def test_tres_nodos_distintos_con_reparto_no_tiene_problemas():
    run_load = _run_load(*_subtareas("nodo-b", "nodo-c", "nodo-d"))
    assert problemas_tres_nodos(_tres_workers(), run_load) == []


def test_varios_workers_en_un_mismo_nodo_son_validos():
    workers = _tres_workers() + [_worker("nodo-b", "100.64.0.2", worker_id="worker-nodo-b-texto")]
    assert problemas_de_workers(workers) == []


def test_dos_activos_no_bastan_aunque_haya_un_tercero_caido():
    workers = [
        _worker("nodo-b", "100.64.0.2"),
        _worker("nodo-c", "100.64.0.3"),
        _worker("nodo-d", "100.64.0.4", alive=False),
    ]
    assert "nodos activos distintos: 2" in _texto(problemas_de_workers(workers))


def test_worker_caido_con_ip_ajena_no_se_evalua():
    workers = _tres_workers() + [_worker("viejo", "172.18.0.2", alive=False)]
    assert problemas_de_workers(workers) == []


def test_tres_replicas_en_un_mismo_nombre_no_son_tres_nodos():
    workers = [
        _worker("nodo-b", "100.64.0.2", worker_id="w1"),
        _worker("nodo-b", "100.64.0.3", worker_id="w2"),
        _worker("nodo-b", "100.64.0.4", worker_id="w3"),
    ]
    assert "hostname 'nodo-b' repetido" in _texto(problemas_de_workers(workers))


def test_tres_nombres_con_la_misma_ip_no_son_tres_nodos():
    workers = [
        _worker("nodo-b", "100.64.0.2"),
        _worker("nodo-c", "100.64.0.2"),
        _worker("nodo-d", "100.64.0.2"),
    ]
    assert "ip '100.64.0.2' repetida" in _texto(problemas_de_workers(workers))


def test_cruce_de_hostname_e_ip_se_rechaza_aunque_sumen_tres_de_cada_uno():
    workers = _tres_workers() + [_worker("nodo-b", "100.64.0.3", worker_id="w-cruzado")]
    texto = _texto(problemas_de_workers(workers))
    assert "hostname 'nodo-b' repetido" in texto
    assert "ip '100.64.0.3' repetida" in texto


@pytest.mark.parametrize("ip", [
    "172.18.0.2",
    "192.168.1.10",
    "100.63.255.255",
    "100.128.0.0",
    "fd7a:115c:a1e0::1",
    "unknown",
    "no-es-ip",
    "",
    None,
])
def test_ip_fuera_de_tailscale_se_rechaza(ip):
    workers = _tres_workers() + [_worker("nodo-e", ip)]
    assert f"ip {ip!r} fuera de" in _texto(problemas_de_workers(workers))


@pytest.mark.parametrize("ip", ["100.64.0.0", "100.127.255.255"])
def test_limites_del_rango_tailscale_se_aceptan(ip):
    workers = _tres_workers() + [_worker("nodo-e", ip)]
    assert problemas_de_workers(workers) == []


@pytest.mark.parametrize("hostname", ["unknown", "", None])
def test_hostname_no_valido_se_rechaza(hostname):
    workers = _tres_workers() + [_worker(hostname, "100.64.0.5", worker_id="w-sin-nombre")]
    assert f"hostname no valido {hostname!r}" in _texto(problemas_de_workers(workers))


def test_worker_sin_campos_de_identidad_se_rechaza_sin_excepcion():
    workers = _tres_workers() + [{"worker_id": "w-vacio", "alive": True}]
    texto = _texto(problemas_de_workers(workers))
    assert "w-vacio: hostname no valido None" in texto
    assert "w-vacio: ip None fuera de" in texto


def test_sin_workers_se_rechaza():
    assert "nodos activos distintos: 0" in _texto(problemas_de_workers([]))


def test_reparto_en_dos_hosts_no_basta():
    problemas = problemas_de_reparto(_tres_workers(), _run_load(*_subtareas("nodo-b", "nodo-c")))
    assert "hosts con sub-tareas completadas: 2" in _texto(problemas)


def test_reparto_se_suma_entre_casos_y_operaciones():
    run_load = {
        "timed_out": False,
        "reports": {
            "caso-1": {"subtasks_by_operation": {
                "transcode_video": _subtareas("nodo-b"),
                "extract_audio": _subtareas("nodo-c"),
            }},
            "caso-2": {"subtasks_by_operation": {"extract_metadata": _subtareas("nodo-d")}},
        },
    }
    assert problemas_de_reparto(_tres_workers(), run_load) == []


def test_nodo_solo_con_fallidas_no_cuenta_para_el_minimo():
    run_load = _run_load(*_subtareas("nodo-b", "nodo-c"), *_subtareas("nodo-d", status="failed"))
    assert "hosts con sub-tareas completadas: 2" in _texto(problemas_de_reparto(_tres_workers(), run_load))


def test_nodo_con_completadas_y_fallidas_cuenta():
    run_load = _run_load(*_subtareas("nodo-b", "nodo-c", "nodo-d"), *_subtareas("nodo-d", status="failed"))
    assert problemas_de_reparto(_tres_workers(), run_load) == []


@pytest.mark.parametrize("status", ["pending", "processing", "cancelled", None])
def test_estado_distinto_de_completada_no_cuenta(status):
    run_load = _run_load(*_subtareas("nodo-b", "nodo-c"), *_subtareas("nodo-d", status=status))
    assert "hosts con sub-tareas completadas: 2" in _texto(problemas_de_reparto(_tres_workers(), run_load))


def test_subtarea_completada_sin_host_no_cuenta():
    run_load = _run_load(*_subtareas("nodo-b", "nodo-c", None))
    assert "hosts con sub-tareas completadas: 2" in _texto(problemas_de_reparto(_tres_workers(), run_load))


def test_metricas_agregadas_no_sustituyen_a_los_reportes():
    run_load = {
        "timed_out": False,
        "metrics": {"subtasks_per_host": {"nodo-b": 5, "nodo-c": 4, "nodo-d": 6}},
        "reports": {},
    }
    assert "hosts con sub-tareas completadas: 0" in _texto(problemas_de_reparto(_tres_workers(), run_load))


def test_corrida_con_timed_out_se_rechaza():
    run_load = _run_load(*_subtareas("nodo-b", "nodo-c", "nodo-d"), timed_out=True)
    assert "timed_out" in _texto(problemas_de_reparto(_tres_workers(), run_load))


def test_host_ajeno_a_los_activos_se_rechaza():
    run_load = _run_load(*_subtareas("nodo-b", "nodo-c", "nodo-d", "nodo-x"))
    assert "'nodo-x'" in _texto(problemas_de_reparto(_tres_workers(), run_load))


def test_host_de_un_worker_caido_se_rechaza():
    workers = _tres_workers() + [_worker("nodo-e", "100.64.0.5", alive=False)]
    run_load = _run_load(*_subtareas("nodo-b", "nodo-c", "nodo-d", "nodo-e"))
    assert "'nodo-e'" in _texto(problemas_de_reparto(workers, run_load))


@pytest.mark.parametrize("run_load", [
    {},
    {"reports": {}},
    {"reports": {"caso-1": None}},
    {"reports": {"caso-1": {}}},
    {"reports": {"caso-1": {"subtasks_by_operation": None}}},
    _run_load(),
])
def test_json_de_run_load_sin_reportes_se_rechaza(run_load):
    assert "hosts con sub-tareas completadas: 0" in _texto(problemas_de_reparto(_tres_workers(), run_load))
