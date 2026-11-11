from importlib import import_module

import pytest

MIB = 1024 * 1024
PS_CON_FFMPEG = (
    "  PID  PPID STAT   RSS CMD\n"
    "    1     0 Ss    1200 python -m src.workers.worker_node\n"
    "   88     1 Sl  210000 ffmpeg -i /scratch/c1/in.mp4 out.mp4\n"
    "   91    88 S      900 ffmpeg -i /scratch/c1/in.mp4 out2.mp4\n"
)
PS_SIN_FFMPEG = "  PID  PPID STAT   RSS CMD\n    1     0 Ss    1200 python -m src.workers.worker_node\n"


def cancel_heavy():
    return import_module("scenarios.cancel_heavy")


def ejecutor_de(respuestas):
    llamadas = []

    def ejecutar(argv):
        llamadas.append(tuple(argv))
        for prefijo, salida in respuestas.items():
            if prefijo in " ".join(argv):
                return salida
        raise AssertionError(f"comando inesperado: {argv}")

    ejecutar.llamadas = llamadas
    return ejecutar


def test_genera_archivo_sintetico_del_tamano_pedido(tmp_path):
    ruta = cancel_heavy().generar_archivo_pesado(tmp_path / "pesado.bin", megabytes=2)
    assert ruta.stat().st_size >= 2 * MIB


def test_tamano_por_defecto_cumple_el_minimo_de_200_mb():
    assert cancel_heavy().MEGABYTES_MINIMOS >= 200


def test_rechaza_archivo_menor_al_minimo_del_enunciado(tmp_path):
    with pytest.raises(ValueError):
        cancel_heavy().generar_archivo_pesado(tmp_path / "chico.bin", megabytes=10, exigir_minimo=True)


def test_instantanea_ejecuta_los_tres_comandos_de_la_ficha():
    ejecutar = ejecutor_de(
        {"ps -eo": PS_CON_FFMPEG, "ls -la /scratch": "total 0\ndrwx c1\n", "memory.current": "734003200\n"}
    )
    cancel_heavy().tomar_instantanea(ejecutar, "antes")
    texto = [" ".join(c) for c in ejecutar.llamadas]
    assert any("ps -eo pid,ppid,stat,rss,cmd" in t for t in texto)
    assert any("ls -la /scratch" in t for t in texto)
    assert any("cat /sys/fs/cgroup/memory.current" in t for t in texto)


def test_instantanea_interpreta_procesos_scratch_y_memoria():
    ejecutar = ejecutor_de(
        {"ps -eo": PS_CON_FFMPEG, "ls -la /scratch": "total 4\ndrwxr-xr-x 2 w w 4096 c1\n", "memory.current": "734003200\n"}
    )
    inst = cancel_heavy().tomar_instantanea(ejecutar, "antes")
    assert inst["etiqueta"] == "antes"
    assert inst["pids_subtareas"] == [88, 91]
    assert inst["scratch"] == ["c1"]
    assert inst["memory_current"] == 734003200


def test_instantanea_ignora_procesos_ajenos_a_las_subtareas():
    ejecutar = ejecutor_de({"ps -eo": PS_SIN_FFMPEG, "ls -la /scratch": "total 0\n", "memory.current": "1000\n"})
    inst = cancel_heavy().tomar_instantanea(ejecutar, "despues")
    assert inst["pids_subtareas"] == []
    assert inst["scratch"] == []


def test_evaluar_cumple_si_no_quedan_procesos_ni_scratch_y_baja_la_memoria():
    antes = {"pids_subtareas": [88, 91], "scratch": ["c1"], "memory_current": 700 * MIB}
    despues = {"pids_subtareas": [], "scratch": [], "memory_current": 90 * MIB}
    veredicto = cancel_heavy().evaluar(antes, despues, estado_caso="cancelled")
    assert veredicto["cumple"] is True
    assert veredicto["problemas"] == []


@pytest.mark.parametrize(
    "despues, estado, fragmento",
    [
        ({"pids_subtareas": [88], "scratch": [], "memory_current": 90 * MIB}, "cancelled", "proceso"),
        ({"pids_subtareas": [], "scratch": ["c1"], "memory_current": 90 * MIB}, "cancelled", "scratch"),
        ({"pids_subtareas": [], "scratch": [], "memory_current": 800 * MIB}, "cancelled", "memoria"),
        ({"pids_subtareas": [], "scratch": [], "memory_current": 90 * MIB}, "running", "cancelled"),
    ],
)
def test_evaluar_senala_cada_incumplimiento(despues, estado, fragmento):
    antes = {"pids_subtareas": [88], "scratch": ["c1"], "memory_current": 700 * MIB}
    veredicto = cancel_heavy().evaluar(antes, despues, estado_caso=estado)
    assert veredicto["cumple"] is False
    assert any(fragmento in p for p in veredicto["problemas"])


def test_tiempo_de_liberacion_es_hasta_el_ultimo_proceso_ausente():
    muestras = [(0.0, [88, 91]), (0.5, [91]), (1.25, []), (2.0, [])]
    assert cancel_heavy().tiempo_liberacion(muestras) == pytest.approx(1.25)


def test_tiempo_de_liberacion_sin_liberar_es_none():
    assert cancel_heavy().tiempo_liberacion([(0.0, [88]), (1.0, [88])]) is None


def test_espera_maxima_supera_la_gracia_del_supervisor():
    assert cancel_heavy().ESPERA_MAXIMA_SEGUNDOS > 10
