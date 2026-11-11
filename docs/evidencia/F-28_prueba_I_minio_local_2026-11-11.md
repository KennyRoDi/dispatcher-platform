**PRUEBA LOCAL: una sola máquina, MinIO efímero; no es la ficha M4 ni acredita nada medido.**

# F-28: prueba I con MinIO real (local), 2026-11-11

Verifica que un objeto cifrado con `EncryptedObjectStore` + `EnvelopeCipher` + `FileKeyProvider` (KEK aleatoria de 32 bytes en un archivo temporal `0600`) llega a MinIO sin el texto en claro, que el viaje de ida y vuelta lo descifra y que alterar un bit falla con `DecryptionError`.

## Entorno

- Fecha: 2026-11-11T08:39:04-06:00
- Docker version 26.1.5+dfsg1, build a72d7cd
- Imagen: `cgr.dev/chainguard/minio@sha256:fb893e36fc369d41e92f678b17ec27378fa5bf0576aeef7ac15460c13629ab5a`
- cryptography              50.0.2; minio                     7.2.20
- Commit base de la prueba: a896aeb (más el cambio de la prueba)
- MinIO efímero: `docker run -d --rm -p 127.0.0.1:<puerto libre>:9000` con credenciales aleatorias (uuid4), sin TLS; el contenedor se elimina al terminar la prueba (0 contenedores después).
- Adaptador de ObjectStore: el mínimo de prueba definido en la propia prueba; el de producción es F-23 (Melany) y no se cableó.

## Comando

```
python -m pytest tests/integration/test_encrypted_object_store_minio.py -v -s -m integration -p no:cacheprovider
```

## Salida real

```
============================= test session starts ==============================
platform linux -- Python 3.13.5, pytest-9.1.1, pluggy-1.7.0 -- /home/krd/Documents/Tecnologico/2026/IIS/Sistemas-Operativos/ProyectoII/.venv/bin/python
rootdir: /home/krd/Documents/Tecnologico/2026/IIS/Sistemas-Operativos/wt-fix-F-28
configfile: pytest.ini
plugins: anyio-4.16.0
collecting ... collected 2 items

tests/integration/test_encrypted_object_store_minio.py::test_objeto_real_en_minio_no_contiene_marcador objeto crudo en MinIO: 1182 bytes, marcador presente: False
PASSED
tests/integration/test_encrypted_object_store_minio.py::test_byte_alterado_en_minio_falla objeto crudo: 632 bytes; se invierte 1 bit del último byte
PASSED

============================== 2 passed in 1.24s ===============================
```

## Lectura

- El objeto leído crudo con el cliente `minio` (1182 bytes para un texto con el marcador dos veces y 1024 bytes aleatorios) no contiene `MARCADOR-SINTETICO-F28-ca5e0b1a`.
- `almacen.open(sha).read()` devuelve el contenido original.
- Con un bit invertido en el último byte almacenado, `almacen.open(sha).read()` lanza `DecryptionError`.

## Límites

Una sola máquina y un solo proceso, sin TLS ni red entre nodos. No mide costo de CPU ni valida el cableado de producción. No sustituye la ficha M4 ni la evidencia en los tres nodos.
