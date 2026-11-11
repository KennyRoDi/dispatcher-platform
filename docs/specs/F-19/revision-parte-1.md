# Revisión F-19, parte 1

**Resultado: APROBADO para el alcance de la parte 1.** Revisión contra `origin/main` y el SPEC aprobado, sobre la rama `feat/F-19-1-estrategias-de-carga`, corte `f413c13`.

## Alcance y criterios

El diff implementa `LoadingConfig` en dominio con las dos estrategias y N entero positivo (sin aceptar `bool`), y `ModelLoader` en infraestructura mediante fábrica/runtime inyectados. La variante por proceso carga desde el callback del hijo; la variante compartida instancia antes de los inicios y pasa el modelo heredado a los hijos. Se pide `fork` explícito. Los errores al iniciar, cargar o inferir provocan intentos de terminación y recolección; los fallos de limpieza se conservan sin sustituir el error principal. Las pruebas cubren estos casos, igualdad de los resultados de los dobles y seis mutaciones.

La capa dominio permanece pura; infraestructura usa el contrato existente `Transcriber`. No hay cambios a puertos compartidos, llaves ni datos reales de terceros. El código de producto son 83 líneas, bajo el límite de 150 de la parte. Los commits revisados usan el formato `docs/feat/test(F-19): ...` requerido.

La parte 1 cumple el alcance aprobado. No acredita los criterios completos de ejecución real, igualdad con Whisper, compatibilidad nativa de fork/CoW, timeout/SIGTERM, PSS/RSS/cgroup ni comparación de memoria; el SPEC los asigna a las partes 2 y 3 y la ficha los mantiene pendientes. La suite general sigue bloqueada por `os.geteuid` en Windows; los fallos complementarios se reprodujeron en el baseline y las excepciones de implementación/verificación quedaron registradas con autorización humana.

## Hallazgos

Ninguno para el alcance de la parte 1. No se detectaron hallazgos que requieran aceptación humana ni desviaciones del SPEC.

## Evidencia revisada

QA-parte-1 registra 56 pruebas focales y de arquitectura aprobadas y seis de seis mutaciones detectadas. El orquestador las volvió a ejecutar y confirmó conformidad del repositorio sin problemas; el informe QA distingue expresamente los límites de los dobles y la suite general no verde. No se repitieron mediciones de SO porque no pertenecen a esta parte.
