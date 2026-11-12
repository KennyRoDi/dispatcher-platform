# F-11: tiempos entre intentos (2026-11-12)

Generado por `tests/acceptance/test_reintentos_log.py` con reloj real, fakeredis y un analizador sintético que siempre lanza `TimeoutError`. Configuración, no medición de SO: `MAX_ATTEMPTS=4`, `RETRY_BASE_S=0.1`, `RETRY_CAP_S=1.0`, jitter fijo en 0.

| Entre intentos | Espera programada (s) | Tiempo observado (s) |
|---|---|---|
| 1 → 2 | 0.099 | 0.110 |
| 2 → 3 | 0.199 | 0.204 |
| 3 → 4 | 0.399 | 0.405 |

Resultado final: `failed` tras 4 intentos.
