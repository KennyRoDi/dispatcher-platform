from importlib import import_module

import pytest

from src.domain.admission import admits

MIB = 1024 * 1024
HUELLA = 100 * MIB
MAXIMO = 1024 * MIB
MARGEN = 64 * MIB
INTERVALO = 5.0


def saturacion():
    return import_module("scenarios.memory_saturation")


def plan_de_prueba(cupo=9):
    return saturacion().PlanCarga(cupo=cupo, subtareas=cupo * 2)


def muestra(instante, heartbeat, actual=500 * MIB, maximo=MAXIMO, oom=False, en_curso=3):
    return {
        "instante": instante,
        "ultimo_heartbeat": heartbeat,
        "memory_current": actual,
        "memory_max": maximo,
        "oom_killed": oom,
        "en_curso": en_curso,
    }


def muestras_sanas():
    return [muestra(t, t) for t in (0, 5, 10, 15, 20)]


def estados(terminal="completed", cantidad=18):
    return {f"s{i}": terminal for i in range(cantidad)}


def evaluar(muestras, finales, plan=None):
    return saturacion().evaluar(plan or plan_de_prueba(), muestras, finales, INTERVALO)


def test_cupo_coincide_con_el_de_admits():
    plan = saturacion().planificar_carga(MAXIMO, MARGEN, HUELLA, 2)
    assert admits(current=(plan.cupo - 1) * HUELLA, max=MAXIMO, footprint=HUELLA, margin=MARGEN)
    assert not admits(current=plan.cupo * HUELLA, max=MAXIMO, footprint=HUELLA, margin=MARGEN)


def test_la_carga_total_supera_memory_max_segun_el_factor():
    plan = saturacion().planificar_carga(MAXIMO, MARGEN, HUELLA, 2)
    assert plan.subtareas * HUELLA > MAXIMO
    assert plan.subtareas * HUELLA >= 2 * (MAXIMO - MARGEN)
    assert plan.subtareas > plan.cupo


def test_un_margen_mayor_reduce_el_cupo():
    chico = saturacion().planificar_carga(MAXIMO, 0, HUELLA, 2)
    grande = saturacion().planificar_carga(MAXIMO, 400 * MIB, HUELLA, 2)
    assert grande.cupo < chico.cupo


@pytest.mark.parametrize(
    "maximo,margen,huella,factor",
    [(0, 0, HUELLA, 2), (MAXIMO, -1, HUELLA, 2), (MAXIMO, 0, 0, 2), (MAXIMO, 0, HUELLA, 1), (MAXIMO, 0, HUELLA, 0)],
)
def test_parametros_invalidos_se_rechazan(maximo, margen, huella, factor):
    with pytest.raises(ValueError):
        saturacion().planificar_carga(maximo, margen, huella, factor)


def test_huella_mayor_que_la_memoria_disponible_se_rechaza():
    with pytest.raises(ValueError):
        saturacion().planificar_carga(MAXIMO, MARGEN, MAXIMO, 2)


def test_huecos_heartbeat_sin_hueco():
    assert saturacion().huecos_heartbeat([0, 5, 10, 15], INTERVALO, 3) == []


def test_huecos_heartbeat_detecta_intervalo_mayor_que_la_tolerancia():
    assert saturacion().huecos_heartbeat([0, 5, 30, 35], INTERVALO, 3) == [(5, 30)]


def test_huecos_heartbeat_acepta_el_limite_exacto():
    assert saturacion().huecos_heartbeat([0, 15], INTERVALO, 3) == []


def test_huecos_heartbeat_ordena_los_instantes():
    assert saturacion().huecos_heartbeat([35, 0, 30, 5], INTERVALO, 3) == [(5, 30)]


def test_evaluar_cumple_con_corrida_sana():
    assert evaluar(muestras_sanas(), estados()) == {"cumple": True, "problemas": []}


def test_evaluar_detecta_hueco_de_heartbeat():
    muestras = [muestra(0, 0), muestra(5, 5), muestra(30, 5), muestra(35, 35)]
    veredicto = evaluar(muestras, estados())
    assert not veredicto["cumple"]
    assert any("heartbeat" in p for p in veredicto["problemas"])


def test_evaluar_detecta_memory_current_sobre_memory_max():
    muestras = muestras_sanas() + [muestra(25, 25, actual=MAXIMO + 1)]
    veredicto = evaluar(muestras, estados())
    assert not veredicto["cumple"]
    assert any("memory.max" in p for p in veredicto["problemas"])


def test_evaluar_detecta_oomkilled():
    muestras = muestras_sanas() + [muestra(25, 25, oom=True)]
    veredicto = evaluar(muestras, estados())
    assert not veredicto["cumple"]
    assert any("OOM" in p for p in veredicto["problemas"])


def test_evaluar_detecta_subtarea_sin_terminar():
    finales = estados()
    finales["s3"] = "running"
    veredicto = evaluar(muestras_sanas(), finales)
    assert not veredicto["cumple"]
    assert any("s3" in p for p in veredicto["problemas"])


def test_evaluar_detecta_admision_por_encima_del_cupo():
    veredicto = evaluar(muestras_sanas() + [muestra(25, 25, en_curso=10)], estados(), plan_de_prueba(cupo=9))
    assert not veredicto["cumple"]
    assert any("cupo" in p for p in veredicto["problemas"])


def test_evaluar_exige_que_todas_las_subtareas_del_plan_tengan_estado():
    veredicto = evaluar(muestras_sanas(), estados(cantidad=17))
    assert not veredicto["cumple"]


def test_evaluar_sin_muestras_no_cumple():
    veredicto = evaluar([], estados())
    assert not veredicto["cumple"]


def test_tomar_muestra_arma_el_diccionario_con_el_ejecutor_inyectado():
    modulo = saturacion()
    respuestas = {
        modulo.COMANDO_MEMORY_CURRENT: f"{300 * MIB}\n",
        modulo.COMANDO_MEMORY_MAX: f"{MAXIMO}\n",
    }
    llamadas = []

    def ejecutar(argv):
        llamadas.append(tuple(argv))
        return respuestas[tuple(argv)]

    resultado = modulo.tomar_muestra(ejecutar, "worker-a", 12.5)

    assert resultado["etiqueta"] == "worker-a"
    assert resultado["instante"] == 12.5
    assert resultado["memory_current"] == 300 * MIB
    assert resultado["memory_max"] == MAXIMO
    assert llamadas
