---
name: cierre
description: "Abre la pull request apilada de una parte o feature cuyas seis fases están aprobadas. Usar con cierre."
---

# Cierre

1. Ejecuta `python scripts/flujo.py fase`. Si faltan aprobaciones, detente e informa.
2. Si la fase de revisión detectó errores de la IA aún sin registrar, publica otra entrada con `python scripts/flujo.py bitacora`, tras mostrársela a la persona.
3. Elige `--tipo` y `--resumen` según `CONTRIBUTING.md`: el título debe describir toda la PR.
4. Consulta el plan de pila del SPEC. Agrega `--final` solo si es la última parte. Ejecuta:

   ```bash
   python scripts/flujo.py cierre --tipo feat --resumen "descripcion en imperativo"
   ```

5. Si falla por tamaño, propón dividir la parte. Si falla por otra causa, corrígela. No omitas validaciones.
6. Informa la URL de la PR y su base. No fusiones: la PR la revisa y fusiona una persona, de abajo hacia arriba, con merge commit.
