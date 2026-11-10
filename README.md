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

*Pendiente: se completará cuando el sistema esté implementado.*

### Requisitos

*Pendiente.*

**Analizador de texto (F-07).** Sus dependencias van en `requirements-texto.txt`, aparte de `requirements-dev.txt` para que CI no instale torch. torch se instala primero, solo CPU:

```bash
pip install torch==2.15.0 --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements-texto.txt
```

Incluye el modelo de spaCy `es_core_news_sm` 3.8.0 (Explosion AI, GPL-3.0). Los modelos `pysentimiento/robertuito-sentiment-analysis` y `pysentimiento/robertuito-hate-speech` (Pérez et al., github.com/pysentimiento/pysentimiento) se descargan de HuggingFace con la revisión fijada en `config/texto.toml`; se entrenaron con datasets de uso no comercial, admitido solo por el uso académico del proyecto. Referencias R11 y R12 de [docs/ARQUITECTURA.md](docs/ARQUITECTURA.md) §10.

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

### Instalación y despliegue en tres nodos

*Pendiente.*

### Uso

*Pendiente.*

### Pruebas

*Pendiente.*
