# Módulo M4: seguridad

Borrador de la parte 1 de F-27. Otras ramas (F-26, F-28 a F-30) añaden sus secciones; al fusionar, se unen. **Medición pendiente**: este documento no lleva salidas medidas.

## TLS entre nodos (F-27)

**Responsable:** Kenni Rodriguez. Decisión: AD-37 y SUP-33 en [ARQUITECTURA](ARQUITECTURA.md) §8 y [REQUERIMIENTOS](REQUERIMIENTOS.md). Diseño: `docs/specs/F-27/SPEC.md`.

### Qué se implementó (parte 1)

- `src/infrastructure/tls.py`: `TlsSettings.from_env` (`TLS_ENABLED`, `TLS_CA_FILE`; falla cerrado si falta la CA o no es legible), `client_context` (TLS 1.3 mínimo, `CERT_REQUIRED`, verificación de hostname), `exigir_cifrado` (rechaza `http://`, `redis://` y `MINIO_SECURE=false` con TLS activo) y constructores `redis_kwargs`, `requests_session` y `minio_http_client`.
- `requests_session` usa `trust_env=False` y `verify` fijo a la CA del equipo, de modo que `REQUESTS_CA_BUNDLE`, proxies y `.netrc` no lo alteran, y rechaza redirecciones de https a un esquema en claro.
- Pruebas unitarias y de integración con sockets locales y certificados efímeros de `trustme`, generados dentro de la prueba y sin versionar ninguno.
- Todavía no hay cableado en workers, coordinador ni scripts (parte 2), ni servidores con TLS ni `generar_certs.sh` (parte 3).

### Cómo se activa (parte 2)

- `TLS_ENABLED=true` y `TLS_CA_FILE=<ruta a ca.pem>`; sin CA legible el arranque falla.
- Coordinador y scripts: URLs `https://`. Redis: `rediss://`. MinIO: `MINIO_SECURE=true`.
- Con TLS activo, una URL `http://` o `redis://`, o `MINIO_SECURE=false`, se rechaza al arrancar, sin degradar a texto claro.
- Salidas reales de un arranque con TLS y de un rechazo: pendiente (sin captura ni ejecución medida).

### Certificados y Compose (parte 3)

- `deploy/tls/generar_certs.sh` crea la CA (EC P-256, `pathlen:0`, 365 días) y el certificado del Nodo A (90 días) en `CERTS_DIR`, fuera del repo. Si a la CA le quedan 91 días o menos, se regenera y hay que redistribuir `ca.pem` a los workers.
- Coordinador `8443` y Redis `6380` con TLS; MinIO con su certificado. Pasos en `docs/DEPLOY_WORKERS.md`.

### Límites declarados

- Redis y MinIO reales no se han probado con TLS: sin salida medida.
- `coordinator`, `redis` y `minio` del Nodo A corren con `user: CERTS_UID:CERTS_GID` para leer `server.key` (0600). No se probó con las imágenes reales; el coordinador no escribe en disco (se revisó el código de `src/coordinator`), pero Redis y MinIO pueden requerir un `chown` único de `redis-data` y `minio-data`.
- Con `TLS_ENABLED=false` el worker igual exige `TLS_CA_FILE`.
- Pendientes de otros dueños: `dashboard/app.py:23` y `scripts/generate_dataset.py:18,291` aún apuntan a `http` y 8000.
- Sin evidencia medida, M4 máximo 2.

### Concepto de Sistemas Operativos y de redes

TLS protege el canal entre procesos de distintos nodos: cifra, comprueba la integridad y autentica al servidor con una cadena de confianza. El módulo `ssl` de Python delega en OpenSSL; el cliente decide con qué CA confía y qué versión mínima acepta. JWT (F-26) identifica a quien llama; no protege el canal. Tailscale tampoco sustituye a TLS: la captura debe mostrar el handshake (`docs/ARQUITECTURA.md` §6).

### Fuentes y dependencias de terceros

- Módulo `ssl` de Python, `openssl`, `redis-py`, `minio-py` y `requests`.
- `trustme` 1.2.1, solo desarrollo (`requirements-dev.txt`): licencia MIT o Apache-2.0 según `pip show trustme`; https://github.com/python-trio/trustme.
- RFC 8446 (TLS 1.3); RFC 6125 y RFC 9525 (verificación de identidad del servidor).

### Mediciones

Comandos exactos de `docs/IMPLEMENTACION.md` §5; los ejecuta la persona en el Nodo A con `sudo`, con la IP real de Tailscale:

```bash
sudo tcpdump -i <if> -w m4.pcap 'port 8443 or 6380 or 9000'
tshark -r m4.pcap -Y tls.handshake.type==1
strings m4.pcap | grep -c <marcador_sintetico>
```

| Medición | Resultado |
|---|---|
| Handshakes TLS en la captura (`tshark`) | pendiente |
| Coincidencias del marcador (`strings ... \| grep -c`) | pendiente |
| Cliente sin la CA rechazado en los servicios reales | pendiente |
| Costo de TLS sobre el throughput de M3 | pendiente |

Sin captura real no hay resultado de TLS y el módulo no pasa de 2 [Parte I §5]. `m4.pcap` queda fuera del repo; solo se versiona el resumen de `tshark`.
