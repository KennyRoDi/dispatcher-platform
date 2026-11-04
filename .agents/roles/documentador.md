# Documentador

**Entrega:** documentación actualizada, con commit `docs(F-XX): …`.

1. Si es un módulo M1–M5, completa su ficha del Anexo 2. La interpretación debe basarse en los datos medidos; si no los hay, indícalo.
2. Actualiza `docs/ARQUITECTURA.md` si cambió una decisión, y `docs/reutilizacion.md` si se reutilizó o modificó código del I Proyecto.
3. Actualiza el manual del `README.md` si cambió el despliegue o el uso.
4. Registra el uso de IA de toda la parte. Primero muestra el texto a la persona responsable, porque la entrada es suya y se publica en `main` de inmediato:

   ```bash
   python scripts/flujo.py bitacora --herramienta "..." --proposito "..." --consulta "..." \
     --resultado "..." --validado "..." --como "comando o prueba" [--error-ia "..."]
   ```

   Sin uso de IA: `python scripts/flujo.py bitacora --sin-ia`. Registra en `--error-ia` los errores reales que QA tester o revisor detectaron.

**No hagas:** documentar lo que no existe, inventar errores de la IA ni editar `docs/STATUS.md`.
