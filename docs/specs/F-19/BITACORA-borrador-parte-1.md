# Borrador de bitácora F-19, parte 1

Pendiente de aprobación humana de documentación y de publicación por el orquestador con `flujo.py bitacora`. No sustituye la entrada de `docs/BITACORA_IA.md` en la rama `estado`. Fecha de publicación e integrante los deriva el script de la fecha real y de la identidad del clon.

| Campo / argumento | Borrador |
|---|---|
| Fecha · integrante | Trabajo realizado el 2026-11-10 por José Andrés Loría Herrera; comprobar fecha real al publicar |
| Componente / `--componente` | F-19 · M1 · parte 1 |
| Rama | feat/F-19-1-estrategias-de-carga |
| Herramienta / `--herramienta` | Codex, con subagentes de arquitecto, developer, QA y documentador, y verificación independiente del orquestador |
| Propósito / `--proposito` | Diseñar y construir la selección de estrategia y el protocolo de carga de modelos con operaciones inyectadas, sin acreditar procesos ni memoria reales |
| Consulta resumida / `--consulta` | Trabajar F-19 según US-19/RF-27 y el ciclo aprobado: plan, pruebas en rojo, implementación, QA y documentación de la parte 1 |
| Resultado obtenido / `--resultado` | SPEC en tres partes; LoadingConfig y ModelLoader (83 líneas de producto), 46 pruebas inicialmente rojas por implementación ausente; 6 casos QA adicionales. QA registró 56 pruebas aprobadas incluyendo arquitectura y 6/6 mutaciones detectadas. Ficha M1 actualizada con mediciones pendientes |
| Validado / corregido / descartado / `--validado` | Se aceptaron selección pura, carga por hijo o precarga y recolección con runtime inyectado. Se corrigió la colisión de SUP-24 usando SUP-25. No se atribuyeron a estos dobles resultados de Whisper real, CoW, señales, ausencia real de zombies ni PSS/RSS. Suite general no declarada verde; fallos previos documentados y excepciones de implementación y verificación autorizadas |
| Cómo se validó / `--como` | Lectura del diff contra SPEC, US-19 y RF-27; pytest focal con test_model_loading.py, test_model_loader.py, test_model_loader_qa.py y test_arquitectura.py: 56 passed; python docs/specs/F-19/mutaciones_parte1.py: 6/6; python -m scripts.conformidad repo: 0 problemas; git diff --check. Evidencia y límites en docs/specs/F-19/QA-parte-1.md. La suite general bloquea colección por os.geteuid en Windows; los dos fallos complementarios se reprodujeron sobre 887f2c7 |
| Error real de IA / `--error-ia` | El borrador de plan asignó SUP-24 al alcance de F-19, pero ese identificador ya se usaba para la reserva de F-16. El orquestador detectó la colisión al cotejar la ficha M1; el arquitecto corrigió la propuesta a SUP-25 antes de publicar el plan. No se cambió el supuesto de reserva |

La entrada resume esta parte; no afirma un número exacto de consultas ni que se haya completado la revisión de fase 6. No se inventaron errores de producto: QA no encontró nuevos fallos de implementación. La colisión documental es el error real detectado y corregido.

No se actualizó `docs/reutilizacion.md`: no existe en esta base y esta parte agrega protocolo nuevo, sin modificar ni reutilizar código del I Proyecto. Se consume el puerto `Transcriber` de F-09. El README no cambia: no se agregó comando, despliegue ni uso productivo; el futuro CLI de medición todavía no existe.
