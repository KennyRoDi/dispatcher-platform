import ipaddress

RANGO_TAILSCALE = ipaddress.ip_network("100.64.0.0/10")
MINIMO_NODOS = 3


def _ip_de_tailscale(ip) -> bool:
    try:
        return ipaddress.ip_address(ip) in RANGO_TAILSCALE
    except ValueError:
        return False


def _activos(workers: list[dict]) -> list[dict]:
    return [worker for worker in workers if worker.get("alive") is True]


def _hostname_valido(hostname) -> bool:
    return bool(hostname) and hostname != "unknown"


def _repetidos(pares: set[tuple[str, str]], clave: int) -> dict[str, list[str]]:
    agrupados: dict[str, list[str]] = {}
    for par in sorted(pares):
        agrupados.setdefault(par[clave], []).append(par[1 - clave])
    return {valor: otros for valor, otros in agrupados.items() if len(otros) > 1}


def problemas_de_workers(workers: list[dict]) -> list[str]:
    problemas = []
    pares = set()
    for worker in _activos(workers):
        hostname, ip = worker.get("hostname"), worker.get("ip")
        identificador = worker.get("worker_id")
        if not _hostname_valido(hostname):
            problemas.append(f"{identificador}: hostname no valido {hostname!r}")
        if not _ip_de_tailscale(ip):
            problemas.append(f"{identificador}: ip {ip!r} fuera de {RANGO_TAILSCALE}")
        if _hostname_valido(hostname) and _ip_de_tailscale(ip):
            pares.add((hostname, ip))

    # Varios workers por nodo son validos; un mismo nodo con dos IP, o una IP en dos nodos, no.
    for hostname, ips in _repetidos(pares, 0).items():
        problemas.append(f"hostname {hostname!r} repetido con varias ip: {ips}")
    for ip, hostnames in _repetidos(pares, 1).items():
        problemas.append(f"ip {ip!r} repetida en varios hostname: {hostnames}")

    if len(pares) < MINIMO_NODOS:
        problemas.append(f"nodos activos distintos: {len(pares)}, se exigen {MINIMO_NODOS}")
    return problemas


def _hosts_con_completadas(run_load: dict) -> list[str]:
    # metrics.subtasks_per_host no sirve aqui: cuenta tambien las sub-tareas fallidas.
    hosts = set()
    for reporte in run_load.get("reports", {}).values():
        for subtareas in ((reporte or {}).get("subtasks_by_operation") or {}).values():
            hosts.update(s.get("host") for s in subtareas if s.get("status") == "completed" and s.get("host"))
    return sorted(hosts)


def problemas_de_reparto(workers: list[dict], run_load: dict) -> list[str]:
    hosts = _hosts_con_completadas(run_load)
    activos = {worker.get("hostname") for worker in _activos(workers)}

    problemas = [f"host {host!r} con sub-tareas completadas no es un hostname activo"
                 for host in hosts if host not in activos]
    if len(hosts) < MINIMO_NODOS:
        problemas.append(f"hosts con sub-tareas completadas: {len(hosts)}, se exigen {MINIMO_NODOS}")
    if run_load.get("timed_out"):
        problemas.append("run_load termino con timed_out: la corrida esta incompleta")
    return problemas


def problemas_tres_nodos(workers: list[dict], run_load: dict) -> list[str]:
    return problemas_de_workers(workers) + problemas_de_reparto(workers, run_load)
