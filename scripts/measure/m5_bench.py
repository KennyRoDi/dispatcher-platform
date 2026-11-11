import argparse
import json
import sys
import time
import wave
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.domain.benchmark import Corrida, ResumenConfig, resumir  # noqa: E402

COMPUTOS = {"cpu-float32": "float32", "cpu-int8": "int8"}


@dataclass(frozen=True)
class Config:
    computo: str
    compute_type: str
    hilos: int

    @property
    def nombre(self) -> str:
        return f"{self.computo}-h{self.hilos}"


def parsear_configs(computos: str, hilos: str) -> list[Config]:
    nombres = [c.strip() for c in computos.split(",") if c.strip()]
    numeros = [int(h) for h in hilos.split(",") if h.strip()]
    desconocidos = [c for c in nombres if c not in COMPUTOS]
    if desconocidos:
        raise ValueError(f"cómputo no soportado {desconocidos}; válidos: {sorted(COMPUTOS)} (GPU: medición pendiente)")
    if not nombres or not numeros or any(h < 1 for h in numeros):
        raise ValueError("hilos debe ser una lista de enteros >= 1 y cómputo no puede estar vacío")
    return [Config(c, COMPUTOS[c], h) for c in nombres for h in numeros]


def medir(
    config: Config, audios: list[Path], repeticiones: int, transcriptor,
    reloj: Callable[[], float], memoria_mb: Callable[[], float], duracion_audio: Callable[[Path], float],
) -> list[Corrida]:
    if not audios:
        raise ValueError("se necesita al menos un audio")
    if repeticiones < 1:
        raise ValueError("repeticiones debe ser >= 1")
    duracion = sum(duracion_audio(a) for a in audios)
    _transcribir_todos(transcriptor, audios)
    corridas = []
    for repeticion in range(1, repeticiones + 1):
        inicio = reloj()
        _transcribir_todos(transcriptor, audios)
        segundos = reloj() - inicio
        corridas.append(Corrida(config.nombre, repeticion, segundos, duracion, memoria_mb()))
    return corridas


def _transcribir_todos(transcriptor, audios: list[Path]) -> None:
    for audio in audios:
        transcriptor.transcribe(audio)


def escribir_json(resumenes: list[ResumenConfig], destino: Path) -> None:
    destino.write_text(json.dumps([asdict(r) for r in resumenes], indent=2), encoding="utf-8")


def duracion_wav(ruta: Path) -> float:
    with wave.open(str(ruta), "rb") as w:
        return w.getnframes() / w.getframerate()


def ejecutar(configs: list[Config], audios: list[Path], repeticiones: int, config_whisper: Path, salida: Path) -> list[ResumenConfig]:
    import psutil

    from src.adapters.whisper_transcriber import WhisperTranscriber, cargar_config_de_audio

    proceso = psutil.Process()
    base = cargar_config_de_audio(config_whisper)
    corridas: list[Corrida] = []
    for config in configs:
        transcriptor = _construir(WhisperTranscriber, replace(base, compute_type=config.compute_type, hilos=config.hilos))
        corridas += medir(
            config, audios, repeticiones, transcriptor, time.perf_counter,
            lambda: proceso.memory_info().rss / 1024 / 1024, duracion_wav,
        )
        del transcriptor
    resumenes = resumir(corridas)
    escribir_json(resumenes, salida)
    return resumenes


def _construir(clase, config_whisper):
    from faster_whisper import WhisperModel

    modelo = WhisperModel(
        config_whisper.nombre, device="cpu", compute_type=config_whisper.compute_type,
        cpu_threads=config_whisper.hilos, revision=config_whisper.revision,
    )
    return clase(modelo, config_whisper)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Benchmark de inferencia M5")
    p.add_argument("--compute", default="cpu-float32,cpu-int8")
    p.add_argument("--threads", default="1,2,4")
    p.add_argument("--reps", type=int, default=5)
    p.add_argument("--audio", type=Path, required=True, help="archivo .wav o carpeta con .wav")
    p.add_argument("--config", type=Path, default=ROOT / "config" / "audio.toml")
    p.add_argument("--salida", type=Path, default=Path("m5_bench.json"))
    args = p.parse_args(argv)
    audios = sorted(args.audio.glob("*.wav")) if args.audio.is_dir() else [args.audio]
    resumenes = ejecutar(parsear_configs(args.compute, args.threads), audios, args.reps, args.config, args.salida)
    print("config,latencia_media_s,latencia_p95_s,throughput_x_realtime,memoria_pico_mb,repeticiones")
    for r in resumenes:
        print(f"{r.config},{r.latencia_media_s:.3f},{r.latencia_p95_s:.3f},{r.throughput_x_realtime:.3f},{r.memoria_pico_mb:.0f},{r.repeticiones}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
