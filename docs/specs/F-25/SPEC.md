# SPEC F-25: Recepción no bloqueante

**Fase:** tests
**Base:** feat/F-25-1-responder-durante-subidas-grandes
**Verificación IA:** revision 054552e8
**Historia:** US-25 · **Requisitos:** RF-34, [B.5 M3] · **Responsable:** V

## Objetivo

El enunciado pide para M3 «E/S asíncrona o no bloqueante en la recepción» [B.5 M3] y RF-34 exige que, durante una subida grande, otra petición de la API responda sin esperar a que termine. F-22 ya lee cada chunk con `async for` y procesa `receive` en el pool de hilos (AD-13). Queda un punto bloqueante: `PUT /uploads/{id}/chunks/{index}` llama a `expected_size`, que lee el manifiesto del disco dentro del event loop; con un disco lento o un volumen de red, cada chunk frena a toda la API. F-25 lo saca del event loop y demuestra con pruebas y medición que la API responde durante subidas grandes.

## Alcance

**Incluye:** mover `expected_size` al pool de hilos; prueba unitaria de no bloqueo; prueba de integración con uvicorn real y una subida lenta en paralelo con peticiones ligeras; script de medición de latencia durante la subida y su sección en la ficha M3.

**No incluye:** cambiar el pool de hilos de AnyIO (40 hilos por defecto); E/S asíncrona del disco (`aiofiles`), que AD-13 descarta a favor del hilo acotado; cambios en el cliente.

## Criterios de aceptación

De `docs/backlog/m3-es-almacenamiento.md` (US-25):

- **Dado** una subida lenta en curso
- **Cuando** llega otra petición
- **Entonces** responde sin esperar a que termine la subida

Criterios adicionales derivados de los requisitos:

- RF-34: mientras un `PUT` espera bytes de un cliente lento o lee un manifiesto en un disco lento, otra petición a la API se atiende antes de que ese `PUT` termine.
- RF-34: con uvicorn real, durante la subida de un chunk de 16 MiB enviado lentamente, 20 peticiones ligeras seguidas responden antes de que termine y la subida termina con 204.

## Diseño

**Contratos.** Sin cambios en puertos ni contratos.

| Capa | Archivo | Cambio | Dueño |
|---|---|---|---|
| Coordinador | `src/coordinator/rutas_archivos.py` | `recibir` obtiene `expected_size` con `run_in_threadpool`, igual que `receive` | Melany |
| Medición | `scripts/measure/m3_no_bloqueo.py` (nuevo), `docs/modulo-M3-es-almacenamiento.md` | Subida lenta de N MiB y, en paralelo, `GET /health` cada 100 ms; registra latencias | Melany |

**Decisiones.** Aplica AD-13 sin cambiarla. Sin supuestos nuevos.

**Código del I Proyecto que reutiliza.** El servidor uvicorn y `/health` de `rutas_monitoreo.py`.

## Pruebas

| Tipo | Prueba | Demuestra |
|---|---|---|
| Unitaria | `test_subida_lenta_no_bloquea_otra_peticion`: un `PUT` cuyo cuerpo llega en partes controladas por eventos; otra ruta responde mientras el cuerpo sigue abierto | Recepción `async` del cuerpo |
| Unitaria | `test_manifiesto_lento_no_bloquea_otra_peticion`: `load_manifest` del staging se bloquea hasta que otra petición se atiende; con la lectura en el event loop, la otra petición no llega a atenderse | Lectura del manifiesto fuera del event loop |
| Integración | uvicorn real: chunk de 16 MiB enviado en partes lentas y 20 peticiones ligeras seguidas durante la subida; todas responden antes de que termine | Criterio de US-25 con servidor real |
| Integración | `test_recepcion_no_bloqueante_disco.py` (QA): `DiskChunkStaging` real con `load_manifest` demorado 1 s; los `GET` responden en menos de 0,5 s y el chunk queda en disco | El cambio de F-25 con disco real; falla si `expected_size` vuelve al event loop |

## Mediciones

M3, recepción no bloqueante (RF-34):

```bash
python scripts/measure/m3_no_bloqueo.py --url <coordinador> --mib 256 --kbps 8192 --out m3_no_bloqueo.csv
```

Registra la latencia de `GET /health` antes, durante y después de la subida. Tres repeticiones. Ficha de destino: `docs/modulo-M3-es-almacenamiento.md`, sección de recepción no bloqueante, con la distribución de latencias. Basta un coordinador; no requiere tres nodos.

## Plan de pila

| Parte | PR (título en Conventional Commits) | Contenido |
|---|---|---|
| 1 | `feat(F-25): responder durante subidas grandes` | `expected_size` en el pool de hilos y las tres pruebas. Estimado: ~5 líneas de código |
| 2 | `docs(F-25): medir latencia durante subidas grandes` | Script de medición y sección de la ficha M3 con datos medidos |

## Riesgos y preguntas abiertas

1. **Pool de hilos compartido.** `receive`, `complete` y los handlers síncronos (como `/health`) comparten el limitador de AnyIO de 40 hilos. Muchas subidas en paralelo podrían ocuparlo. La medición lo observa; si hace falta, un limitador propio para `complete` iría en otra parte.
2. **Medición.** La puede correr cualquier integrante con un coordinador; los números se miden, nunca se estiman.

## Aprobaciones

Las registra `scripts/flujo.py`. No editar.

| Fase | Aprobó | Fecha | Excepción o motivo |
|---|---|---|---|
| verificación IA de plan | Claude (Opus 5.5) | 2026-11-11 | SPEC sin subagente. Comprobado en codigo: PUT ya lee async y receive va en run_in_threadpool (F-22); expected_size lee el manifiesto en el event loop. Aplica AD-13. Conformidad 0. (7149b5ba) |
| plan | Melany Vindas | 2026-11-11 |  |
| verificación IA de tests | Claude (Opus 5.5) | 2026-11-11 | Sin subagente. 2 unitarias (cuerpo lento, manifiesto lento) y 1 de integracion con uvicorn real (16 MiB lentos, 20 peticiones en paralelo). Rojo: el manifiesto lento bloquea la API 5 s; las otras dos pasan porque F-22 ya lee async. (e69130db) |
| tests | Melany Vindas | 2026-11-11 | Suite verificada en Linux por Claude; en Windows falla test_generar_certs, ajena a F-25. |
| verificación IA de implementacion | Claude (Opus 5.5) | 2026-11-11 | Sin subagente. expected_size en run_in_threadpool (1 linea). Unitarias 43/43, integracion uvicorn 3/3, suite 3610 verde en Linux. (444da75f) |
| implementacion | Melany Vindas | 2026-11-11 | Suite verificada en Linux por Claude; en Windows falla test_generar_certs, ajena a F-25. |
| verificación IA de verificacion | Claude (Opus 5.5) | 2026-11-11 | QA independiente (subagente) APROBADO: pruebas 3/3; con DiskChunkStaging real y uvicorn real, GET responde en menos de 0.5 s durante un chunk lento; mutante sin run_in_threadpool detectado; no quedan llamadas bloqueantes en handlers async. Agrego prueba con disco real porque la de integracion usaba el doble. (3532dc6b) |
| verificacion | Melany Vindas | 2026-11-11 | Suite verificada en Linux por Claude; en Windows falla test_generar_certs, ajena a F-25. |
| verificación IA de documentacion | Claude (Opus 5.5) | 2026-11-11 | Documentacion: SPEC ajustado (peticiones seguidas, prueba con disco real); sin ficha, la medicion es la parte 2; bitacora con un error real de la IA. (be567ec8) |
| documentacion | Melany Vindas | 2026-11-11 |  |
| verificación IA de revision | Claude (Opus 5.5) | 2026-11-11 | Revision no independiente: 2 lineas de codigo en rutas_archivos.py y 3 archivos de prueba; cumple el SPEC parte 1 sin agregados; capas y commits correctos. (054552e8) |
| revision | Melany Vindas | 2026-11-11 |  |
