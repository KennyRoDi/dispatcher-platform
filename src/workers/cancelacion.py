from __future__ import annotations

import logging
import threading

logger = logging.getLogger(__name__)

CANCEL_PATTERN = "cancel:*"


class SubprocesosPorCaso:
    def __init__(self, supervisor):
        self._supervisor = supervisor
        self._pids: dict[str, set[int]] = {}
        self._lock = threading.Lock()

    def para_subtarea(self, case_id: str) -> "_SupervisorDeSubtarea":
        return _SupervisorDeSubtarea(self, case_id)

    def cancelar_caso(self, case_id: str) -> None:
        with self._lock:
            pids = sorted(self._pids.get(case_id, ()))
        for pid in pids:
            try:
                self._supervisor.cancel(pid)
            except Exception:
                logger.exception("no se pudo cancelar el subproceso %s del caso %s", pid, case_id)

    def _registrar(self, case_id: str, pid: int) -> None:
        with self._lock:
            self._pids.setdefault(case_id, set()).add(pid)

    def _olvidar(self, case_id: str, pids: set[int]) -> None:
        with self._lock:
            restantes = self._pids.get(case_id, set()) - pids
            if restantes:
                self._pids[case_id] = restantes
            else:
                self._pids.pop(case_id, None)


class _SupervisorDeSubtarea:
    def __init__(self, registro: SubprocesosPorCaso, case_id: str):
        self._registro = registro
        self._case_id = case_id
        self._pids: set[int] = set()

    def start(self, argv, scratch) -> int:
        pid = self._registro._supervisor.start(argv, scratch=scratch)
        self._pids.add(pid)
        self._registro._registrar(self._case_id, pid)
        return pid

    def cancel(self, pid: int) -> None:
        self._registro._supervisor.cancel(pid)

    def cerrar(self) -> None:
        self._registro._olvidar(self._case_id, self._pids)


def escuchar_cancelaciones(redis_client, registro: SubprocesosPorCaso, stop_event: threading.Event) -> threading.Thread:
    pubsub = redis_client.pubsub(ignore_subscribe_messages=True)
    pubsub.psubscribe(CANCEL_PATTERN)

    def bucle() -> None:
        try:
            while not stop_event.is_set():
                mensaje = pubsub.get_message(timeout=0.1)
                if mensaje and mensaje.get("data"):
                    registro.cancelar_caso(str(mensaje["data"]))
        finally:
            pubsub.close()

    hilo = threading.Thread(target=bucle, name="cancel-listener", daemon=True)
    hilo.start()
    return hilo
