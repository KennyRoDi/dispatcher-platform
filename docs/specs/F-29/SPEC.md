# SPEC F-29: Cadena de custodia

**Fase:** tests
**Base:** main
**Verificación IA:** plan a0ca31b
**Historia:** US-29 · **Requisitos:** RF-38, RF-39, RNF-08, QA-07 · **Responsable:** K

## Objetivo

Hoy el puerto `CustodyLog` solo tiene un doble que guarda tuplas en memoria: nada demuestra que una evidencia o el registro no se alteraron. El enunciado exige «cadena de custodia: hash al ingresar y en cada transformación, en log de solo-anexión encadenado por hash» y verificarla [B.5 M4]. Esta feature entrega ese log y un verificador que, ante una evidencia alterada, una entrada alterada o un log truncado, falla e indica la posición; sin alteraciones, pasa (RF-38, RF-39, QA-07). Un hash encadenado sin llave se puede recalcular entero y no detecta truncamiento (AD-17); por eso cada eslabón lleva un HMAC con una llave que no está en el repositorio (RNF-08) y el último eslabón se ancla aparte. La decisión se registra como AD-35 y SUP-31.

## Alcance

**Incluye:**
- `CustodyChain` (dominio): construcción de entradas selladas con HMAC-SHA-256 y verificación de la cadena, con la posición de la primera alteración.
- Adaptador `JsonlCustodyLog`: implementa el puerto `CustodyLog.record`; JSONL de solo-anexión (`O_APPEND`, `fsync`, `flock`) y archivo de ancla del último eslabón.
- Caso de uso `verify_custody`: cadena, ancla, linaje (toda transformación parte de una evidencia ingresada) y evidencia (SHA-256 recalculado de cada objeto contra el registrado), con `ObjectStore`.
- CLI `scripts/verify_custody.py` (código de salida distinto de 0 si hay alteración).
- Llave de custodia de 32 bytes fuera del repositorio, leída con `FileKeyProvider` de F-28 (sin duplicar su lectura).
- Registro de AD-35 y SUP-31 y borrador de la sección de custodia en `docs/modulo-M4-seguridad.md`.

**No incluye:**
- Llamar a `CustodyLog.record` desde la recepción (M3) y desde los workers: cada dueño cablea su punto (F-03/F-10 y F-07 a F-09). Aquí se entrega el puerto con adaptador y se documenta el punto de composición.
- El adaptador MinIO de `ObjectStore` (F-23, Melany): se prueba con `FakeObjectStore`.
- Reglas de reporte y alertas que consuman el resultado (F-14), rotación de la llave, firma asimétrica, sellado de tiempo de terceros, log distribuido entre nodos.
- La prueba A con manipulación real en la demo y la ficha M4 con datos medidos: quedan **pendiente** hasta ejecutarlas; no se inventa ninguna salida.

## Criterios de aceptación

Copiados de `docs/backlog/m4-seguridad.md`:

- **Dado** evidencias procesadas, con entrada de ingreso y de cada transformación
- **Cuando** se altera una evidencia, una entrada, o se trunca el log
- **Entonces** el verificador falla e indica la posición; sin alteraciones, pasa

Concretado:
1. Cada evidencia tiene una entrada `ingreso` y una por transformación; cada entrada incluye el sello del eslabón anterior (`prev_hash`) y el suyo (`entry_hash`) (RF-38).
2. Sin alteraciones, `verify` devuelve `ok` y exit 0 (también con el log vacío y con una sola entrada).
3. Alterar cualquier campo de una entrada (hash, operación, actor, fecha, `seq`) hace fallar `verify` y reporta la posición de esa entrada (número de línea, base 1) y el motivo.
4. Borrar, insertar, duplicar o reordenar líneas se detecta en la posición donde se rompe el enlace.
5. Truncar el final del log (quitar una o más entradas) se detecta por el ancla, con la posición esperada del último eslabón; quitar la entrada final y el ancla también se detecta como ancla ausente.
6. Recalcular toda la cadena con SHA-256 sin la llave no pasa la verificación: el HMAC no coincide en la primera entrada tocada.
7. Alterar el contenido de una evidencia en el almacén (su SHA-256 recalculado difiere del registrado) o borrarla hace fallar `verify` y reporta la posición de la entrada de ingreso o de transformación afectada y el hash esperado. Si falta la llave, `verify` falla cerrado (exit 2) y no declara la cadena válida.
8. Una transformación cuya evidencia de origen no fue ingresada ni es resultado de una entrada previa se reporta como violación de linaje en su posición.
9. La llave de custodia no está en el código ni en el historial; con permisos distintos de `0400`/`0600` o largo distinto de 32 bytes el adaptador falla cerrado.

## Diseño

**Contratos.** Implementa `CustodyLog` de `docs/CONTRATOS.md` (Kenni, F-29; consumen recepción y workers) con la firma ya publicada en `ports.record(evidence_sha256, operation, result_sha256, actor)`; no se cambia. Usa `ObjectStore.exists/open` (F-23) para releer evidencias, `Clock.now` para la fecha y `KeyProvider` de F-28 para la llave. El verificador no forma parte del puerto: es un caso de uso que lee el archivo.

**Capas y archivos** (`tests/unit/test_arquitectura.py` hace cumplir las dependencias):

| Capa | Archivo | Contenido |
|---|---|---|
| Dominio | `src/domain/custody_chain.py` | `CustodyEntry`, `seal(key, prev_hash, seq, fields) -> CustodyEntry`, `Anchor`, `verify_chain(lines, key, anchor) -> list[Violation]`, `Violation(position, kind, detail)`. Solo `hmac`, `hashlib` y `json`; sin E/S. |
| Aplicación | `src/application/verify_custody.py` | `verify_custody(log_lines, anchor, key_provider, store) -> VerificationReport`: cadena, ancla, linaje y evidencia. |
| Adaptador | `src/adapters/jsonl_custody_log.py` | `JsonlCustodyLog(path, key_provider, clock)`: implementa `CustodyLog.record`; lee el último eslabón al abrir; escribe el ancla de forma atómica. |
| Script | `scripts/verify_custody.py` | CLI: `PYTHONPATH=. python -m scripts.verify_custody --log ... --anchor ... [--store DIR]`. |
| Pruebas | `tests/dobles.py`, `tests/contratos.py` | `FakeCustodyLog` pasa a sellar igual; `comprobar_custody_log` lo cumplen el doble y `JsonlCustodyLog`. |

**Formato de la entrada (AD-35, provisional).** Una línea JSON con claves ordenadas y UTF-8 por entrada: `seq` (desde 0), `ts` (UTC, ISO 8601), `evidence_sha256`, `operation` (`ingreso` o el nombre de la transformación), `result_sha256` (igual a `evidence_sha256` en `ingreso`), `actor`, `prev_hash` y `entry_hash`. La primera entrada usa `prev_hash = "0" * 64`. `entry_hash = HMAC-SHA256(key, prev_hash ‖ JSON canónico de los demás campos)`, con el JSON canónico en claves ordenadas y sin espacios, para que no dependa del formato.

**Ancla del último eslabón.** Archivo `<log>.head` con `{"seq", "entry_hash", "mac"}` donde `mac = HMAC-SHA256(key, "head" ‖ seq ‖ entry_hash)`. Se reescribe (archivo temporal, `fsync`, `rename`, `fsync` del directorio) tras cada anexo y después del `fsync` del log. Si el proceso muere entre ambos pasos, el ancla queda una entrada atrás: el verificador lo acepta si la cadena es válida y avisa «ancla atrasada» sin fallar; si el ancla está por delante del log, es truncamiento.

**Verificador.** Recorre el log en orden. Para cada línea comprueba: JSON válido, `seq` consecutivo desde 0, `prev_hash` igual al `entry_hash` anterior y HMAC correcto. Se detiene en el primer eslabón roto: `position` es su número de línea (base 1), porque los eslabones siguientes ya no son confiables. Luego compara el último eslabón con el ancla (`mac` válido, mismo `seq` y `entry_hash`). Después comprueba el linaje (toda `operation` distinta de `ingreso` parte de un `evidence_sha256` ya ingresado o resultado de una entrada previa) y, por cada objeto, que `sha256(open(sha))` coincida con el registrado y que exista; esta parte se ejecuta sobre las entradas anteriores al eslabón roto y reporta todas las evidencias alteradas, cada una con la posición de su entrada. Cada hallazgo es `Violation(position, kind, detail)` con `kind` en `entrada`, `enlace`, `sello`, `truncado`, `ancla`, `linaje`, `evidencia`.

**Escritor único (AD-17).** El log lo escribe un solo proceso (el coordinador), con `O_APPEND`, `flock` y `fsync`. Workers y recepción envían sus registros al coordinador; ese cableado es de cada dueño y se documenta como límite. `JsonlCustodyLog` rechaza anexar si el último eslabón no verifica (`CustodyCorrupted`): no extiende una cadena ya alterada.

**Llave (AD-16 aplicada, sin duplicar).** `CUSTODY_KEY_FILE` apunta a 32 bytes aleatorios fuera del repositorio, `0400`, distinta de la KEK de F-28 (separación de llaves). Se lee con `FileKeyProvider(os.environ["CUSTODY_KEY_FILE"])` (el constructor de F-28 ya acepta una ruta); `kek()` devuelve aquí la llave de sello. No se reescribe su lectura, sus permisos ni su manejo de variables locales. Para desarrollo, `FakeKeyProvider`. Se añade `*.custody-key` al `.gitignore` si falta.

**Reutilización.** Del I Proyecto no se reutiliza nada. `hashlib` y `hmac` son de la biblioteca estándar; `sha256_de_archivo` (`src/adapters/hashing.py`) se reutiliza para el hash de los objetos en la CLI cuando el almacén es un directorio.

**Decisiones nuevas** (se registran en `docs/ARQUITECTURA.md` §8 y `docs/REQUERIMIENTOS.md` en la parte 1; AD-35 y SUP-31 se comprobaron libres en todas las ramas remotas: el mayor visto es AD-34 y SUP-30):
- **AD-35**, cadena de custodia con HMAC y ancla (precisa AD-17: `entry_hash` pasa de SHA-256 a HMAC-SHA-256 en cada eslabón, no solo en la cabeza). Alternativas: SHA-256 sin llave con cabeza sellada (AD-17 original); firma Ed25519 de la cabeza (el verificador no podría forjar, pero añade gestión de un par de llaves); árbol de Merkle; sellado de tiempo de terceros. Criterio: con la llave solo en el escritor y el verificador, recalcular la cadena exige la llave, y el ancla detecta truncamiento. Fuente: AD-17, R10, [B.5 M4].
- **SUP-31**, el enunciado no fija el algoritmo, el lugar de la llave ni el ancla. Se asume: HMAC-SHA-256, llave de 32 bytes por entorno en `CUSTODY_KEY_FILE`, ancla en un archivo junto al log y un solo escritor. Se declara que quien posea la llave puede forjar la cadena y que reponer un ancla antigua junto con un log truncado al mismo punto no se detecta mientras el ancla viva en el mismo disco.

## Pruebas

| Tipo | Prueba | Demuestra |
|---|---|---|
| Unitaria | `test_cada_entrada_enlaza_a_la_anterior` | `prev_hash` de cada entrada es el `entry_hash` previo; la primera usa el génesis |
| Unitaria | `test_cadena_sin_alteraciones_pasa` (vacía, una entrada, varias) | `verify` devuelve ok |
| Unitaria | `test_alterar_entrada_detecta_posicion` parametrizada por campo | La alteración se reporta en la línea correcta |
| Unitaria | `test_borrar_insertar_o_reordenar_detecta_posicion` | Rotura de enlace con su posición |
| Unitaria | `test_truncar_log_se_detecta` (una y varias entradas, y ancla borrada) | El ancla delata el truncamiento |
| Unitaria | `test_recalcular_cadena_sin_llave_no_pasa` | El HMAC impide la reescritura completa |
| Unitaria | `test_ancla_atrasada_no_falla_y_adelantada_si` | Tolerancia exacta a una caída entre log y ancla |
| Unitaria | `test_alterar_evidencia_se_detecta` y `test_evidencia_ausente_se_detecta` con `FakeObjectStore` | El SHA-256 recalculado difiere; posición de la entrada |
| Unitaria | `test_linaje_sin_ingreso_se_detecta` | Una transformación de evidencia no ingresada falla |
| Unitaria | `test_falla_cerrado_sin_llave` y `test_no_extiende_cadena_alterada` | Sin llave no hay veredicto; no se anexa sobre un log roto |
| Contrato | `comprobar_custody_log` sobre `FakeCustodyLog` y `JsonlCustodyLog` | Ambos cumplen el puerto |
| Integración (`integration`) | `test_log_en_disco_manipulado_falla` con archivos reales en `tmp_path` y reapertura del adaptador | Persistencia, `O_APPEND`/`fsync` y detección sobre archivos reales, sin servicios externos |
| Aceptación | CLI `scripts.verify_custody` antes y después de manipular un log y una evidencia sintéticos | Salida y exit code; la prueba A con manipulación en la demo queda pendiente |

## Mediciones

No aplica. F-29 aporta evidencia de ejecución a la ficha M4, no mediciones de SO M1–M5: la salida del verificador antes y después de manipular (backlog: «ficha M4: salida del verificador antes y después»). Se registra con el comando exacto en `docs/modulo-M4-seguridad.md`; la ficha y la prueba A quedan **pendiente** hasta ejecutarlas en la demo, y sin ellas el módulo M4 tiene máximo 2. El costo de HMAC por entrada no se mide aquí.

## Plan de pila

Cada PR hace una sola cosa y tiene hasta 400 líneas sin contar pruebas ni documentos.

| Parte | PR (título en Conventional Commits) | Contenido |
|---|---|---|
| 1 | `feat(F-29): cadena de custodia sellada con HMAC` | `src/domain/custody_chain.py` (`seal`, `verify_chain`, `Anchor`, `Violation`), registro de AD-35 y SUP-31. Aprox. 130 líneas. |
| 2 | `feat(F-29): registro de custodia JSONL de solo anexión` | `JsonlCustodyLog`, ancla atómica, `CustodyCorrupted`, `FakeCustodyLog` sellado, `comprobar_custody_log`, `.gitignore`. Depende de `KeyProvider` y `FileKeyProvider` de F-28 (parte 2). Aprox. 120 líneas. |
| 3 | `feat(F-29): verificador de custodia y CLI` | `verify_custody` (cadena, ancla, linaje, evidencia), `scripts/verify_custody.py`, borrador en `docs/modulo-M4-seguridad.md`. Aprox. 130 líneas. |

## Riesgos y preguntas abiertas

1. **Orden frente a F-28.** El backlog no declara dependencia, pero reutilizar `FileKeyProvider` exige que la parte 2 de F-28 esté en `main` (hoy en PR). ¿Se apila la parte 2 de F-29 sobre F-28, o se espera la fusión? La parte 1 no depende.
2. **Dónde vive el ancla.** En el mismo disco que el log, quien lo escribe puede reponer un ancla antigua y truncar a ese punto. ¿Se acepta el límite (SUP-31) o se copia el ancla a otro nodo en F-38?
3. **Llave simétrica.** Quien verifica puede forjar. ¿Se acepta HMAC, o se prefiere Ed25519 (verificador sin poder de forjar, más gestión)?
4. **Escritor único.** Workers en tres nodos deberían enviar sus registros al coordinador; hoy no hay endpoint. ¿Lo crea quien cablea el puerto (rutas de subtareas) o se anota como límite?
5. **Linaje.** ¿Se exige que toda transformación parta de una evidencia ingresada (criterio 8) o basta cadena, ancla y evidencia?
6. **Evidencia verificada.** Se recalcula el SHA-256 solo de los objetos registrados; un resultado intermedio que no se guardó se omite sin fallar. ¿Se acepta?
7. **Alcance de la demo.** ¿La prueba A manipula un log y una evidencia reales en los nodos de F-38, o en una ejecución local sintética?
8. **Distribución de la llave.** Solo el coordinador sella y el verificador lee: ¿la llave vive únicamente en el coordinador y en el equipo de quien verifica, sin copiarla a los workers?

## Aprobaciones

Las registra `scripts/flujo.py`. No editar.

| Fase | Aprobó | Fecha | Excepción o motivo |
|---|---|---|---|
| verificación IA de plan | Claude Code (orquestador Sonnet 5.5; subagente arquitecto general-purpose) | 2026-11-10 | SPEC F-29 sin campos pendientes (grep 0); diff contra main solo el SPEC. AD-35 y SUP-31 libres segun arquitecto (no re-verifique; el log previo dice max AD-34/SUP-30). Diseño (HMAC por eslabon, ancla con MAC, llave distinta de la KEK) es propuesta del arquitecto. 8 preguntas abiertas; decision provisional: aceptar, parte 1 sin dependencias, parte 2 apilada sobre la rama de F-28 (FileKeyProvider) solo cuando llegue. (a0ca31b) |
| plan | Kenni Rodriguez | 2026-11-10 | aprobación delegada |
