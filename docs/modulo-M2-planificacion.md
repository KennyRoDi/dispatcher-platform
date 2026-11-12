# M2 · Planificación

## Qué se implementó

F-20 agrega `Priority` (cuatro niveles), `SchedulingPolicy` (FIFO, aging) y `SchedulerState` en `src/domain/scheduling.py`: el aging es implícito, con `puntaje = t_entrada − bono(prioridad)` y el menor puntaje sale primero (AD-04). F-21 agrega `SchedulingPolicy.desde_configuracion(valor)` para elegir la política por configuración (variable `SCHED_POLICY`) y `scripts/measure/m2_sched.py`, que simula una carga sintética bajo cada política y mide espera, turnaround y throughput por nivel. F-34 mide, con `scenarios/worker_crash.py`, el tiempo real de detección y reasignación del reaper heredado ante la caída de un worker (ver `docs/evidencia/F-34_caida_worker_2026-11-12.md`): 20.0 s con el `reaper_interval` de producción, refinando la estimación informal de `docs/DEMO.md`.

## Concepto de Sistemas Operativos

Ambas políticas son lógica de planificación pura (sin E/S de red ni disco): deciden, dado un conjunto de casos en cola con su prioridad y momento de llegada, cuál se despacha primero. FIFO ordena estrictamente por `entered_at`. Aging ordena por un puntaje que favorece a los casos recientes de prioridad alta, pero cuya ventaja decae con el tiempo: un caso de baja prioridad que espera lo suficiente alcanza, y luego supera, el puntaje de los casos altos recientes, acotando su espera máxima a `bono(crítica) − bono(baja)` (400 ms con la configuración por defecto).

## Método de medición

`scripts/measure/m2_sched.py` simula un servidor único: encola `--low` casos de prioridad baja al inicio (t=0, ya en espera, como describe el criterio de aceptación), luego una ráfaga de `--high-rate` casos de prioridad alta que llegan de forma continua (intervalo medio 5 ms, con ruido gaussiano fijado por `--seed`), despachando a la mitad de esa tasa durante la ráfaga (intervalo medio de servicio 10 ms) para generar un backlog creciente, y drena el resto al terminar la ráfaga. El reloj es virtual (se parchea `time.time` dentro del script, igual que en las pruebas unitarias de F-20) para que la medición sea determinista y rápida, sin reloj real ni red:

```bash
SCHED_POLICY=fifo python scripts/measure/m2_sched.py --high-rate 100 --low 5 --seed 42 --out m2_fifo_42.csv
SCHED_POLICY=aging python scripts/measure/m2_sched.py --high-rate 100 --low 5 --seed 42 --out m2_aging_42.csv
```

Se repitió con las semillas 42, 43 y 44 para ambas políticas. El CSV crudo combinado está en `docs/evidencia/F-21_comparacion_politicas_2026-11-11.csv`.

**Nota de alcance:** esta es una simulación en memoria de la lógica de `SchedulerState` (CPU y orden de decisión), no una corrida distribuida sobre los tres nodos reales del clúster — F-20 y F-21 son puramente de dominio, sin E/S de red ni de disco, así que no hay nada adicional que medir en los nodos físicos para esta feature.

## Resultados

Media de las 3 repeticiones (ms, salvo throughput en casos/s):

| Política | Nivel | Espera (ms) | Turnaround (ms) | Throughput (casos/s) |
|---|---|---|---|---|
| FIFO | baja | 50.6 | 60.7 | 3.20 |
| FIFO | alta | 452.8 | 462.9 | 64.0 |
| Aging | baja | 235.0 | 244.2 | 3.20 |
| Aging | alta | 443.6 | 453.7 | 64.0 |

Espera máxima observada de la prioridad baja bajo aging, en las 3 repeticiones: **245.8 ms** (semilla 43), por debajo de la cota teórica de AD-04 (400 ms).

El throughput por nivel es igual entre políticas: con la misma semilla, ambas corridas despachan el mismo número total de casos en el mismo tiempo total (makespan); la política solo decide el *orden*, no la *cantidad* de trabajo hecho. La diferencia real está en la espera y el turnaround.

![Comparación FIFO vs aging por nivel](evidencia/F-21_comparacion_politicas_2026-11-11.png)

Generado con `python scripts/measure/m2_plot.py docs/evidencia/F-21_comparacion_politicas_2026-11-11.csv --out docs/evidencia/F-21_comparacion_politicas_2026-11-11.png`.

## Interpretación

En este escenario (el caso bajo ya está en cola cuando empieza la ráfaga de altos), FIFO despacha al caso bajo casi de inmediato porque ya estaba primero en el orden de llegada — su buen resultado aquí es un efecto de cuándo llegó, no una garantía general. Si ese mismo caso bajo llegara más tarde, en medio de una ráfaga continua de altos, FIFO lo haría esperar detrás de todos los altos que sigan llegando, sin ninguna cota: bajo carga sostenida, su espera puede crecer indefinidamente.

Aging, en cambio, sacrifica algo del buen trato que el caso bajo recibía en este escenario (su espera sube de ~51 ms a ~235 ms, porque los altos recientes lo adelantan mientras no haya envejecido lo suficiente) a cambio de una **cota garantizada**: sin importar cuándo llegue el caso bajo relativo a la ráfaga, su espera máxima queda acotada por `bono(crítica) − bono(baja)` = 400 ms, confirmado empíricamente (245.8 ms máximo observado, dentro de la cota). Los casos altos, a su vez, mejoran levemente su espera media bajo aging (452.8 → 443.6 ms) porque el puntaje los prioriza frente a la competencia entre ellos mismos.

La ausencia de inanición queda demostrada con datos: bajo aging, el caso de baja prioridad siempre se despachó dentro de la cota teórica en las 3 repeticiones, con una carga continua de casos altos que, de usarse FIFO con una llegada tardía del caso bajo, no tendría ese límite garantizado.
