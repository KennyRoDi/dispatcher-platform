# Compatibilidad de cierre en Windows

Se corrigió la colección de la prueba POSIX de permisos: se omite en Windows,
donde chmod no garantiza retirar la lectura, y se conserva la omisión para root.
La validación de manifiestos ahora rechaza rutas con raíz o unidad tanto POSIX
como Windows. El generador pesado rechaza nombres de caso que no sean un único
componente antes de crear archivos; las dos expectativas de fallo sobre nombres
maliciosos pasan a pruebas normales.

En Windows con Python 3.14, PYTHONUTF8=1 y acceso normal a los temporales:

- `python -m pytest -q -m "not integration and not acceptance" --tb=short`:
  1624 passed, 5 skipped, 8 deselected, 19 xfailed, 1 warning en 146.36 s.
- Después de ampliar los parámetros de rutas Windows, los tres tests dirigidos
  de rechazo de rutas/nombres produjeron 8 passed en 2.13 s.
- `python -m scripts.conformidad repo`: 0 problemas.

Esto resuelve los bloqueos locales antes documentados, sin acreditar procesos
reales, Whisper tras fork ni mediciones de memoria. Los errores de temporales
de la ejecución en sandbox no se contaron como fallos del producto.
