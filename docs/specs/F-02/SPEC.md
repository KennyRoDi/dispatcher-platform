# SPEC F-02: Validar y normalizar

**Fase:** plan
**Base:** main
**Verificación IA:** pendiente
**Historia:** US-02 · **Requisitos:** RF-02 (exportaciones de chat), RNF-06 (normalización) · **Responsable:** N

## Objetivo

El puerto `ConversationParser` (`src/application/ports.py`) y `TextAnalyzer` (F-07, `src/adapters/text_analyzer.py`) ya existen, pero **ningún adaptador real lo implementa todavía** — solo `FakeConversationParser` (`tests/dobles.py`), usado en pruebas. F-01 clasifica un archivo `.txt`/`.json` como fuente `TEXT` por extensión (`classify_source`), pero no valida que su *contenido* sea realmente una exportación de WhatsApp o Telegram bien formada: un `.txt` cualquiera pasaría la clasificación y fallaría silenciosamente, o con un error confuso, más adelante.

F-02 entrega los dos adaptadores concretos que el análisis de texto necesita para funcionar con datos reales: `WhatsAppParser` y `TelegramParser`, que convierten el archivo crudo en `ChatMessage` (hora UTC, remitente, texto UTF-8) y rechazan con un error explícito cualquier archivo que no cumpla el formato esperado.

**Formato verificado en el código** (reutilizado del generador sintético de F-03, `src/adapters/chat_export_generator.py`, que es la fuente de verdad de cómo se ven las exportaciones de este dataset):
- WhatsApp (`.txt`): una línea por mensaje, `D/M/AA, HH:MM - Remitente: Texto` (día y mes sin cero inicial, año de 2 dígitos); una línea que no empieza con esa cabecera es continuación del mensaje anterior (mensajes multilínea).
- Telegram (`.json`): `{"name", "type", "messages": [{"id", "type": "message", "date": "AAAA-MM-DDTHH:MM:SS", "date_unixtime", "from", "text"}, ...]}` (formato real de exportación de Telegram Desktop).

## Alcance

**Incluye:**
- `src/adapters/whatsapp_parser.py`: `WhatsAppParser` implementa `ConversationParser.parse(path) -> Iterable[ChatMessage]`; agrupa líneas de continuación al mensaje anterior; rechaza con `FormatoDeChatInvalido` si ninguna línea coincide con la cabecera esperada o si el archivo no es UTF-8 válido.
- `src/adapters/telegram_parser.py`: `TelegramParser` implementa el mismo puerto sobre el JSON de Telegram; rechaza con `FormatoDeChatInvalido` si falta la clave `messages`, si el JSON es inválido, o si un mensaje no trae `date`/`from`/`text`.
- `src/domain/chat_export.py` (o donde corresponda): excepción compartida `FormatoDeChatInvalido(path, motivo)`.
- Normalización: timestamps sin huso horario explícito (ambos formatos) se interpretan como UTC — ver decisión **AD-48** y **SUP-44**.

**No incluye:**
- Clasificación por extensión general (ya la hace `classify_source`, F-05, usada por F-01).
- Conectar estos parsers a `POST /cases` o a un worker en ejecución: `TextAnalyzer` (F-07) ya acepta un `ConversationParser` inyectado (`TextAnalyzer.from_config(parser, ...)`); cablear cuál parser real usa en producción es configuración de despliegue, no de esta feature.
- Nuevos formatos de exportación (solo WhatsApp y Telegram, los que pide la historia).
- Análisis del contenido (palabras clave, sentimiento, amenazas): eso ya lo hace F-07 sobre los `ChatMessage` que este parser produce.

## Criterios de aceptación

Copiado de `docs/backlog/recepcion-dataset.md` (US-02):

**Dado** una exportación de WhatsApp o Telegram y un archivo no admitido
**Cuando** se reciben
**Entonces** la exportación produce mensajes con timestamp UTC, remitente y UTF-8, y el archivo se rechaza con error explícito

**Pruebas:** U parsers y validador. I subida por API. A todas las conversaciones del dataset se analizan sin errores.
**Demuestra:** prueba A. **Evidencia:** conteo de mensajes válidos frente a rechazados.

## Diseño

**Contratos usados (sin modificar):**
- `ConversationParser` (`src/application/ports.py`): puerto que ambos adaptadores implementan
- `ChatMessage` (`src/domain/chat_message.py`): ya exige `timestamp_utc` con huso horario (`__post_init__`); los parsers construyen instancias válidas o no las construyen

**Archivos a crear** (todos de Nahúm, M2/recepción):
- `src/domain/chat_export.py` (nuevo): `FormatoDeChatInvalido`
- `src/adapters/whatsapp_parser.py` (nuevo): `WhatsAppParser`
- `src/adapters/telegram_parser.py` (nuevo): `TelegramParser`
- `tests/unit/test_whatsapp_parser.py`, `tests/unit/test_telegram_parser.py` (nuevos)
- `tests/integration/test_parsers_con_archivo_subido.py` (nuevo)
- `tests/acceptance/test_dataset_se_analiza_sin_errores.py` (nuevo)

**Decisión nueva propuesta (AD-48, se registra en `docs/ARQUITECTURA.md` §8 en la fase de documentación):**
- Un timestamp sin huso horario explícito (WhatsApp: `D/M/AA, HH:MM`; Telegram: `date` sin offset) se interpreta directamente como UTC, sin conversión. Alternativa rechazada: asumir hora local del servidor y convertir — se descarta porque no hay forma confiable de saber en qué huso se generó una exportación real, y el dataset sintético de F-03 ya escribe esas cadenas en UTC (`chat_export_generator.py:_whatsapp_entry`/`_telegram_entry`, ambos con `.astimezone(timezone.utc)` antes de formatear). Se declara como **SUP-44**: exportaciones reales en otro huso horario deben convertirse antes de ingresar al sistema; no hay dato en el archivo que permita detectarlo automáticamente.

**Reutilización del I Proyecto:**
- Ninguna; el formato se reconstruye a partir del propio generador de F-03 (sintético, no es reutilización del I Proyecto)

## Pruebas

| Tipo | Prueba | Archivo | Demuestra |
|---|---|---|---|
| Unitaria | `test_whatsapp_parser_produce_mensajes_utc_utf8` | `tests/unit/test_whatsapp_parser.py` | Un `.txt` válido produce `ChatMessage` con `timestamp_utc` con huso, remitente y texto UTF-8; mensajes multilínea se agrupan en uno solo |
| Unitaria | `test_whatsapp_parser_rechaza_formato_no_reconocido` | `tests/unit/test_whatsapp_parser.py` | Un archivo sin ninguna línea con la cabecera esperada lanza `FormatoDeChatInvalido` |
| Unitaria | `test_whatsapp_parser_rechaza_bytes_no_utf8` | `tests/unit/test_whatsapp_parser.py` | Un archivo con bytes inválidos en UTF-8 lanza `FormatoDeChatInvalido`, no se adivina otro encoding |
| Unitaria | `test_telegram_parser_produce_mensajes_utc_utf8` | `tests/unit/test_telegram_parser.py` | Un `.json` válido (formato Telegram Desktop) produce los mismos `ChatMessage` correctos |
| Unitaria | `test_telegram_parser_rechaza_json_sin_messages` | `tests/unit/test_telegram_parser.py` | JSON válido pero sin la clave `messages`, o JSON inválido, lanza `FormatoDeChatInvalido` |
| Integración | `test_parsers_leen_archivo_subido_por_chunks` | `tests/integration/test_parsers_con_archivo_subido.py` | Un archivo WhatsApp subido por el flujo real de `POST /uploads` (F-22) se recupera del almacén y se parsea correctamente |
| Aceptación | `test_dataset_se_analiza_sin_errores` | `tests/acceptance/test_dataset_se_analiza_sin_errores.py` | Generando varias conversaciones con el generador sintético de F-03 (WhatsApp y Telegram), todas se parsean sin excepción; se cuentan mensajes válidos (evidencia) |

## Mediciones

No aplica: F-02 es lógica de parseo (dominio/adaptador), no hay medición de SO prevista para M2 fuera de F-20/F-21.

## Plan de pila

Cada PR hace una sola cosa y tiene hasta 400 líneas sin contar pruebas ni documentos.

| Parte | PR (título en Conventional Commits) | Contenido | Líneas aprox |
|---|---|---|---|
| 1 | `feat(F-02): parsers de WhatsApp y Telegram con validacion y normalizacion UTC` | `chat_export.py`, `whatsapp_parser.py`, `telegram_parser.py`, AD-48 | ~160 |

## Riesgos y preguntas abiertas

1. **Huso horario de exportaciones reales.** Declarado en AD-48/SUP-44: se asume UTC si no hay offset. Si el equipo usa exportaciones reales en otro huso, hay que convertir antes de ingerir (fuera de esta feature).
2. **No se conecta a producción todavía.** Igual que F-05/F-06 con `POST /cases`, estos parsers quedan listos para que `TextAnalyzer` los use, pero cablear cuál usa el worker de texto en runtime es una decisión de despliegue/configuración, no de esta feature.
3. **Formato de Telegram simplificado.** Telegram Desktop real incluye más campos (`from_id`, `text_entities`, mensajes de servicio sin `from`/`text`); el parser solo exige `date`, `from` y `text`, e ignora el resto. Mensajes de servicio (`type != "message"`) se omiten, no se rechazan.

## Aprobaciones

Las registra `scripts/flujo.py`. No editar.

| Fase | Aprobó | Fecha | Excepción o motivo |
|---|---|---|---|
