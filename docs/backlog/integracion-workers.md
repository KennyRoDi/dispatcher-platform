# Área: integración de workers tipados

### US-43 · Integración de workers tipados (F-43) · P1 · H2
- **Responsable:** K · **Depende de:** F-01, F-05, F-06, F-07, F-08, F-09, F-11, F-13, F-14, F-22
Como operador, quiero que los casos multifuente se procesen de punta a punta por workers de texto, imagen y audio para cumplir el pipeline de B.4.
- **Dado** un caso con fuentes de texto, imagen, audio y video creado con `POST /cases` y `sources`
- **Cuando** corren los workers tipados sobre `queue:text`, `queue:image` y `queue:audio`
- **Entonces** cada sub-tarea se analiza, sus hallazgos quedan en el almacén sin duplicados, el caso cierra por barrier en `completed` o `partially_completed`, y el reporte consolidado sale con evidencias; un fallo transitorio se reintenta con espera, un worker caído devuelve su sub-tarea a la cola y un caso cancelado no se procesa
- **Pruebas:** U fábricas de analizador y de almacén, reencolado en formato `Subtask`, selección de parser. I `POST /cases` con `fakeredis` y dobles de modelo hasta el cierre, video con fotogramas, cancelación, reintento y muerte del worker. A reporte consolidado con almacén real.
- **Demuestra:** prueba I de extremo a extremo y el log de un caso completo. **Evidencia:** `docs/WORKER_CONTRACT.md` con el contrato del worker tipado y el reparto por `hostname` en `GET /workers`.
