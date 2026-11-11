# SPEC F-27: TLS entre nodos

**Fase:** tests
**Base:** feat/F-27-1-tls-entre-nodos
**Verificación IA:** revision 6bd4d8a
**Historia:** US-27 · **Requisitos:** RF-36 (cifrado en tránsito); [B.5 M4], [B.7 Seguridad] · **Responsable:** K

## Objetivo

Hoy workers, coordinador, Redis y MinIO hablan en claro (`http://`, `redis://` sin TLS, `MINIO_SECURE=false`). Quien capture tráfico en la red entre nodos lee los mensajes, las credenciales de Redis y MinIO y, cuando exista F-26, los JWT. El enunciado exige TLS entre nodos y como evidencia «una captura entre nodos que muestre TLS y no contenga contenido en claro» [B.5 M4]; RF-36 lo repite. **Tailscale no sustituye a TLS** (`docs/ARQUITECTURA.md` §6): la captura se toma en la interfaz y debe mostrar el handshake.

F-27 cifra y autentica al servidor en las tres conexiones entre nodos (workers y reaper a la API, a Redis y a MinIO) con una CA privada del equipo, y hace que un cliente que no tenga la CA, o que se conecte en claro, sea rechazado.

## Alcance

**Incluye:**
- Script `deploy/tls/generar_certs.sh` (`openssl`) que crea la CA privada y un certificado del Nodo A con SAN de IP de Tailscale y nombres DNS, en un directorio **fuera del repo** (`CERTS_DIR`, por defecto `$HOME/.ms-certs`).
- `src/infrastructure/tls.py`: `TlsSettings.from_env` (`TLS_ENABLED`, `TLS_CA_FILE`) y contexto TLS de cliente: TLS 1.3 como mínimo, `CERT_REQUIRED`, verificación de hostname.
- Cableado de los clientes: `requests` (reporter, reaper, scripts), `redis-py` (workers, reaper, coordinador) y `minio` (workers, coordinador).
- Rechazo de comunicación en claro: con TLS habilitado, un cliente se niega a arrancar con `http://`, Redis sin TLS o `MINIO_SECURE=false`.
- Servidores con TLS en Compose del Nodo A: uvicorn (API en 8443), Redis (solo `--tls-port 6380`, puerto en claro cerrado) y MinIO (9000 con certificado). Healthchecks y reaper por `https`.
- `.gitignore`, `.env.example` y guía de despliegue con la distribución de `ca.pem`.
- Pruebas con certificados efímeros generados en la prueba, y borrador de la sección TLS de `docs/modulo-M4-seguridad.md` con comandos y resultados «pendiente».

**No incluye:**
- mTLS (certificado de cliente por worker): ver AD-37 y pregunta 2. La identidad del worker ante la API la da el JWT con rol `servicio` de F-26; ante Redis y MinIO, sus credenciales.
- Rotación o revocación de certificados, OCSP, CA intermedia, HSM.
- TLS del dashboard de Streamlit (de Melany) y del puerto de consola de MinIO (9001): el dashboard solo es cliente y usa `REQUESTS_CA_BUNDLE`; la consola no se publica.
- Autenticación y roles (F-26), cifrado en reposo (F-28), cadena de custodia (F-29), endurecimiento sin privilegios (F-30).
- Ejecutar la prueba real entre nodos y la captura: son de la persona (partes 3 y 4); sin ejecutarlas no se escribe ningún resultado.

## Criterios de aceptación

Copiados de `docs/backlog/m4-seguridad.md`:

- **Dado** el sistema procesando un mensaje con un marcador sintético
- **Cuando** se captura el tráfico entre nodos
- **Entonces** hay handshake TLS y el marcador no aparece en la captura; un cliente sin la CA es rechazado

Concretado:
1. Un cliente configurado con `ca.pem` completa el handshake con la API (8443), Redis (6380) y MinIO (9000) y negocia TLS 1.3.
2. Un cliente sin la CA (almacén del sistema) falla con error de verificación del certificado, no con un aviso ignorado.
3. Un certificado válido de la CA pero con SAN que no incluye el host al que se conecta se rechaza (verificación de hostname).
4. Una conexión en claro a Redis (puerto 6379 o `redis://`) falla; la API en claro no responde en 8443; con TLS habilitado los clientes no arrancan con `http://` ni `MINIO_SECURE=false`.
5. `tshark -r m4.pcap -Y tls.handshake.type==1` muestra handshakes y `strings m4.pcap | grep -c <marcador>` da 0 (evidencia de la persona; pendiente).
6. Ninguna llave privada ni certificado de demo está en el repo ni en el historial.

## Diseño

**Contratos.** No implementa ni cambia ningún contrato de `docs/CONTRATOS.md`: TLS es configuración de conexión, no un puerto nuevo. `deploy/` y la configuración de infraestructura son de Kenni («Quién toca qué»). Toca archivos compartidos con cambios aditivos y aviso: `src/workers/config.py`, `reporter.py` y `storage.py` (José Andrés) y `src/coordinator/conexion.py` (compartido con Nahúm); `dashboard/` **no** se edita.

**Capas y archivos** (`tests/unit/test_arquitectura.py` hace cumplir las dependencias):

| Capa | Archivo | Contenido |
|---|---|---|
| Infraestructura | `src/infrastructure/tls.py` | `TlsSettings` (`enabled`, `ca_file`); `from_env` falla si `TLS_ENABLED` y falta `TLS_CA_FILE` o no existe; `client_context(settings)` con `ssl.create_default_context(cafile=...)`, `minimum_version=TLSv1_3`, `check_hostname=True`; `redis_kwargs`, `requests_session`, `minio_http_client`; `exigir_cifrado(coordinator_url, minio_secure, ...)` que lanza `ValueError` ante transporte en claro. Sin importar nada de `src/workers` ni de `src/coordinator`. |
| Infraestructura | `src/workers/config.py` (`make_redis`), `reporter.py`, `storage.py`, `src/coordinator/conexion.py` | Reciben los argumentos de `tls.py`; sin TLS el comportamiento actual no cambia. |
| Scripts | `scripts/check_connectivity.py`, `run_load.py`, `submit_case.py`, `reaper.py` | Usan `requests_session` o la variable estándar `REQUESTS_CA_BUNDLE`. |
| Despliegue | `deploy/tls/generar_certs.sh`, `docker-compose.yml` (Nodo A), `deploy/docker-compose.worker.yml`, `.env.example`, `.gitignore` | Certificados fuera del repo, montados de solo lectura; `TLS_CA_FILE` en los workers. |

**Servidores.** uvicorn: `--ssl-keyfile`, `--ssl-certfile` (https://www.uvicorn.org/deployment/#running-with-https). Redis: `--port 0 --tls-port 6380 --tls-cert-file --tls-key-file --tls-ca-cert-file --tls-auth-clients no --tls-protocols TLSv1.3` (https://redis.io/docs/latest/operate/oss_and_stack/management/security/encryption/). MinIO: certificados en el directorio de certificados (`--certs-dir`), `public.crt` y `private.key` (https://min.io/docs/minio/linux/operations/network-encryption.html). Que las imágenes elegidas traigan TLS compilado y acepten esos parámetros **no está comprobado**: se verifica con la prueba I de la parte 3.

**Certificados.** Un certificado por nodo servidor (AD-15): solo el Nodo A sirve, así que hay una CA y un certificado, con SAN `IP:<NODE_IP de Tailscale>`, `DNS:<hostname del nodo>` y los nombres de servicio de Compose (`redis`, `minio`, `coordinator`) para el tráfico interno de contenedores. Clave EC P-256, CA válida 365 días y certificado 90 días (SUP-33). La llave de la CA se queda en la máquina que la generó; a los workers solo viaja `ca.pem` (pública), por copia manual, nunca por Git.

**Decisiones nuevas** (se registran en `docs/ARQUITECTURA.md` §8 en la parte 1; números comprobados libres en todas las ramas remotas: el mayor visto es AD-36 y SUP-32):

- **AD-37 (provisional):** TLS de servidor con verificación de CA y de hostname en el cliente, en API (8443), Redis (6380) y MinIO (9000); sin mTLS por ahora. Alternativas:
  - *mTLS en todo.* Autentica al nodo en el transporte, pero MinIO no valida certificados de cliente en la API S3, exige un certificado por worker en tres Windows y duplica la identidad que ya da el JWT `servicio` (F-26).
  - *mTLS solo en API y Redis.* Añade identidad de nodo a costa de emitir, repartir y renovar tres certificados de cliente; es el endurecimiento natural si el tiempo alcanza (pregunta 2).
  - *Solo TLS sin verificar el certificado.* Cifra, pero cualquiera puede suplantar al servidor: rechazado.
  - *WireGuard o Tailscale como único cifrado.* Ya descartado en AD-15: la captura debe mostrar TLS.
  - Criterio: cubrir RF-36 y el criterio «un cliente sin la CA es rechazado», con el mínimo de material de llaves por distribuir. Fuente: RFC 8446 (R8); verificación de identidad del servidor, RFC 6125 y RFC 9525; [B.7 Seguridad]. Medición pendiente: costo de TLS sobre el throughput de M3 (ficha M3).
- **Qué cubre TLS y qué JWT (F-26).** JWT dice *quién llama y qué puede hacer*; no protege el canal, y sin TLS el token viaja en claro y puede reutilizarse. TLS dice *que el servidor es el nuestro y que nadie lee ni altera el tráfico*; no dice quién es el cliente. Redis y MinIO no entienden JWT: su protección es TLS más credencial. Con mTLS se cubriría además la identidad del worker en el transporte, que hoy cubre el JWT en la API.
- **SUP-33 (provisional):** parámetros de demo: CA de 365 días, certificado de 90 días, EC P-256, puerto de API 8443 (el de `docs/IMPLEMENTACION.md` §5), Redis 6380 con el 6379 cerrado, `TLS_ENABLED` activo por defecto (seguro por defecto, como `AUTH_ENABLED`) y `TLS_ENABLED=false` explícito, con aviso en el registro, solo en `deploy/docker-compose.local.yml`. El enunciado no fija ninguno.

**Reutilización.** Del I Proyecto, nada. Terceros citados en el código y en `docs/modulo-M4-seguridad.md` [Parte I §9]: módulo `ssl` de Python, `openssl`, `redis-py`, `minio-py`, `requests` y `trustme` (solo pruebas, MIT o Apache-2.0).

**Dependencia nueva (solo desarrollo):** `trustme==1.2.1` en `requirements-dev.txt`, versión más reciente según `pip index versions trustme`; requiere `cryptography>=3.1` e `idna` (metadatos de la rueda). `cryptography==50.0.2` ya está instalada en el entorno y la rama de F-28 la fija en `requirements.txt`; esta rama no la fija. Alternativa sin dependencia: llamar a `openssl` por `subprocess` y marcar las pruebas `integration` (más lento, depende del binario). La producción no añade dependencias: `ssl`, `requests`, `redis` y `minio` ya están.

## Pruebas

Las unitarias no usan red ni reloj; los certificados efímeros se generan en `tmp_path` con `trustme` dentro de la prueba y no se versiona ninguno. Las pruebas I con sockets locales (`127.0.0.1`, puerto efímero) y con servicios reales se marcan `integration`.

| Tipo | Prueba | Demuestra |
|---|---|---|
| Unitaria | `test_tls_settings_desde_entorno` (parametrizada: activo, apagado, valores `0/false/no/off`) | Parseo de `TLS_ENABLED` y `TLS_CA_FILE` |
| Unitaria | `test_tls_activo_sin_ca_falla`, `test_ca_inexistente_falla`, `test_ca_vacia_o_corrupta_falla` | Falla cerrado: sin CA no arranca |
| Unitaria | `test_contexto_exige_tls13_cert_requerido_y_hostname` | `minimum_version`, `verify_mode` y `check_hostname` del contexto |
| Unitaria | `test_exigir_cifrado_rechaza_http_redis_plano_y_minio_inseguro` (parametrizada) | Comunicación en claro rechazada con TLS activo |
| Unitaria | `test_kwargs_de_redis_requests_y_minio_con_tls` | Cada cliente recibe CA, hostname y TLS 1.3 |
| Unitaria | `test_sin_tls_el_comportamiento_no_cambia` | Con `TLS_ENABLED=false` los clientes quedan como hoy |
| Unitaria | `test_repo_sin_llaves_ni_certificados` (recorre `git ls-files`) y `test_gitignore_cubre_certs` | Criterio 6: sin `BEGIN ... PRIVATE KEY` rastreado |
| Unitaria | `test_script_de_certificados_escribe_fuera_del_repo` (lee `generar_certs.sh`, sin ejecutarlo) | El directorio por defecto no está bajo el repo |
| Integración | `test_cliente_con_ca_completa_el_handshake_tls13` (servidor `ssl` local) | Criterio 1 |
| Integración | `test_cliente_sin_la_ca_es_rechazado` | Criterio 2: `SSLCertVerificationError` |
| Integración | `test_hostname_distinto_al_san_es_rechazado` | Criterio 3 |
| Integración | `test_cliente_tls12_es_rechazado_por_el_contexto` y `test_cliente_en_claro_contra_servidor_tls_falla` | Mínimo TLS 1.3; sin fallback a claro |
| Integración | `test_requests_contra_https_local_verifica_la_ca` | El cableado de `requests` verifica de verdad |
| Integración | `test_redis_tls_real_rechaza_conexion_en_claro_y_cliente_sin_ca` y `test_minio_tls_real_con_ca` (Docker; se omiten sin Docker) | Criterio 4 sobre los servicios reales; **pendiente** de ejecutar |
| Aceptación | `tests/acceptance/test_tls_entre_nodos.py`: levanta los nodos, procesa un caso con marcador, captura con `tcpdump` y revisa con `tshark` y `strings` | Criterio 5; **pendiente**, la ejecuta la persona con `sudo` |

## Mediciones

M4, TLS (F-27). Comandos exactos de `docs/IMPLEMENTACION.md` §5; ejecuta la persona en el Nodo A con `sudo`, una captura por intento y la IP real de Tailscale:

```bash
sudo tcpdump -i <if> -w m4.pcap 'port 8443 or 6380 or 9000'
tshark -r m4.pcap -Y tls.handshake.type==1
strings m4.pcap | grep -c <marcador_sintetico>
```

Producto esperado: handshakes TLS y 0 coincidencias del marcador. Va en `docs/modulo-M4-seguridad.md` con la captura (`m4.pcap` fuera del repo, solo el resumen de `tshark`); mientras no se ejecute, la ficha dice «pendiente» y no lleva salida. Las mediciones de M1 a M3 se repiten, al menos el throughput de M3, si TLS altera sus resultados, y la diferencia se reporta (`docs/IMPLEMENTACION.md` §7). No se estima el costo de TLS en este SPEC.

## Plan de pila

Cada PR hace una sola cosa y tiene hasta 400 líneas sin contar pruebas ni documentos. Estimaciones, no medidas.

| Parte | PR (título en Conventional Commits) | Contenido |
|---|---|---|
| 1 | `feat(F-27): configuración y contexto TLS de cliente` | `src/infrastructure/tls.py` (`TlsSettings`, contexto, `exigir_cifrado`, constructores de argumentos), `trustme` en `requirements-dev.txt`, registro de AD-37 y SUP-33 en `docs/ARQUITECTURA.md` y `docs/REQUERIMIENTOS.md`. Aprox. 110 líneas; pruebas unitarias y de integración con sockets locales. |
| 2 | `feat(F-27): cablear TLS en workers, coordinador y scripts` | `make_redis`, `reporter.py`, `storage.py`, `conexion.py`, reaper y scripts usan `tls.py`; rechazo de claro al arrancar; sin cambio de comportamiento con TLS apagado. Aprox. 120 líneas. Avisar a José Andrés y Nahúm antes de abrirla. |
| 3 | `feat(F-27): servidores con TLS y certificados de demo en Compose` | `deploy/tls/generar_certs.sh`, Compose del Nodo A y de worker con TLS (API 8443, Redis 6380, MinIO 9000), healthchecks, `.gitignore`, `.env.example`, pruebas I con Redis y MinIO reales. Sin código en `src/` (script de aprox. 60 líneas). Fusionar sin coordinar con José y Melany rompería los workers: ver pregunta 1. |
| 4 | `docs(F-27): ficha M4 de TLS y guion de captura` | Sección TLS de `docs/modulo-M4-seguridad.md` y de `docs/DEPLOY_WORKERS.md`, aceptación `test_tls_entre_nodos.py`; resultados «pendiente» hasta que la persona capture. 0 líneas de código. |

## Riesgos y preguntas abiertas

1. **Activación y compañeros.** Con TLS activo por defecto, los workers de José, el coordinador de Nahúm y el dashboard de Melany fallan hasta recibir `ca.pem` y URLs `https`. Propuesta: `TLS_ENABLED` activo por defecto y fusionar la parte 3 solo tras coordinar, como F-26. El dashboard funciona sin editar `dashboard/` si exporta `REQUESTS_CA_BUNDLE`. ¿Se acepta?
2. **mTLS.** Esta propuesta no emite certificados de cliente (AD-37). ¿Se añade mTLS en API y Redis como endurecimiento si sobra tiempo, o se deja como mejora declarada?
3. **Puertos.** La API pasa de 8000 a 8443 y Redis de 6379 a 6380 con el puerto en claro cerrado; cambia `COORDINATOR_URL` y `REDIS_PORT` en `.env`. Coincide con los comandos de `docs/IMPLEMENTACION.md` y el diagrama de `docs/ARQUITECTURA.md`.
4. **TLS 1.3 mínimo.** El contexto de los clientes y Redis lo exigen. uvicorn no expone versión mínima por línea de comandos ni MinIO por parámetro, así que servidor API y MinIO podrían aceptar TLS 1.2 de un cliente ajeno. Alternativa: un lanzador propio del coordinador (más código). ¿Se acepta el límite declarado?
5. **Llaves y permisos.** La llave de la CA queda en la máquina que ejecuta el script; las llaves de servidor se montan de solo lectura, y con UID distinto en cada imagen el modo `0400` puede impedir la lectura (se resuelve con copia por servicio o grupo): se comprueba en la parte 3. Sin renovación automática: a los 90 días hay que regenerar. ¿Quién guarda la CA y quién copia `ca.pem` a los tres nodos Windows?
6. **Dependencia `trustme`** solo para pruebas (alternativa: `openssl` por `subprocess`, marcado `integration`). ¿Se acepta?
7. **Imágenes.** No se ha comprobado que `redis:7-alpine` y la imagen de MinIO de Chainguard soporten TLS con esos parámetros; si no, se cambia de imagen en la parte 3 y se registra.
8. **Orden con F-26.** Ambas tocan `.gitignore`, `.env.example`, `docs/modulo-M4-seguridad.md` y los puertos; esperar a que se fusione la rama de F-26 evita conflictos. ¿Cuál va primero?
9. **Captura real.** Requiere `sudo` y los tres nodos; la ejecuta la persona. Hasta entonces no hay resultado de M4 de TLS y el módulo no pasa de 2 [Parte I §5].
10. **Costo en M1 a M3.** TLS puede bajar el throughput de M3: repetir esa medición (`docs/IMPLEMENTACION.md` §7) y reportar la diferencia.

## Límites declarados de la parte 1

- `requests_session` no impone TLS 1.3 como mínimo: verifica CA y hostname, pero `requests` no expone la versión mínima sin un adaptador propio.
- `redis_kwargs` lleva `ssl=True`, por lo que no sirve con `Redis.from_url("rediss://...")` (parámetro duplicado). La parte 2 debe construir el cliente con `host`, `port` y `ssl=True`. Decisión: queda declarado con 2 `xfail`.
- Una URL con `?ssl_cert_reqs=none` pasada directo a `Redis.from_url` no pasa por `exigir_cifrado` y no se rechaza (`xfail`); la parte 2 debe llamar a `exigir_cifrado` antes de crear el cliente.
- Las pruebas de Redis tardan unos 4,5 s por los reintentos del cliente.
- Las pruebas `test_repo_sin_llaves_ni_certificados`, `test_gitignore_cubre_certs` y la del script `generar_certs.sh` van en la parte 3, cuando existan el script y el `.gitignore`.
- Con TLS activo por defecto, los workers de José, el coordinador de Nahúm y el dashboard de Melany fallan hasta tener `ca.pem` y URLs `https`: coordinar antes de fusionar la parte 3.

## Aprobaciones

Las registra `scripts/flujo.py`. No editar.

| Fase | Aprobó | Fecha | Excepción o motivo |
|---|---|---|---|
| verificación IA de plan | Claude Code (orquestador Sonnet 5.5; subagente arquitecto general-purpose) | 2026-11-11 | SPEC F-27 sin campos pendientes (grep 0); diff contra main solo el SPEC (rama al dia con main, Base: main). AD-37/SUP-33 libres segun arquitecto (no re-verifique). Diseño (TLS de servidor + CA + hostname, sin mTLS, trustme==1.2.1 como dependencia de desarrollo) es propuesta del arquitecto. Pila de 4 partes; 10 preguntas abiertas; decision provisional: aceptar, no fusionar la parte 3 sin coordinar con Jose, Nahum y Melany. (0d427b5) |
| plan | Kenni Rodriguez | 2026-11-11 | aprobación delegada |
| verificación IA de tests | Claude Code (orquestador Sonnet 5.5; subagente developer general-purpose) | 2026-11-11 | Diff solo tests (unit, integracion) y requirements-dev.txt (trustme==1.2.1); src intacto. Ejecute test_tls: error de coleccion ModuleNotFoundError src.infrastructure.tls (rojo); integracion compila. Developer valido los helpers de integracion con un stub temporal (7/7); ese cambio final del timeout solo con py_compile. API asumida la fijan las pruebas (TlsSettings, client_context, exigir_cifrado, redis_kwargs, requests_session, minio_http_client). Pruebas de repo sin llaves y de generar_certs.sh quedan para la parte 3. (e1a1159) |
| tests | Kenni Rodriguez | 2026-11-11 | aprobación delegada |
| verificación IA de implementacion | Claude Code (orquestador Sonnet 5.5; subagente developer general-purpose) | 2026-11-11 | Diff: src/infrastructure/tls.py (~90 lineas) y SPEC; tests intactos. Ejecute test_tls y la integracion local de TLS (resultados arriba). Suite completa segun developer 1813 passed/3 xfailed (no la repeti). Limite: requests_session no impone TLS 1.3 minimo (verifica CA y hostname). (df15443) |
| implementacion | Kenni Rodriguez | 2026-11-11 | aprobación delegada |
| devuelta de verificacion | Kenni Rodriguez | 2026-11-11 | QA: requests_session ignora CA propia con REQUESTS_CA_BUNDLE (alta); proxies/netrc; redirect https->http; redis_kwargs ssl duplicado; exigir_cifrado acepta ssl_cert_reqs=none; hosts vacios; minio_secure 0/false; CA no validada |
| verificación IA de implementacion | Claude Code (orquestador Sonnet 5.5; subagente developer general-purpose) | 2026-11-11 | Correccion de hallazgos QA en tls.py; diff de tests solo quita marcadores xfail (comprobado). Suite completa tras ece11d8: 1864 passed, 8 skipped, 3 xfailed. Integracion segun developer: 25 passed, 3 xfailed. Quedan 3 xfail: redis_kwargs lleva ssl=True y rompe Redis.from_url (decision: la parte 2 usa host/port con ssl=True; limite), ?ssl_cert_reqs=none via from_url directo, TLS 1.3 minimo en requests. (ece11d8) |
| implementacion | Kenni Rodriguez | 2026-11-11 | aprobación delegada |
| verificación IA de verificacion | Claude Code (orquestador Sonnet 5.5; subagente qa-tester general-purpose) | 2026-11-11 | QA 92ec5ac: 26 xfail, 23 corregidos y desmarcados; quedan 3 declarados como limites. Defecto alto (REQUESTS_CA_BUNDLE pisaba la CA) corregido con trust_env=False y verify fijo. No ejecute la integracion de TLS por mi cuenta tras la correccion (developer: 25 passed). (89f7e33) |
| verificacion | Kenni Rodriguez | 2026-11-11 | aprobación delegada |
| verificación IA de documentacion | Claude Code (orquestador Sonnet 5.5; subagente documentador general-purpose) | 2026-11-11 | Diff solo docs (ARQUITECTURA AD-37, REQUERIMIENTOS SUP-33, modulo-M4 nuevo borrador, SPEC); rama alineada con origen. Aviso: modulo-M4-seguridad.md se crea tambien en las ramas de F-26/F-28/F-29?/F-30: habra conflicto al fusionar (resolver al fusionar). Bitacora en estado segun el subagente (no la verifique). Sin pytest: no cambio codigo. (493999b) |
| documentacion | Kenni Rodriguez | 2026-11-11 | aprobación delegada |
| verificación IA de revision | Claude Code (orquestador Sonnet 5.5; subagente revisor general-purpose) | 2026-11-11 | Revisor APROBADO sin bloqueantes: tls.py cumple diseño, sin llaves ni certificados versionados, trustme solo en dev; pytest segun revisor 1864 passed/3 xfailed, integracion TLS 25 passed/3 xfailed. Menores: estimacion de lineas (128 vs 110), conflicto de modulo-M4 con otras ramas al fusionar. (6bd4d8a) |
| revision | Kenni Rodriguez | 2026-11-11 | aprobación delegada |
