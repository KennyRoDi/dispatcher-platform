from dataclasses import dataclass
from multiprocessing import get_context
from multiprocessing.connection import Connection
from collections.abc import Callable
from typing import Any
import traceback


@dataclass
class ForkHandle:
    process: Any
    receiver: Connection

    @property
    def exitcode(self) -> int | None:
        return self.process.exitcode

    def is_alive(self) -> bool:
        return self.process.is_alive()


def _run(sender: Connection, target: Callable, args: tuple) -> None:
    try:
        sender.send((True, target(*args)))
    except BaseException as error:
        sender.send((False, (type(error).__name__, str(error), traceback.format_exc())))
        raise SystemExit(1)
    finally:
        sender.close()


class ForkProcessRuntime:
    def __init__(self, timeout: float = 120) -> None:
        if timeout <= 0:
            raise ValueError("timeout debe ser positivo")
        self.timeout = timeout

    def start(self, target: Callable, args: tuple, *, method: str) -> ForkHandle:
        if method != "fork":
            raise ValueError("el runtime solo admite fork")
        context = get_context("fork")
        receiver, sender = context.Pipe(duplex=False)
        process = context.Process(target=_run, args=(sender, target, args))
        try:
            process.start()
        except BaseException:
            receiver.close()
            sender.close()
            raise
        sender.close()
        return ForkHandle(process, receiver)

    def result(self, handle: ForkHandle) -> Any:
        if not handle.receiver.poll(self.timeout):
            raise TimeoutError("el proceso excedió el tiempo límite")
        try:
            succeeded, value = handle.receiver.recv()
        except EOFError as error:
            raise RuntimeError("el proceso terminó sin devolver resultado") from error
        if not succeeded:
            name, message, trace = value
            raise RuntimeError(f"{name}: {message}\n{trace}")
        return value

    def terminate(self, handle: ForkHandle) -> None:
        if handle.process.is_alive():
            handle.process.terminate()

    def join(self, handle: ForkHandle) -> None:
        handle.process.join(self.timeout)
        handle.receiver.close()
        if handle.process.is_alive():
            raise TimeoutError("el proceso no terminó después de join")
