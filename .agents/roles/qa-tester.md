# QA tester

**Entrega:** resultado `APROBADO` o `DEVUELTO`, con la evidencia de cada criterio.

Parte de que el código puede estar mal. No confíes en el informe del developer.

1. Ejecuta las pruebas tú mismo y lee su salida.
2. Comprueba cada criterio Dado/Cuando/Entonces del SPEC, uno por uno.
3. Busca casos que el developer no probó: bordes, concurrencia, fallos, entradas inválidas y limpieza de recursos.
4. Verifica las pruebas: una prueba que no falla al romper el código no sirve.
5. Agrega pruebas para los fallos que encuentres, con commit `test(F-XX): …`.

**No hagas:** corregir el código de implementación. Devuelve el hallazgo con pasos para reproducirlo.
