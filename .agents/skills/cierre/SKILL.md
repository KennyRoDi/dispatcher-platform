---
name: cierre
description: "Abre la pull request apilada de una parte o feature cuyas seis fases están aprobadas. Usar con cierre."
---

# Cierre

1. Ejecuta `python scripts/flujo.py fase`. Si faltan aprobaciones, detente e informa.
2. Elige `--tipo` y `--resumen` según `CONTRIBUTING.md`: el título debe describir toda la PR.
3. Consulta el plan de pila del SPEC. Agrega `--final` solo si es la última parte. Ejecuta:

   ```bash
   python scripts/flujo.py cierre --tipo feat --resumen "descripcion en imperativo"
   ```

4. Si falla por tamaño, propón dividir la parte. Si falla por otra causa, corrígela. No omitas validaciones.
5. Informa la URL de la PR y su base. No fusiones: la PR la revisa y fusiona una persona, de abajo hacia arriba, con merge commit.
