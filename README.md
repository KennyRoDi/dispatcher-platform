# Plataforma distribuida de análisis de datos de mensajería

II Proyecto Programado de IC-6600 Principios de Sistemas Operativos, II Semestre 2026, Instituto Tecnológico de Costa Rica, Campus San Carlos. Alternativa B.

La plataforma recibe casos de análisis con conversaciones, notas de voz, imágenes, videos y documentos, los procesa en workers distribuidos y genera reportes consolidados con evidencias enlazadas a su fuente.

El análisis es la carga de trabajo, no el objetivo. El proyecto se centra en cómo el sistema administra recursos escasos y protege información sensible:

| Módulo | Tema |
|---|---|
| M1 | Gestión de memoria: límites con cgroups v2, control de admisión y recuperación de OOM |
| M2 | Planificación: cuatro niveles de prioridad, sin inanición |
| M3 | E/S y almacenamiento: chunks, almacenamiento por contenido y backpressure |
| M4 | Protección y seguridad: roles, TLS, cifrado en reposo y cadena de custodia |
| M5 | Cómputo heterogéneo: routing basado en mediciones |

Solo se usan datos sintéticos o públicos con licencia. Está prohibido incorporar conversaciones, audios o imágenes reales de terceros, incluidos chats propios con mensajes de otras personas.

## Estado

**En desarrollo.** El repositorio contiene el código del I Proyecto Programado, que sirve de base, y los documentos de diseño. Las funcionalidades del II Proyecto y sus mediciones aún no están implementadas. El avance está en `docs/STATUS.md` de la rama `estado`.

## Cómo trabajar

Personas y agentes (Claude Code, Codex y Antigravity) siguen el mismo ciclo: elegir una tarea y avanzar por seis fases, plan, tests, implementación, verificación, documentación y revisión, con aprobación humana en cada una, hasta abrir PR pequeñas y apiladas. **Si eres nuevo, abre [docs/GUIA.html](docs/GUIA.html) en tu navegador.** Las reglas están en [AGENTS.md](AGENTS.md) y [CONTRIBUTING.md](CONTRIBUTING.md).

```bash
python scripts/flujo.py empezables
```

## Mapa del repositorio

| Ruta | Contenido |
|---|---|
| [docs/GUIA.html](docs/GUIA.html) | Guía para entender el repositorio y contribuir |
| [AGENTS.md](AGENTS.md) | Reglas y ciclo de trabajo para agentes y personas |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Commits, títulos de PR y pilas |
| `docs/STATUS.md` de la rama `estado` | Estado de cada funcionalidad |
| [docs/backlog/](docs/backlog/README.md) | Historias, responsables, dependencias y criterios de aceptación |
| [docs/specs/](docs/specs/) | `SPEC.md` aprobado de cada funcionalidad |
| [docs/BITACORA_IA.md](docs/BITACORA_IA.md) | Bitácora de uso de IA |
| [docs/ENUNCIADO.md](docs/ENUNCIADO.md) | Enunciado del proyecto: fuente de verdad |
| [docs/REQUERIMIENTOS.md](docs/REQUERIMIENTOS.md) | Requisitos con cita al enunciado, supuestos y trazabilidad |
| [docs/ARQUITECTURA.md](docs/ARQUITECTURA.md) | Escenarios de calidad, capas, diagramas y decisiones |
| [docs/IMPLEMENTACION.md](docs/IMPLEMENTACION.md) | Funcionalidades, responsables, TDD y comandos de medición |
| [docs/README_I_PROYECTO.md](docs/README_I_PROYECTO.md) | Manual de la plataforma heredada |
| `src/domain`, `src/application`, `src/adapters`, `src/infrastructure` | Capas nuevas |
| `src/coordinator`, `src/workers`, `dashboard`, `scripts`, `deploy` | Código heredado del I Proyecto |
| `tests/` | Pruebas heredadas y `unit`, `integration`, `acceptance` |
| `scripts/flujo.py` | Comandos del ciclo de trabajo |
| `.agents/` | Comandos y roles comunes a todos los agentes |

## Manual

Cada bloque lleva su estado de verificación. «Probado en Linux» significa que se ejecutó tal cual en Debian 13 el 2026-11-11. «Sin probar en Windows» significa que es la traducción de un comando de Linux y que nadie lo ha ejecutado en Windows: verifícalo antes de confiar en él. Desde la raíz del repositorio, salvo que se indique otra cosa. Las funciones de las PR abiertas se listan al final y aún no están en `main`.

### Requisitos

| Herramienta | Para qué | Linux | Windows 11 |
|---|---|---|---|
| Python 3.13 o superior | Todo (`os.process_cpu_count`) | `python3 --version` | `py -3.13 --version` |
| `git` | Clonar y el flujo de trabajo | `apt-get install git` | `winget install --id Git.Git -e` |
| `gh` con sesión (`gh auth login`) | `scripts/flujo.py` | [cli.github.com](https://cli.github.com) | `winget install --id GitHub.cli -e` |
| Docker con Compose v2.20 o superior | Demo local, Nodo A y workers | [Docker Engine](https://docs.docker.com/engine/install/) | Docker Desktop con WSL2: `winget install --id Docker.DockerDesktop -e` |
| `ffmpeg` | Dataset sintético y pruebas que lo usan (se omiten si falta) | `apt-get install ffmpeg` | `winget install --id Gyan.FFmpeg -e` |
| Tailscale | Solo el despliegue en tres nodos | [tailscale.com](https://tailscale.com/download/linux) | `winget install --id Tailscale.Tailscale -e` |

Las instalaciones con `apt-get` y `winget` no se ejecutaron: requieren `sudo` o administrador. Para el Nodo A y los nodos Windows, [docs/DEPLOY_WORKERS.md](docs/DEPLOY_WORKERS.md) §2 trae el procedimiento completo. En Windows puedes ejecutar todo lo que no sea Docker dentro de WSL2 (`wsl --install`, repositorio en el sistema de archivos de WSL2) con los mismos comandos de Linux; esa ruta tampoco está probada.

### Instalación

**Probado en Linux (Debian 13, 2026-11-11)**, con Python 3.13.5; `pip install` tardó unos 20 s:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
```

**Sin probar en Windows: traducción de los comandos de Linux; verificar.** PowerShell:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
```

Si PowerShell bloquea el script de activación, habilita scripts solo en esa ventana con `Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned`.

`requirements-dev.txt` instala el coordinador, los workers, el dashboard y las pruebas, sin torch. Los analizadores de texto, imagen y audio tienen dependencias propias, en [Analizadores](#analizadores-de-texto-imagen-y-audio-f-07-f-08-f-09).

### Pruebas

**Probado en Linux (Debian 13, 2026-11-11):** `1764 passed, 8 skipped, 14 deselected, 3 xfailed` en 93 s, con ffmpeg instalado.

```bash
pytest -q -m "not integration and not acceptance"
```

**Sin probar en Windows: traducción de los comandos de Linux; verificar.** El mismo comando, con el venv activo en PowerShell. Las marcas `integration` y `acceptance` necesitan servicios o nodos reales y no se ejecutan aquí.

### Demo local

Levanta Redis, MinIO, coordinador, reaper, tres workers y un `feeder` que envía casos aleatorios, todo en una máquina, sin `.env` y sin Tailscale. Puertos libres: `8000`, `9000`, `9001` y `127.0.0.1:6379`. Lo que lee el dashboard y los estados de caso están en [docs/DEMO.md](docs/DEMO.md).

**Defecto conocido en `main` (medido el 2026-11-11, sin corregir):** los workers exigen `ADMISSION_MARGIN_BYTES` y `FOOTPRINT_<OP>_BYTES` (F-17, `src/workers/config.py`), y ni `deploy/docker-compose.local.yml` ni `.env.example` los definen. Con el comando de DEMO.md tal cual, los tres workers reinician en bucle con `ValueError: ADMISSION_MARGIN_BYTES es obligatoria y debe ser un entero en bytes`, aunque `/health` del coordinador responde y `/stats` encola casos. Además, sin `mem_limit` el lector de cgroups falla con `ValueError: /sys/fs/cgroup/memory.max debe contener un entero en bytes` y el worker no toma tareas. Hace falta una PR de código; esta guía no la hace.

**Solución provisional, solo para la demo local.** Crea en la raíz un archivo `demo-admision.yml` (sin versionar) con valores **de demostración, no medidos**. Las huellas reales las fija la ficha M1 (§4.1, pendiente de medir):

```yaml
services:
  worker:
    mem_limit: 2g
    memswap_limit: 2g
    environment:
      ADMISSION_MARGIN_BYTES: 268435456
      FOOTPRINT_TRANSCODE_VIDEO_BYTES: 268435456
      FOOTPRINT_EXTRACT_AUDIO_BYTES: 268435456
      FOOTPRINT_GENERATE_THUMBNAIL_BYTES: 268435456
      FOOTPRINT_CONVERT_AUDIO_BYTES: 268435456
      FOOTPRINT_EXTRACT_METADATA_BYTES: 268435456
```

**Probado en Linux (Debian 13, 2026-11-11)**, con el archivo anterior: ocho contenedores arriba, tres workers con `alive: true` en `GET /workers`, casos en `completed` y el feeder enviando casos. Sin el archivo, los workers no arrancan, como se describió.

```bash
docker compose -f deploy/docker-compose.demo.yml -f demo-admision.yml up -d --build
docker compose -f deploy/docker-compose.demo.yml logs -f feeder
curl -s http://localhost:8000/stats
curl -s http://localhost:8000/workers
docker compose -f deploy/docker-compose.demo.yml down -v
```

Con la demo en marcha y el venv activo, en otra terminal, estos comandos también se probaron en Linux. `cp .env.demo .env` reemplaza el `.env` que tengas:

```bash
cp .env.demo .env
python -m scripts.check_connectivity
python -m scripts.submit_case --dir <carpeta con videos o audios> --mode auto --timeout 100
```

`check_connectivity` salió con `[OK]` en redis, coordinator, minio, ffmpeg y work_dir. `submit_case` subió un video de 2 s, terminó en `completed` y salió con 0. Al terminar, `down -v` dejó 0 contenedores y 0 volúmenes. `docker compose ... down` sin `-v` conserva los datos.

**Sin probar en Windows: traducción de los comandos de Linux; verificar.** Los comandos `docker compose` y `python` son los mismos en PowerShell; cambian la activación del venv y la copia del `.env`:

```powershell
Copy-Item .env.demo .env
curl.exe -s http://localhost:8000/stats
```

### Nodo A y workers

La topología es un Nodo A (Linux: coordinador, Redis, MinIO y reaper) y tres nodos worker (Windows 11 con Docker Desktop sobre WSL2), unidos por Tailscale. El procedimiento completo, con `.env` por máquina, arranque, comprobaciones y problemas, está en [docs/DEPLOY_WORKERS.md](docs/DEPLOY_WORKERS.md); no se repite aquí. **Esa guía no se ha ejecutado sobre nodos reales** y lo dice así.

Resumen de los comandos, tal como los define esa guía. **Sin probar: requieren Tailscale y los nodos, que esta verificación no tocó.**

```bash
cp .env.example .env          # en cada máquina; sustituye <IP_TAILSCALE_NODO_A>, NODE_NAME y NODE_IP
docker compose up -d --build  # Nodo A, Linux
```

```powershell
Copy-Item .env.example .env
docker compose --env-file .env -f deploy/docker-compose.worker.yml run --rm worker python -m scripts.check_connectivity
python scripts/start_worker.py
```

Para workers, configure `WORKER_MEM_LIMIT` en el `.env` local con un límite por worker medido para ese nodo; no hay un valor predeterminado. `python scripts/start_worker.py` ejecuta el preflight y después `docker compose up -d --build`; en el nodo GPU use `--gpu`. El preflight puede ejecutarse solo con `python scripts/preflight.py [--gpu]`. Obtiene `MemTotal` del daemon Linux de Docker con `docker info --format '{{.MemTotal}}'`; en Docker Desktop consulta su entorno WSL2 aunque Python corra desde PowerShell. El procedimiento de tres arranques y lecturas de cgroups está en [la ficha M1](docs/modulo-M1-memoria.md). Las mediciones reales de límites en nodos siguen pendientes.

**Probado en Linux (Debian 13, 2026-11-11):** solo el preflight, con un `.env` de valores locales de prueba (`NODE_NAME=prueba-local`, `NODE_IP=127.0.0.1`, `WORKER_MEM_LIMIT=2g`, sin tocar ningún nodo). Salida: `Preflight aprobado: presupuesto de memoria dentro de la RAM del nodo`, código 0. `start_worker.py` no se ejecutó, porque después del preflight levanta un worker contra el Nodo A.

**Defecto conocido, por lectura del código, no ejecutado en un nodo:** `.env.example` y `deploy/docker-compose.worker.yml` tampoco definen `ADMISSION_MARGIN_BYTES` ni `FOOTPRINT_<OP>_BYTES`, de modo que un worker de nodo fallaría igual que en la demo. Estos valores deben salir de la medición de la ficha M1; no se inventan en esta guía.

### Dataset sintético

Genera el dataset de [B.3] solo con datos sintéticos: chats, imágenes, audios, documentos y casos pesados, con `manifest.json`. Necesita `ffmpeg`. `--out` debe estar fuera del repositorio. Se ejecuta como módulo y con `PYTHONPATH` en la raíz: `python scripts/dataset_sintetico.py` falla con `ModuleNotFoundError`. Opciones: `--seed`, `--out` (obligatoria), `--params` (JSON con los campos de `DatasetParams`) y `--validar`.

Sin `--params`, los valores predeterminados son los mínimos de B.3 (40 casos, 20 000 mensajes, 300 imágenes, 150 audios y casos pesados de 200 MiB). Esa corrida es grande y no se ejecutó en esta verificación. Para probar la herramienta con un tamaño mínimo, guarda esto como `~/scratch/dataset-minimo.json` (UTF-8 sin BOM):

```json
{"cases": 2, "light_heterogeneous": 1, "heavy_heterogeneous": 0, "messages": 50, "images": 4, "audios": 2, "heavy_bytes": 0}
```

**Probado en Linux (Debian 13, 2026-11-11)**, con ffmpeg 7.1.5. Generó 9 archivos (24 MB) en 2 s, con código 0 y repetible. `--validar` salió con código 1 porque ese tamaño no alcanza los mínimos, como debe:

```bash
PYTHONPATH=. python -m scripts.dataset_sintetico --seed 1 --out ~/scratch/dataset-minimo --params ~/scratch/dataset-minimo.json
PYTHONPATH=. python -m scripts.dataset_sintetico --out ~/scratch/dataset-minimo --validar
```

Para el dataset completo, omite `--params`: `PYTHONPATH=. python -m scripts.dataset_sintetico --seed 1 --out ~/scratch/dataset`.

**Sin probar en Windows: traducción de los comandos de Linux; verificar.** En PowerShell la variable de entorno se define aparte, y es de esa sesión:

```powershell
$env:PYTHONPATH = "."
python -m scripts.dataset_sintetico --seed 1 --out "$HOME\scratch\dataset-minimo" --params "$HOME\scratch\dataset-minimo.json"
python -m scripts.dataset_sintetico --out "$HOME\scratch\dataset-minimo" --validar
```

El dataset heredado del I Proyecto (`dataset/`, `scripts/build_dataset.py`) es otra cosa y se usa en la corrida de carga de [docs/DEPLOY_WORKERS.md](docs/DEPLOY_WORKERS.md) §5.1.

### Flujo de trabajo

`scripts/flujo.py` automatiza el ciclo de [AGENTS.md](AGENTS.md) y necesita `gh` con sesión iniciada. **Probado en Linux (Debian 13, 2026-11-11):** `python scripts/flujo.py empezables --todas` lista las funcionalidades por clase (EMPEZABLES, APILABLES, ACTIVAS). El resto de los comandos modifican ramas, SPEC y PR, y no se ejecutaron en esta verificación:

```bash
python scripts/flujo.py soy <usuario-de-GitHub>   # una vez por clon
python scripts/flujo.py empezables
python scripts/flujo.py trabajar F-XX
python scripts/flujo.py cierre --tipo feat --resumen "texto"
```

**Sin probar en Windows: traducción de los comandos de Linux; verificar.** En PowerShell son los mismos, con el venv activo.

### Analizadores de texto, imagen y audio (F-07, F-08, F-09)

**Analizador de texto (F-07).** Sus dependencias van en `requirements-texto.txt`, aparte de `requirements-dev.txt` para que CI no instale torch. torch se instala primero, solo CPU:

```bash
pip install torch==2.15.0 --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements-texto.txt
```

Incluye el modelo de spaCy `es_core_news_sm` 3.8.0 (Explosion AI, GPL-3.0). Los modelos `pysentimiento/robertuito-sentiment-analysis` y `pysentimiento/robertuito-hate-speech` (Pérez et al., github.com/pysentimiento/pysentimiento) se descargan de HuggingFace con la revisión fijada en `config/texto.toml`; se entrenaron con datasets de uso no comercial, admitido solo por el uso académico del proyecto. La licencia MIT cubre el código y el dataset sintético del repositorio, no los modelos de terceros, que conservan sus licencias. Referencias R11 y R12 de [docs/ARQUITECTURA.md](docs/ARQUITECTURA.md) §10.

La primera carga descarga unos 870 MB de HuggingFace y necesita red. Para generar la tabla de aciertos, desde la raíz del repositorio:

```bash
pytest -m integration tests/integration/test_text_models_real.py
python -m scripts.aciertos_texto --conversacion tests/datos/aciertos_texto_conversacion.json --etiquetas tests/datos/aciertos_texto_etiquetas.json --salida docs/evidencia/F-07_aciertos_<fecha>.md
pytest -m acceptance tests/acceptance/test_texto_aciertos.py
```

El script usa el tamaño de lote del archivo de etiquetas. La conversación es sintética; la tabla prueba el funcionamiento de punta a punta, no la precisión. La corrida del 2026-11-07 está en `docs/evidencia/F-07_aciertos_2026-11-07.md`.

**Analizador de imagen (F-08).** Sus dependencias van en `requirements-imagen.txt`, aparte de `requirements-dev.txt` para que CI no instale torch. torch se instala primero, solo CPU:

```bash
pip install torch==2.15.0 --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements-imagen.txt
```

Usa Ultralytics YOLO 8.4.208 (AGPL-3.0) con los pesos `yolo11n.pt` de la release v8.4.0 de github.com/ultralytics/assets, también AGPL-3.0. Los pesos no van en el repositorio (`*.pt` está en `.gitignore`): se descargan a mano y se colocan en el directorio de pesos que recibe `YoloDetector.from_config`, que comprueba antes de cargarlos el SHA-256 fijado en `config/imagen.toml`. La prueba de integración toma ese directorio de `F08_DIRECTORIO_PESOS` (por defecto, la raíz del repositorio) y la imagen positiva de `F08_IMAGEN_POSITIVA`. Referencia R13 de [docs/ARQUITECTURA.md](docs/ARQUITECTURA.md) §10.

Para generar la tabla de aciertos, desde la raíz del repositorio, con el directorio de pesos en `F08_DIRECTORIO_PESOS`:

```bash
F08_IMAGEN_POSITIVA=tests/datos/imagenes/cuchillo_02.jpg pytest -m integration tests/integration/test_yolo_detector_real.py
python -m scripts.aciertos_imagen --muestra tests/datos/imagenes --etiquetas tests/datos/imagenes/etiquetas.json --salida docs/evidencia/F-08_aciertos_<fecha>.md --pesos "$F08_DIRECTORIO_PESOS"
pytest -m acceptance tests/acceptance/test_imagen_aciertos.py
```

La muestra son 20 fotos propias de José Andrés (CC BY 4.0); la tabla prueba el funcionamiento de punta a punta, no la precisión. La corrida del 2026-11-09, con el análisis de sus fallos, está en `docs/evidencia/F-08_aciertos_2026-11-09.md`.

**Analizador de audio (F-09).** Sus dependencias van en `requirements-audio.txt`, aparte de `requirements-dev.txt` para que CI no instale torch. Incluye `requirements-texto.txt`, porque la transcripción pasa por el análisis de texto de F-07. torch se instala primero, solo CPU:

```bash
pip install torch==2.15.0 --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements-audio.txt
```

Transcribe con faster-whisper 1.2.1 (SYSTRAN, MIT) en CPU, con los pesos de Whisper (OpenAI, MIT) convertidos a CTranslate2 en `Systran/faster-whisper-base`. La revisión de esos pesos queda fijada en `config/audio.toml`, donde `idioma` debe ser un código de idioma de Whisper (por ejemplo `es`) y cualquier otro valor falla al cargar. Los pesos no van en el repositorio: se descargan a la caché de Hugging Face en la primera carga, que necesita red. La prueba de integración toma la nota de voz de `F09_NOTA`, que debe ser propia o con licencia [B.3], y se salta si faster-whisper no está instalado. Desde la raíz del repositorio:

```bash
F09_NOTA=<ruta> pytest -m integration tests/integration/test_whisper_transcriber_real.py
```

Referencia R14 de [docs/ARQUITECTURA.md](docs/ARQUITECTURA.md) §10.

La muestra de `tests/datos/audio/` son 5 notas de voz `.ogg` Opus (2 con una amenaza explícita y 3 neutras), con su transcripción esperada, procedencia y licencia en `transcripciones.json`. Son la voz propia de José Andrés leyendo guiones sintéticos y ficticios, redactados con IA, bajo licencia CC BY 4.0 [B.3]. El script `scripts/comparar_transcripcion.py` compara la transcripción obtenida con la esperada y calcula la tasa de error por palabra (WER) tras normalizar mayúsculas, tildes y puntuación, sin umbral.

`requirements-audio.txt` fija `av==18.1.0`: faster-whisper 1.2.1 falla con PyAV 19.0.2 (`TypeError ... metadata_errors`), medido en la corrida.

**La corrida con el modelo real se hizo el 2026-11-10** (faster-whisper 1.2.1, av 18.1.0, pesos `base` fijados, Python 3.14, CPU, `int8`). Su evidencia, con las observaciones medidas, está en `docs/evidencia/F-09_transcripcion_2026-11-10.md`: WER de 15.4, 9.1, 36.4, 27.3 y 0.0 % sobre las 5 notas. US-09 queda demostrada solo con esa muestra de 5 notas propias y sintéticas, sin representatividad: `amenaza_01` es un falso negativo, porque Whisper `base` oyó «más a ver» en vez de «vas a ver», y un tono sostenido produce un segmento inventado de `...`. Para repetirla, desde la raíz del repositorio y con `requirements-audio.txt` instalado:

```bash
F09_NOTA=tests/datos/audio/amenaza_01.ogg pytest -m integration tests/integration/test_whisper_transcriber_real.py
pytest -m integration tests/integration/test_whisper_errores_de_av_reales.py
python -m scripts.comparar_transcripcion --muestra tests/datos/audio --esperadas tests/datos/audio/transcripciones.json --salida docs/evidencia/F-09_transcripcion_<fecha>.md
pytest -m acceptance tests/acceptance/test_audio_transcripcion.py
```

## Funciones en PR abiertas (aún no en main)

Estas funciones están implementadas en PR abiertas y todavía no se han fusionado, así que no están en `main` ni aquí se documentan comandos para ellas. Sus instrucciones de uso llegarán a este README cuando se fusionen:

- TLS entre nodos
- Autenticación y roles
- Cifrado en reposo
- Cadena de custodia
- Reporte consolidado
- Alertas
