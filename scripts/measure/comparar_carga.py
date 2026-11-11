import argparse
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import multiprocessing
import os
from pathlib import Path
import platform
import signal
import sys
import time
from collections import defaultdict
import traceback

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.adapters.whisper_transcriber import WhisperTranscriber, cargar_config_de_audio  # noqa: E402
from src.domain.model_loading import LoadingConfig  # noqa: E402
from src.infrastructure.model_memory import (  # noqa: E402
    CgroupMemory,
    ProcessMemory,
    read_cgroup_memory,
    read_process_memory,
)


ESTRATEGIAS = ("por_proceso", "workers_compartidos")


@dataclass(frozen=True)
class Snapshot:
    stage: str
    pids: dict[int, ProcessMemory]
    cgroup: CgroupMemory

    @property
    def rss_bytes(self) -> int:
        return sum(memory.rss_bytes for memory in self.pids.values())

    @property
    def pss_bytes(self) -> int:
        return sum(memory.pss_bytes for memory in self.pids.values())


class MeasurementRunner:
    def __init__(self, factory, timeout: float, cgroup: Path):
        self.factory = factory
        self.timeout = timeout
        self.cgroup = cgroup
        self.context = multiprocessing.get_context("fork")

    def run(self, strategy: str, workers: int, path: Path, measure: bool):
        config = LoadingConfig(strategy, workers)
        deadline = time.monotonic() + self.timeout
        baseline = read_cgroup_memory(self.cgroup) if measure else None
        count = workers if strategy == "por_proceso" else 1
        processes = []
        connections = []
        try:
            for _ in range(count):
                parent, child = self.context.Pipe(duplex=True)
                process = self.context.Process(
                    target=_child,
                    args=(child, self.factory, path, config.strategy,
                          config.processes if strategy == "workers_compartidos" else 1),
                )
                try:
                    process.start()
                except BaseException:
                    parent.close()
                    child.close()
                    raise
                child.close()
                processes.append(process)
                connections.append(parent)
            self._await(connections, "loaded", deadline)
            snapshots = [self._snapshot("loaded", processes)] if measure else []
            self._release(connections)
            results = self._await(connections, "inferred", deadline)
            if measure:
                snapshots.append(self._snapshot("inferred", processes))
            self._release(connections)
            self._join(processes, deadline)
            outputs = results[0] if strategy == "workers_compartidos" else results
            return outputs, snapshots, baseline
        except BaseException as error:
            cleanup_errors = []
            for process in processes:
                try:
                    if process.is_alive():
                        process.terminate()
                except BaseException as cleanup_error:
                    cleanup_errors.append(cleanup_error)
            for process in processes:
                try:
                    process.join(1)
                    if process.is_alive():
                        process.kill()
                        process.join(1)
                    if process.is_alive():
                        cleanup_errors.append(TimeoutError("no se pudo recolectar un proceso hijo"))
                except BaseException as cleanup_error:
                    cleanup_errors.append(cleanup_error)
            if cleanup_errors:
                error.add_note(f"falló la limpieza de hijos: {cleanup_errors!r}")
            raise
        finally:
            for connection in connections:
                connection.close()
            for process in processes:
                if process.pid is not None and not process.is_alive():
                    process.close()

    def _await(self, connections, stage, deadline):
        messages = []
        pending = set(range(len(connections)))
        while pending:
            progressed = False
            for index in tuple(pending):
                connection = connections[index]
                if connection.poll(0):
                    message = connection.recv()
                    if message[0] == "error":
                        raise RuntimeError(f"hijo: {message[1]}\n{message[2]}")
                    if message[0] != stage:
                        raise RuntimeError(f"etapa inesperada: {message[0]}")
                    messages.append(message[1])
                    pending.remove(index)
                    progressed = True
            if pending and time.monotonic() >= deadline:
                raise TimeoutError(f"timeout esperando etapa {stage}")
            if pending and not progressed:
                time.sleep(0.01)
        return messages

    @staticmethod
    def _release(connections):
        for connection in connections:
            connection.send("continue")

    def _snapshot(self, stage, processes):
        pids = [os.getpid(), *(process.pid for process in processes)]
        readings = {pid: read_process_memory(pid) for pid in pids if pid is not None}
        return Snapshot(stage, readings, read_cgroup_memory(self.cgroup))

    def _join(self, processes, deadline):
        for process in processes:
            process.join(max(0, deadline - time.monotonic()))
            if process.is_alive():
                raise TimeoutError("el proceso no terminó después de join")
            if process.exitcode != 0:
                raise RuntimeError(f"el proceso hijo terminó con código {process.exitcode}")


def _child(connection, factory, path, strategy, workers):
    try:
        model = factory(workers)
        connection.send(("loaded", os.getpid()))
        connection.recv()
        if strategy == "workers_compartidos":
            with ThreadPoolExecutor(max_workers=workers) as pool:
                results = list(pool.map(model.transcribe, [path] * workers))
        else:
            results = [model.transcribe(path)]
        connection.send(("inferred", results))
        connection.recv()
    except BaseException as error:
        try:
            connection.send(("error", f"{type(error).__name__}: {error}", traceback.format_exc()))
        except (BrokenPipeError, EOFError, OSError):
            pass
        raise SystemExit(1)
    finally:
        connection.close()


def validar_equivalencia(salidas):
    if set(salidas) != set(ESTRATEGIAS):
        raise ValueError("faltan estrategias o hay estrategias no admitidas")
    referencia = salidas[ESTRATEGIAS[0]]
    if not referencia or any(salidas[estrategia] != referencia for estrategia in ESTRATEGIAS[1:]):
        raise ValueError("las salidas de las estrategias no coinciden")
    return salidas


def _transcriber_factory(config_path: Path, hilos: int):
    return lambda workers: WhisperTranscriber.from_config(
        config_path, num_workers=workers, hilos=hilos
    )


def _arguments(argv=None):
    parser = argparse.ArgumentParser(description="Compara estrategias de carga de Whisper para F-19")
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--hilos", type=int, required=True)
    parser.add_argument("--entrada", type=Path, required=True)
    parser.add_argument("--procesos", type=int, nargs="+", required=True)
    parser.add_argument("--estrategias", choices=ESTRATEGIAS, nargs="+", required=True)
    parser.add_argument("--repeticiones", type=int, default=1)
    parser.add_argument("--timeout", type=float, default=120)
    parser.add_argument("--cgroup", type=Path, default=Path("/sys/fs/cgroup"))
    parser.add_argument("--solo-validar", action="store_true")
    parser.add_argument("--salida", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.hilos <= 0 or args.repeticiones <= 0 or args.timeout <= 0:
        parser.error("hilos, repeticiones y timeout deben ser positivos")
    if any(type(count) is not int or count <= 0 for count in args.procesos):
        parser.error("procesos debe contener enteros positivos")
    if set(args.estrategias) != set(ESTRATEGIAS):
        parser.error("deben indicarse ambas estrategias")
    if len(args.estrategias) != len(ESTRATEGIAS):
        parser.error("cada estrategia debe indicarse una vez")
    if not args.config.is_file() or not args.entrada.is_file():
        parser.error("config y entrada deben existir")
    return args


def _run(args):
    if os.name != "posix":
        raise RuntimeError("la comparación de memoria requiere Linux/POSIX")
    original_sigterm = signal.getsignal(signal.SIGTERM)
    signal.signal(signal.SIGTERM, _handle_sigterm)
    try:
        factory = _transcriber_factory(args.config, args.hilos)
        runner = MeasurementRunner(factory, args.timeout, args.cgroup)
        runs = []
        counts = [args.procesos[0]] if args.solo_validar else args.procesos
        repeats = 1 if args.solo_validar else args.repeticiones
        strategies = args.estrategias
        for workers in counts:
            for repetition in range(1, repeats + 1):
                by_strategy = {}
                for strategy in strategies:
                    outputs, snapshots, baseline = runner.run(
                        strategy, workers, args.entrada, measure=not args.solo_validar
                    )
                    by_strategy[strategy] = outputs
                    runs.append(_record_run(strategy, workers, repetition, outputs, snapshots, baseline))
                validar_equivalencia(by_strategy)
        _write_output(args, runs)
    finally:
        signal.signal(signal.SIGTERM, original_sigterm)


def _record_run(strategy, workers, repetition, outputs, snapshots, baseline):
    return {
        "strategy": strategy,
        "workers": workers,
        "repetition": repetition,
        "outputs": [[asdict(segment) for segment in result] for result in outputs],
        "baseline": asdict(baseline) if baseline is not None else None,
        "snapshots": [
            {
                "stage": snapshot.stage,
                "pids": {str(pid): asdict(memory) for pid, memory in snapshot.pids.items()},
                "rss_bytes": snapshot.rss_bytes,
                "pss_bytes": snapshot.pss_bytes,
                "cgroup": asdict(snapshot.cgroup),
            }
            for snapshot in snapshots
        ],
    }


def _write_output(args, runs):
    args.salida.mkdir(parents=True, exist_ok=True)
    model_config = replace(cargar_config_de_audio(args.config), hilos=args.hilos)
    record = {
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "node": platform.node(),
        "kernel": platform.release(),
        "python": sys.version,
        "versions": {
            name: importlib.metadata.version(name)
            for name in ("faster-whisper", "ctranslate2", "av")
        },
        "config": asdict(model_config),
        "input_sha256": hashlib.sha256(args.entrada.read_bytes()).hexdigest(),
        "runs": runs,
        "summary": summarize_runs(runs),
    }
    destination = args.salida / f"run-{datetime.now(timezone.utc):%Y%m%dT%H%M%S%fZ}.json"
    destination.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    print(destination)


def summarize_runs(runs):
    grouped = defaultdict(list)
    for run in runs:
        baseline = run["baseline"]["memory_current"] if run["baseline"] else None
        for snapshot in run["snapshots"]:
            grouped[(run["strategy"], run["workers"], snapshot["stage"])].append(
                {
                    "rss_bytes": snapshot["rss_bytes"],
                    "pss_bytes": snapshot["pss_bytes"],
                    "memory_current_bytes": snapshot["cgroup"]["memory_current"],
                    "memory_current_delta_bytes": (
                        snapshot["cgroup"]["memory_current"] - baseline
                        if baseline is not None else None
                    ),
                }
            )
    summaries = []
    for (strategy, workers, stage), values in sorted(grouped.items()):
        metrics = {}
        for metric in values[0]:
            numbers = [value[metric] for value in values if value[metric] is not None]
            if not numbers:
                continue
            low, high = min(numbers), max(numbers)
            metrics[metric] = {
                "mean": sum(numbers) / len(numbers),
                "min": low,
                "max": high,
                "range": high - low,
            }
        summaries.append(
            {"strategy": strategy, "workers": workers, "stage": stage,
             "repetitions": len(values), "metrics": metrics}
        )
    return summaries


def main():
    _run(_arguments())


def _handle_sigterm(_signum, _frame):
    raise InterruptedError("medición interrumpida por SIGTERM")


if __name__ == "__main__":
    main()
