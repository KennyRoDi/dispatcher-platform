# Resolución de conflictos con main

Se integró `origin/main` en la rama F-19 sin reescribir historial. Los cuatro
conflictos provenían de las mejoras de dataset F-03 y las correcciones Windows.

- Manifiesto: se conserva el rechazo de NUL de main y el rechazo de rutas con
  raíz/unidad POSIX o Windows de F-19.
- Generador pesado: conserva `checked_case_name` y `produce` compartido de main,
  además de rechazar componentes de ruta Windows antes de escribir.
- Pruebas: se retiran los xfail ya resueltos en main, conservando parámetros
  Windows y la omisión de chmod para Windows/root.
- Las pruebas nuevas de main que crean symlinks comprueban previamente la
  capacidad real y se omiten solo ante WinError 1314; otros errores se propagan.

La primera suite integrada dio 1689 passed y cuatro fallos por WinError 1314.
Tras añadir la comprobación de capacidad, los módulos afectados dieron
18 passed, 6 skipped, 3 xfailed. Conformidad: 0 problemas.

Suite final Windows: `python -m pytest -q -m "not integration and not acceptance"
--tb=short`: 1689 passed, 10 skipped, 8 deselected, 3 xfailed y una advertencia
en 188.15 s. Python 3.14, PYTHONUTF8=1, acceso normal a temporales Windows.
