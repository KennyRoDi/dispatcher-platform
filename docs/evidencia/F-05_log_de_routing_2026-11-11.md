# F-05 · Log de routing por tipo de contenido

**Fecha:** 2026-11-11 · **Commit:** `b57cde4` · **Python:** 3.13.17 (Windows 10, win32) · **pytest:** 9.1.1

## Qué prueba y qué no

Prueba A de US-05: un caso con texto, imagen, audio y video se descompone con `DispatchCase` y cada sub-tarea llega a la cola de su tipo; el video aporta una sub-tarea a `queue:image` y otra a `queue:audio`; tres consumidores, uno por cola, toman solo lo suyo y no queda nada sin consumir.

Es una ejecución local sobre `FakeWorkQueue` y `FakeClock` (`tests/dobles.py`) con datos sintéticos (sha256 de relleno `aaaa…`, `bbbb…`, `cccc…`, `dddd…`). **No** es Redis, ni `fakeredis`, ni nodos reales; no mide tiempos de sistema operativo y el `0.09s` solo indica que la prueba corre rápido en memoria. El adaptador Redis llega en la parte 2.

## Comando

```bash
.venv/Scripts/python.exe -m pytest -p no:cacheprovider -m acceptance tests/acceptance/test_worker_por_tipo.py -o log_cli=true -o log_cli_level=INFO
```

## Salida cruda

La ruta local del `rootdir` se sustituyó por `<raíz del repositorio>`; el resto es la salida tal cual.

```text
============================= test session starts =============================
platform win32 -- Python 3.13.17, pytest-9.1.1, pluggy-1.7.0
rootdir: <raíz del repositorio>
configfile: pytest.ini
plugins: anyio-4.16.0
collected 1 item

tests/acceptance/test_worker_por_tipo.py::test_worker_de_cada_tipo_consume_solo_lo_suyo 
-------------------------------- live log call --------------------------------
INFO     src.application.dispatch_case:dispatch_case.py:26 routing case=C-1 subtask=C-1:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa:text kind=text source=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa queue=queue:text
INFO     src.application.dispatch_case:dispatch_case.py:26 routing case=C-1 subtask=C-1:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb:image kind=image source=bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb queue=queue:image
INFO     src.application.dispatch_case:dispatch_case.py:26 routing case=C-1 subtask=C-1:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc:audio kind=audio source=cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc queue=queue:audio
INFO     src.application.dispatch_case:dispatch_case.py:26 routing case=C-1 subtask=C-1:dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd:image kind=image source=dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd queue=queue:image
INFO     src.application.dispatch_case:dispatch_case.py:26 routing case=C-1 subtask=C-1:dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd:audio kind=audio source=dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd queue=queue:audio
PASSED                                                                   [100%]

============================== 1 passed in 0.09s ==============================
```

## Lectura

Las cinco líneas `routing` salen del orden de las fuentes (texto, imagen, audio, video); la fuente `dddd…` es el video y produce dos líneas, imagen antes que audio, con el mismo `source`.
