**Resumen:** 46 requisitos funcionales y 25 no funcionales de la Alternativa B, cada uno con cita al enunciado, criterio verificable y módulo asociado.

# Requerimientos: Plataforma distribuida de análisis de datos de mensajería

Fuente única: [ENUNCIADO.md](ENUNCIADO.md), conversión de `II_ProyectoProgramado_IC6600_IIS2026.docx`, Parte III (B.1 a B.10), Anexos 1 a 3 y Parte I como marco común.
Convención de citas: `[B.5 M1]`, `[B.4 Estados del caso]`, `[Parte I §3]`, `[Anexo 2]`.

## 1. Requisitos funcionales

### 1.1 Pipeline base

| ID | Descripción | Fuente | Criterio verificable | Módulo |
|---|---|---|---|---|
| RF-01 | Crear casos que agrupen múltiples fuentes de uno o varios usuarios (conversaciones, texto, voz, imagen, video, documentos). | [B.4 Recepción de casos] [B.1] | Un caso con texto, imagen, audio y video queda registrado con 4 fuentes consultables por API. | Pipeline |
| RF-02 | Validar el formato de cada fuente al recibirla. | [B.4 Recepción de casos] | Una fuente con formato no admitido se rechaza con error explícito y no genera sub-tarea. | Pipeline |
| RF-03 | Registrar y almacenar la carga de cada caso. | [B.4 Recepción de casos] | Cada fuente aceptada queda en almacenamiento y su registro enlaza caso, fuente y objeto. | Pipeline |
| RF-04 | Descomponer cada caso en sub-tareas. | [B.4 Cola y distribución] | Un caso de N fuentes genera sub-tareas trazables a su fuente y al caso. | Pipeline |
| RF-05 | Enrutar sub-tareas por tipo de contenido hacia workers especializados. | [B.4 Cola y distribución] | Texto, imagen y audio llegan solo a colas consumidas por su tipo de worker. | Pipeline |
| RF-06 | Worker de texto: palabras clave, clasificación temática, sentimiento, lenguaje ofensivo o amenazas. | [B.4 Workers de análisis] | Una conversación etiquetada produce las cuatro salidas por mensaje o lote. | Pipeline |
| RF-07 | Worker de imagen: clasificación o detección de objetos o contenido sensible. | [B.4 Workers de análisis] | Una imagen positiva de la verdad de referencia produce categoría y confianza. | Pipeline |
| RF-08 | Worker de audio: speech-to-text y análisis del texto transcrito. | [B.4 Workers de análisis] | Una nota de voz produce transcripción con timestamps y el análisis de RF-06. | Pipeline |
| RF-09 | Manejar los estados `queued`, `processing`, `completed`, `partially_completed`, `failed`, `retrying`, `cancelled`. | [B.4 Estados del caso] | Cada estado se alcanza en una prueba; una transición no permitida se rechaza. | Pipeline |
| RF-10 | Cerrar el caso mediante sincronización tipo barrier/join. | [B.4 Estados del caso] | El caso solo pasa a estado final cuando todas sus sub-tareas terminaron, sin doble conteo. | Pipeline |
| RF-11 | Reintentar con backoff y número máximo configurable. | [B.4 Reintentos y cancelación] | Una sub-tarea que falla se reintenta con esperas crecientes y falla al llegar al máximo configurado. | Pipeline |
| RF-12 | Cancelación real: detener sub-tareas en curso y liberar procesos, memoria y archivos temporales. | [B.4 Reintentos y cancelación] | Tras cancelar no quedan procesos ni temporales de la sub-tarea y la memoria del worker baja. | Pipeline |
| RF-13 | Reporte consolidado con hallazgos, categorías detectadas, línea temporal de actividad e incidencias. | [B.4 Reporte consolidado] [B.1] | El reporte de un caso finalizado contiene las cuatro secciones. | Pipeline |
| RF-14 | Fragmentos de evidencia (mensaje, imagen o segmento de audio con timestamp) enlazados a su fuente original. | [B.4 Reporte consolidado] | Cada fragmento resuelve a su objeto de origen y a su posición o timestamp. | Pipeline |
| RF-15 | Notificar de forma asíncrona cuando un caso finaliza. | [B.4 Alertas] | La alerta llega sin que el pipeline espere al consumidor de alertas. | Pipeline |
| RF-16 | Notificar de forma asíncrona cuando se detecta una incidencia de severidad alta. | [B.4 Alertas] | Una incidencia alta genera alerta antes del cierre del caso. | Pipeline |
| RF-17 | Dashboard en tiempo real de casos, sub-tareas, workers, colas y uso de recursos por nodo (CPU, memoria, GPU si existe). | [B.4 Dashboard] | Durante una ráfaga, el panel muestra los cinco grupos de datos actualizándose para los tres nodos. | Pipeline |

### 1.2 Dataset

| ID | Descripción | Fuente | Criterio verificable | Módulo |
|---|---|---|---|---|
| RF-18 | Al menos 40 casos, de ellos al menos 10 heterogéneos (texto + imagen + audio + video/documento). | [B.3 Dataset mínimo] | El validador del manifiesto cuenta ≥ 40 casos y ≥ 10 heterogéneos. | Pipeline |
| RF-19 | Al menos 20 000 mensajes en formato de exportación realista, con timestamps y remitentes. | [B.3 Dataset mínimo] | El validador cuenta ≥ 20 000 mensajes y todos se analizan sintácticamente. | Pipeline |
| RF-20 | Al menos 300 imágenes con proporción conocida de contenido positivo. | [B.3 Dataset mínimo] | El manifiesto declara ≥ 300 imágenes y la proporción por categoría. | Pipeline |
| RF-21 | Al menos 150 notas de voz de distintas duraciones. | [B.3 Dataset mínimo] | El manifiesto declara ≥ 150 audios; `ffprobe` confirma variedad de duraciones. | Pipeline |
| RF-22 | Al menos 5 casos con video o adjuntos ≥ 200 MB. | [B.3 Dataset mínimo] | El validador encuentra ≥ 5 casos con un archivo de tamaño ≥ 200 MB. | M3 |
| RF-23 | Verdad de referencia para al menos una muestra, para reportar aciertos y errores. | [B.3 Dataset mínimo] | Un script compara salida y etiquetas y reporta aciertos y errores por categoría. | Pipeline |

### 1.3 Módulos de Sistemas Operativos

| ID | Descripción | Fuente | Criterio verificable | Módulo |
|---|---|---|---|---|
| RF-24 | Cada worker corre bajo un límite de memoria (cgroups v2). | [B.5 M1] | `memory.max` del cgroup de cada worker contiene el límite configurado, no `max`. | M1 |
| RF-25 | Control de admisión basado en la huella medida: el nodo solo acepta lo que su memoria permite. | [B.5 M1] | Con carga superior a la capacidad, las sub-tareas excedentes esperan en cola y no se ejecutan. | M1 |
| RF-26 | Detectar terminaciones por OOM y reencolar con una política definida. | [B.5 M1] | Un OOM provocado se registra como tal y la sub-tarea sigue la política documentada. | M1 |
| RF-27 | Permitir ejecutar las dos estrategias de carga de modelos para justificar una. | [B.5 M1] | Un parámetro de configuración selecciona un modelo por proceso o modelo compartido tras `fork`. | M1 |
| RF-28 | Cuatro niveles de prioridad: baja, media, alta y crítica. | [B.5 M2] | Un caso se crea con cualquiera de los 4 niveles; otro valor se rechaza. | M2 |
| RF-29 | Algoritmo de planificación explícito, documentado y sin inanición de casos de baja prioridad. | [B.5 M2] | Una prueba con reloj simulado demuestra que un caso bajo se despacha bajo flujo alto continuo. | M2 |
| RF-30 | Permitir ejecutar al menos dos políticas para compararlas. | [B.5 M2] | Un parámetro selecciona FIFO o prioridad con aging sin cambiar otro código. | M2 |
| RF-31 | Transferir archivos grandes en bloques de tamaño justificado, con reensamblado verificado por hash. | [B.5 M3] | Un archivo ≥ 200 MB se reensambla con SHA-256 igual; un bloque alterado se rechaza. | M3 |
| RF-32 | Almacenamiento direccionado por contenido (SHA-256) con deduplicación. | [B.5 M3] | Subir dos veces el mismo contenido deja un solo objeto, referenciado por ambas fuentes. | M3 |
| RF-33 | Contrapresión: colas acotadas que bloquean o rechazan productores al llenarse. | [B.5 M3] | Con la cola llena, el productor recibe bloqueo o rechazo y la profundidad no supera el límite. | M3 |
| RF-34 | Recibir archivos con E/S asíncrona o no bloqueante. | [B.5 M3] | Durante una subida grande, otra petición de la API responde sin esperar a que termine. | M3 |
| RF-35 | Autenticación y control de acceso por roles: analista, supervisor, administrador. | [B.5 M4] | Sin credencial se responde 401; con un rol insuficiente se responde 403. | M4 |
| RF-36 | Cifrado en tránsito (TLS) entre nodos. | [B.5 M4] | Una captura entre nodos muestra TLS y no contiene contenido en claro. | M4 |
| RF-37 | Cifrado en reposo de las evidencias con gestión de llaves justificada. | [B.5 M4] | El objeto almacenado no se descifra sin la llave y no contiene el texto original. | M4 |
| RF-38 | Cadena de custodia: hash al ingresar y en cada transformación, en log de solo-anexión encadenado por hash. | [B.5 M4] | Cada evidencia tiene una entrada de ingreso y una por transformación, enlazadas al hash anterior. | M4 |
| RF-39 | Verificar la cadena y detectar manipulación de evidencia o log. | [B.5 M4] | El verificador falla e indica la posición al alterar una evidencia o una entrada del log. | M4 |
| RF-40 | Ejecutar al menos una carga de inferencia en dos o más configuraciones de cómputo. | [B.5 M5] | La misma entrada produce latencia, throughput y memoria para cada configuración. | M5 |
| RF-41 | Política de routing del coordinador por tipo de nodo, definida con los resultados medidos. | [B.5 M5] [B.5 Conexión con Unidad 1] | La tabla de routing cita la medición que la justifica y el coordinador la aplica. | M5 |

### 1.4 Escenarios de carga y tolerancia a fallos

| ID | Descripción | Fuente | Criterio verificable | Módulo |
|---|---|---|---|---|
| RF-42 | Ráfaga: envío concurrente de al menos 20 casos. | [B.6 Ráfaga de carga] | Se reportan throughput, latencia por caso y recursos por nodo durante la ráfaga. | Pipeline |
| RF-43 | Caída de un worker durante un caso en proceso: detección, reasignación y estado final correcto. | [B.6 Caída de un worker] | Tras `docker kill`, sus sub-tareas se reasignan y el caso cierra en estado correcto. | Pipeline |
| RF-44 | Reinicio del coordinador con casos en curso: retomar sin perder ni duplicar sub-tareas. | [B.6 Reinicio del coordinador] | Las sub-tareas contadas al final coinciden con las creadas, sin faltantes ni repetidas. | Pipeline |
| RF-45 | Cancelación de un caso pesado a mitad de procesamiento, con liberación de recursos. | [B.6 Cancelación en curso] | Antes y después de cancelar se comparan memoria, procesos y temporales. | Pipeline |
| RF-46 | Carga superior a la memoria de un nodo: el control de admisión evita el colapso. | [B.6 Saturación de memoria] [B.5 M1] | El nodo sigue respondiendo y sus heartbeats no se interrumpen durante la saturación. | M1 |

## 2. Requisitos no funcionales

| ID | Descripción | Fuente | Criterio verificable | Módulo |
|---|---|---|---|---|
| RNF-01 | Al menos tres nodos worker en entidades de ejecución separadas, comunicados por red; no todo en una máquina. | [B.2] [B.10] | Tres `hostname` e IP distintos aparecen como workers activos y procesan sub-tareas en la demo. | Pipeline |
| RNF-02 | `docs/reutilizacion.md` declara qué se reutiliza, qué se modifica y qué es nuevo. | [B.2] [B.8] [B.9] | Cada componente del I Proyecto aparece en una de las tres categorías, con ruta. | Pipeline |
| RNF-03 | Corregir las deficiencias señaladas en la evaluación del I Proyecto. | [B.2] | Cada deficiencia señalada tiene su corrección enlazada en `docs/reutilizacion.md`. | Pipeline |
| RNF-04 | Prohibido usar conversaciones, audios o imágenes reales de terceros, incluidos chats propios con mensajes de otras personas. | [B.3] | Revisión del manifiesto: ninguna fuente procede de datos reales de terceros. | Pipeline |
| RNF-05 | Conversaciones sintéticas o públicas con licencia académica; imágenes y audios públicos con licencia o propios; uso de IA declarado. | [B.3] | Cada fuente del manifiesto tiene origen admitido; lo generado con IA aparece en la bitácora. | Pipeline |
| RNF-06 | `docs/dataset.md` declara procedencia y licencia de cada fuente. | [B.3] [B.8] [B.10] | Ninguna fuente del manifiesto carece de procedencia y licencia. | Pipeline |
| RNF-07 | Workers sin privilegios: usuario no root y sistema de archivos de solo lectura o equivalente. | [B.5 M4] | `docker exec <worker> id -u` devuelve distinto de 0 y `ReadonlyRootfs` es `true`. | M4 |
| RNF-08 | Las llaves nunca van en el código. | [B.5 M4] | Una búsqueda de secretos sobre todo el historial de Git no encuentra llaves. | M4 |
| RNF-09 | Evidencia M1: tabla de huella por modelo; memoria por worker en el tiempo durante una ráfaga; OOM provocado y recuperación; comparación entre las dos estrategias de carga. | [B.5 M1] | Los cuatro productos aparecen con sus datos en la ficha M1. | M1 |
| RNF-10 | Evidencia M2: al menos dos políticas bajo flujo sostenido de alta prioridad; espera, turnaround y throughput por nivel; ausencia de inanición demostrada con datos. | [B.5 M2] | Las tres métricas aparecen por nivel y política; la espera de la prioridad baja queda acotada en los datos. | M2 |
| RNF-11 | Evidencia M3: MB/s para al menos 3 tamaños de chunk; tasa de deduplicación sobre el dataset; profundidad de cola y tiempos de respuesta con y sin backpressure. | [B.5 M3] | Los tres productos aparecen con sus datos en la ficha M3. | M3 |
| RNF-12 | Evidencia M4: prueba de manipulación; accesos denegados por rol; captura de tráfico cifrado; workers sin root. | [B.5 M4] | Los cuatro productos aparecen con su comando en la ficha M4. | M4 |
| RNF-13 | Evidencia M5: tabla de latencia, throughput y memoria por configuración; routing justificado; conexión con Unidad 1. | [B.5 M5] [B.5 Conexión con Unidad 1] | La tabla y la justificación aparecen en la ficha M5. | M5 |
| RNF-14 | Una ficha por módulo con los cinco elementos, en `docs/modulo-MX-nombre.md`. Sin datos medidos, el módulo tiene máximo 2. | [Parte I §5] [Anexo 2] [B.8] | Existen 5 fichas con 5 secciones cada una; ninguna depende solo de capturas. | M1–M5 |
| RNF-15 | Documentar los cinco escenarios en el informe final, con métricas, gráficos e interpretación. | [B.6] [B.8] [B.9] | El informe tiene una sección con los tres elementos por escenario. | Pipeline |
| RNF-16 | Cubrir la rúbrica: pipeline 15 %, M1–M5 40 % (8 % cada uno), pruebas 10 %, documentación 10 %, defensa 15 %, bitácora 10 %. | [B.9] | Cada rubro tiene al menos una funcionalidad asignada en `IMPLEMENTACION.md`. | M1–M5 y pipeline |
| RNF-17 | Matriz de responsabilidades en `docs/responsabilidades.md`; al menos un módulo por integrante como responsable principal. | [Parte I §3] [B.5] [B.10] [Anexo 1] | Cada módulo tiene responsable, apoyo, ruta y ficha; cada integrante tiene al menos un módulo. | M1–M5 y pipeline |
| RNF-18 | Historial de Git que refleje la matriz, con contribuciones distribuidas y sin commits masivos al final. | [Parte I §3] [Parte I §8] | `git shortlog -sn` y `git log --stat` muestran contribuciones por integrante en sus componentes. | M1–M5 y pipeline |
| RNF-19 | `docs/BITACORA_IA.md` (SUP-20) en formato del Anexo 3, con entrada por módulo donde se usó IA y al menos dos errores de la IA detectados. | [Parte I §4] [Anexo 3] [B.9] | Cada módulo tiene entrada o declaración de no uso; hay ≥ 2 casos de error con su validación. | M1–M5 y pipeline |
| RNF-20 | Hitos H1, H2 y H3 verificables en el historial. | [Parte I §2] [Parte I §8] | Cada entregable de hito tiene commits identificables; fechas reales, sin reescritura. | M1–M5 y pipeline |
| RNF-21 | Entregables comunes: repositorio con historial completo, README, `docs/`, informe PDF de máximo 20 páginas sin anexos. | [Parte I §7] | Lista de comprobación completa; el PDF tiene ≤ 20 páginas sin anexos y sigue la convención de nombres del curso. | M1–M5 y pipeline |
| RNF-22 | Entregables específicos: código, despliegue por nodo con instrucciones, arquitectura actualizada con diagramas de componentes, despliegue y flujo. | [B.8] | Una persona externa al equipo puede seguir las instrucciones de despliegue; existen los tres diagramas. | Pipeline |
| RNF-23 | Demostración en vivo sobre los nodos reales y defensa oral individual; sin videos pregrabados como sustituto. | [Parte I §6] [B.8] [B.10] | Cada responsable explica y modifica en vivo su componente sin apoyo. | M1–M5 y pipeline |
| RNF-24 | Citar el código y las configuraciones de terceros en el código y en la documentación. | [Parte I §9] | Cada dependencia copiada o adaptada tiene su fuente citada en ambos lugares. | M1–M5 y pipeline |
| RNF-25 | El proyecto no entrena modelos de IA: el análisis es la carga de trabajo y se usan modelos ya entrenados. | [B.1 Requisito central] | El repositorio no contiene código de entrenamiento. | Pipeline |

## 3. Supuestos

El documento no define estos puntos. Son decisiones provisionales, no requisitos. Requieren confirmación los marcados con ⚠.

| ID | Supuesto | Justificación técnica |
|---|---|---|
| SUP-01 ⚠ | Equipo de 4: Kenni Rodriguez, Nahúm Murillo, José Andrés Loría Herrera y Melany Vindas, con la distribución de módulos aceptada. Falta confirmar el usuario de GitHub de Melany Vindas y que Nahúm Murillo acepte la invitación. | Indicado por Kenni Rodriguez; [Parte I, Modalidad] mantiene los equipos. |
| SUP-02 | H1 el 28/oct/26 y H2 el 04/nov/26, contando semanas desde el 21/oct/26. | El documento dice «fin de semana 1» y «fin de semana 2» sin fecha. Es una inferencia, compatible con tres semanas hasta el 10/nov/26. |
| SUP-03 | La entrega final es el 10/nov/26, no el 04/nov/26 del enunciado. | Indicado por Kenni Rodriguez. Falta la hora de entrega. |
| SUP-04 | Coordinador, Redis, MinIO y custodia comparten el Nodo A, una máquina Linux que no corre workers. Los tres nodos worker son otras tres máquinas, con Windows 11. | [B.2] exige tres nodos worker en entidades separadas, no prohíbe una máquina adicional para los servicios, y el equipo tiene cuatro. |
| SUP-05 | `completed`: todas bien. `partially_completed`: al menos una bien y una fallida definitiva. `failed`: ninguna bien. `retrying`: alguna espera reintento. `cancelled`: terminal y prevalece. | [B.4] enumera estados, no su semántica. Coincide con `_final_case_status` del I Proyecto. |
| SUP-06 | Máximo de 3 intentos y backoff exponencial con jitter, base configurable. | 3 viene de `MAX_ATTEMPTS` del I Proyecto. [B.4] solo exige que sea configurable. |
| SUP-07 | Severidad alta: amenaza explícita en texto o audio, o detección de arma en imagen. Reglas en un archivo de configuración. | [B.4 Alertas] usa la severidad sin definirla. |
| SUP-08 | Alertas por Redis Stream, mostradas en el dashboard. Sin canales externos. | [B.4 Alertas] exige asincronía, no un canal. Evita agregar dependencias. |
| SUP-09 | Reporte en JSON por API, con vista en el dashboard. | [B.4] define el contenido, no el formato. |
| SUP-10 | Permisos: analista crea y consulta sus casos; supervisor además consulta todos, cancela y verifica custodia; administrador además gestiona usuarios. | [B.5 M4] define los roles mínimos, no sus permisos. |
| SUP-11 | Video: se extraen audio y fotogramas con FFmpeg, que van a los workers de audio e imagen. Documento: `.txt` va al worker de texto; otros formatos solo se almacenan y custodian. | [B.1] y [B.3] incluyen video y documentos; [B.4] solo obliga workers de texto, imagen y audio. |
| SUP-12 | Sub-tarea: un archivo multimedia o un lote de mensajes de tamaño configurable. | Un lote acotado permite cancelar y planificar con granularidad fina. |
| SUP-13 | Deduplicación a nivel de archivo; los chunks son solo unidad de transferencia. | [B.5 M3] no fija el nivel. Evita que la tasa de deduplicación dependa del tamaño de chunk comparado. |
| SUP-14 | Política OOM: reencolar con reserva de memoria aumentada, sin consumir intentos normales, hasta 2 veces; luego falla con causa `oom`. | [B.5 M1] exige una política definida, sin fijarla. |
| SUP-15 | Normalización a esquema canónico (`timestamp` UTC ISO 8601, `sender`, `text`, UTF-8). | Práctica Clean Data; necesaria para la línea temporal de [B.4 Reporte consolidado]. |
| SUP-16 | Bibliografía de las fichas: Silberschatz, Galvin y Gagne, *Operating System Concepts*, 10.ª ed. | [Anexo 2] exige autor y capítulo sin fijar libro. Confirmar con el programa del curso. |
| SUP-17 | Los parámetros sin valor en el documento (aging, márgenes, chunk) se calibran midiendo. | Ningún umbral numérico de rendimiento aparece en B.5 o B.6. |
| SUP-23 | **Aprobado en el plan de F-16 por José Andrés Loría Herrera (2026-11-10):** límites y reserva se configuran explícitamente; el lector/preflight rechaza capacidad ilimitada, datos ausentes o inválidos sin continuar silenciosamente. No se fija valor numérico por defecto. | [B.5 M1] exige límites pero no define el comportamiento ante configuración inválida; AD-29 establece impedir un arranque sin presupuesto verificable. Su cableado corresponde a la parte 2 de F-16. |
| SUP-25 | **Aprobado en el plan de F-19 por José Andrés Loría Herrera (2026-11-10):** comparación inicial de estrategias sobre Whisper CPU de F-09, con N=1/N=2, cinco repeticiones, un hilo por proceso y timeout externo de 120 s; no generaliza resultados a otros modelos ni acredita sus huellas. La compatibilidad real tras fork se valida en Linux antes de declarar listo el cargador; si falla, se solicita decisión humana. | [B.5 M1] pide comparación sin fijar modelo ni parámetros; US-19 depende de F-09. AD-07 conserva elección provisional hasta medir. |
| SUP-30 | **Provisional:** la KEK es un secreto de 32 bytes por nodo, leído de `KEK_FILE` (archivo fuera del repositorio) o de `KEK` en base64 solo en desarrollo. Todos los nodos pueden compartir el mismo valor porque leen los mismos objetos. La rotación de la KEK queda fuera de alcance. | El enunciado exige cifrado en reposo [B.5 M4] pero no fija el origen ni la distribución de la llave; AD-16 prohíbe llaves en el código. Cómo llega la KEK a los tres nodos es decisión operativa de F-38. |
| SUP-18 | Reporte y alertas se asignan a H2 y H3 respectivamente, y el dashboard a H3. | La sección 2 de Parte I no los asigna a un hito. |
| SUP-20 ⚠ | La bitácora de IA se llama `docs/BITACORA_IA.md`. | Decisión del equipo. [Parte I §4] y [Anexo 3] la nombran `docs/bitacora_ia.md`; confirmar con el profesor que el cambio de nombre es aceptable. |
| SUP-19 ⚠ | Las deficiencias de RNF-03 se toman de `docs/DECISIONES_DISENO.md` del I Proyecto. | No se encontró la retroalimentación de la evaluación; solo limitaciones autodeclaradas. |
| SUP-21 | Las instrucciones de despliegue las valida Kenni Rodriguez, integrante y líder, en vez de la persona externa que pide el criterio de RNF-22. **Límite: Kenni no es externo y es responsable de F-38**, así que la validación no es independiente y puede pasar por alto pasos implícitos. | [B.8] solo pide «instrucciones de despliegue distribuido» y no menciona a nadie externo: ese requisito es un añadido de RNF-22, no del enunciado. Decisión de Kenni Rodriguez. |
| SUP-22 | «Contenido sensible» en imagen son las clases del detector listadas en `config/imagen.toml`; inicialmente solo `knife` → `arma`, porque es la única clase de COCO que es un arma. No se detectan armas de fuego ni desnudez. | [B.4 Workers de análisis] pide detectar «contenido sensible» sin definirlo, y [B.1] prohíbe entrenar un modelo para otras clases. Aprobado por José Andrés con el plan de F-08. Con YOLO11n, `umbral_minimo` se mantiene en 0.25 tras la tabla de F-08 (SUP-17), por decisión de José Andrés, para no calibrar con la misma muestra con que se mide. |
| SUP-26 | La verdad de referencia mínima de B.3 («al menos una muestra») se cumple con la muestra etiquetada de imágenes del manifiesto de F-03 (`positivo` → `{categoria}`, `neutro` → `{}`). Texto y audio se agregan solo si existen etiquetas con procedencia y licencia declaradas. | [B.3 Dataset mínimo] pide etiquetas esperadas «para al menos una muestra» sin fijar el tipo. Las imágenes sintéticas validan el mecanismo, no la calidad de un modelo. Plan de F-04 (Kenni Rodriguez). |
| SUP-27 ⚠ | **Provisional, decisión de la persona pendiente:** orígenes admitidos `sintetico`, `propio` y `publico`; licencia en blanco o de relleno (`desconocida`, `ninguna`, `sin licencia`, `n/a`, `-`) se rechaza; una fuente `publico` exige una de `CC0-1.0`, `CC-BY-4.0`, `CC-BY-SA-4.0`, `MIT`, `Apache-2.0`. | [B.3 Consideraciones éticas] exige declarar procedencia y licencia que permita su uso académico, sin enumerar licencias. La lista la confirma la persona. |
| SUP-28 | **Provisional, decisión de la persona pendiente:** matriz de permisos de F-26: analista crea y consulta casos; supervisor consulta, cancela y ve monitoreo; administrador hace todo eso; `servicio` solo reporta subtareas. Los tokens expiran a los 60 min por defecto. | [B.5 M4] fija solo los roles mínimos (analista, supervisor, administrador), sin permisos ni expiración. Es interpretación del arquitecto, no verificada contra el enunciado. Ver AD-33 y `src/domain/rbac.py`. |
| SUP-29 | **Provisional, decisión de la persona pendiente:** `GET /health` es pública, sin token. | Permite sondas de despliegue; no expone datos de casos. [B.5 M4] no la menciona. Ver AD-33. |
| SUP-31 | El enunciado no fija el algoritmo, la llave ni el ancla de la cadena de custodia. Se asume HMAC-SHA-256, llave de 32 bytes en `CUSTODY_KEY_FILE`, ancla en un archivo junto al log y un solo escritor. **Límites:** quien tenga la llave puede forjar la cadena; reponer un ancla antigua junto con un log truncado al mismo punto no se detecta mientras el ancla viva en el mismo disco; el adaptador escribe un ancla génesis (`seq` 0) al crear el log y, al ser determinista por llave, una copia de ella oculta el truncado de un log de N entradas a 0 o 1 (alternativa no hecha: atarla a un nonce del log); `record` solo verifica las últimas 2 líneas y el ancla, y una línea intermedia manipulada solo la detecta el verificador completo. Provisional (AD-35). | [B.5 M4] pide cadena de custodia con hash encadenado y log de solo-anexión, sin precisar algoritmo ni ubicación de la llave. |
| SUP-32 | Los workers corren con UID fijo `10001:10001`, raíz de solo lectura, `cap_drop: [ALL]` y `no-new-privileges:true`. Provisional. | US-30 pide UID distinto de 0, raíz de solo lectura y sin capacidades; `no-new-privileges` se añade porque impide la escalada por binarios setuid. Un UID fijo hace el chequeo reproducible en los tres nodos. |
| SUP-33 | Parámetros de demo de TLS (provisional): CA de 365 días, certificado de servidor de 90 días, claves EC P-256, API en 8443, Redis en 6380 con el 6379 cerrado, `TLS_ENABLED` activo por defecto (seguro por defecto, como `AUTH_ENABLED`); `TLS_ENABLED=false` solo explícito y con aviso en el registro. | El enunciado exige TLS entre nodos [B.5 M4] pero no fija validez, algoritmo ni puertos; los puertos coinciden con `docs/IMPLEMENTACION.md` §5. Sin renovación automática: a los 90 días se regenera. Decisión provisional del orquestador (F-27); AD-37. |
| SUP-34 | **Provisional (plan de F-13, pendiente de aprobación):** «incidencia» es un hallazgo de severidad `ALTA`, una sub-tarea `failed` (con su `error_type`), una evidencia sin fuente en el catálogo o sin objeto en el almacén, o una posición no reconocida. «Resuelve a su fuente y timestamp» es que el fragmento nombra el objeto (`sha256`, `file_path`, tipo) y lleva la hora UTC del mensaje o el tramo en segundos del audio. Imagen y audio no tienen hora absoluta: van en `sin_marca_absoluta` con `timestamp_utc: null`, sin inventarla. | [US-13] pide incidencias y fragmentos que resuelvan a fuente y timestamp sin definirlos; confirmar con F-14, que reutiliza la severidad. Ver AD-38. |
| SUP-35 (provisional) | «Incidencia alta» es un `Finding` de severidad `ALTA` (la asignada por F-07 a F-09); «una alerta por cada evento» es una por hallazgo alto agregado al almacén y una por el cierre del caso (`completed`, `partially_completed`, `failed`; `cancelled` no alerta); «consumidor» es quien lee el Stream; «el pipeline continúa» incluye que falle el canal de alertas; «visible en el dashboard» se acredita con `GET /alerts` mientras la vista de Melany no exista. | [B.4 Alertas] pide notificar incidencias altas y el cierre sin definir esos términos. Alternativa descartada: recalcular severidad en el módulo de alertas (duplica umbrales). Ver AD-39. |
| SUP-36 | **Provisional:** «carga superior a la memoria disponible» es una huella total de las sub-tareas encoladas ≥ 2 × (`memory.max` × (1 − margen)). El factor 2 es configurable y criterio propio; Medición pendiente. | [B.5 M1] y US-37 piden carga superior a la memoria sin definir cuánto; ver AD-41. |
| SUP-37 | **Provisional:** «heartbeats no se interrumpen» es que ningún intervalo entre heartbeats consecutivos supera 3 × `HEARTBEAT_INTERVAL` durante la saturación. «Admite solo lo que cabe» es que en ninguna muestra `memory.current` supera `memory.max` ni hay `OOMKilled`. «Terminan» es que todas las sub-tareas llegan a estado terminal antes del plazo de la corrida. El 3 es criterio propio; Medición pendiente. | US-37 no define «interrumpen», «solo lo que cabe» ni «terminan»; ver AD-41. |
| SUP-38 | La comparación sin control de admisión se hace solo si la persona confirma que el worker de prueba está aislado y que un OOM no afecta a otro nodo; si no, se declara «no realizada». | Provocar un OOM puede afectar el nodo; el enunciado no autoriza hacerlo sin aislamiento; ver AD-41. |
| SUP-39 | **Provisional:** se asume que `retrying→processing` y `queued→cancelled` son transiciones válidas; `completed`, `partially_completed`, `failed` y `cancelled` son terminales. | US-10 no define la tabla completa de transiciones; ver AD-43. |
| SUP-40 | **Provisional:** el tipo de una fuente se decide por extensión, sin distinguir mayúsculas: texto `.txt`, `.csv`, `.json`; imagen `.jpg`, `.jpeg`, `.png`; audio `.mp3`, `.wav`, `.flac`, `.ogg`, `.m4a`, `.aac`, `.opus`, `.wma`; video `.mp4`, `.mkv`, `.avi`, `.mov`, `.webm`, `.flv`, `.wmv`, `.m4v`. Una extensión desconocida lanza `ValueError`. | El enunciado no fija los formatos; las de audio y video cubren las de `src/coordinator/router.py`. F-02 puede fijar los formatos de chat admitidos; ver AD-46. |
| SUP-41 | **Provisional:** los documentos adjuntos quedan fuera del alcance de la descomposición. | [B.4] pide routing para texto, imagen, audio y video; una extensión de documento se rechaza con `ValueError`; ver AD-46. |
| SUP-42 | **Provisional:** el id de sub-tarea es `{case_id}:{sha256}:{kind}`. | Es determinista y trazable a caso, fuente y tipo (RF-04, RF-05); ver AD-46. |
| SUP-43 | **Provisional:** la misma fuente repetida en un caso produce una sola sub-tarea. | Evita duplicar evidencia idéntica y permite reintentar sin duplicar; ver AD-46. |
| SUP-44 | Un timestamp sin huso horario explícito en una exportación de WhatsApp o Telegram se interpreta como UTC. | No hay dato en el archivo que permita detectar el huso real; el dataset sintético de F-03 ya se genera en UTC. Exportaciones reales en otro huso deben convertirse antes de ingresar; ver AD-48. |
| SUP-46 | **Provisional:** «concurrente» significa concurrencia de envío ≥ número de casos (mínimo 20), para que todos estén en vuelo a la vez. «Estado final» es `FINISHED_STATUSES` de `scripts/submit_case.py` (`completed`, `partially_completed`, `failed`, `cancelled`); un caso `failed` cuenta como final (límite declarado: el veredicto no lo reporta aparte). «Tres nodos activos» son tres `host` distintos con sub-tareas procesadas o visibles en `series`. El plazo de la corrida es el `--timeout` de `run_load`. | El enunciado pide «al menos 20 casos concurrentes» sin precisar el grado de concurrencia ni qué es un estado final; ver AD-50. |
| SUP-45 | **Provisional:** N, el máximo configurable de reintentos, es el número total de intentos de la sub-tarea, igual que `attempts < max_attempts` en `recovery.py`. Con N = 3 hay 1 intento inicial y 2 reintentos, el tercer fallo marca `failed` y hay N − 1 esperas. | RF-11 y [B.4] piden un «número máximo configurable» sin precisar si cuenta el intento inicial; reutilizar la semántica de `recovery.py` evita dos límites distintos; ver AD-48. |
| SUP-47 | **Provisional:** una fuente `.csv` se admite en la descomposición (SUP-40) pero no tiene parser; su sub-tarea de texto falla de forma permanente con un mensaje legible. No se amplía el alcance. | El enunciado no define un formato de exportación CSV y lo que no pide no entra al alcance; `classify_source` no cambia y `src/adapters/parser_por_extension.py` rechaza la extensión con `ExtensionSinParser`; ver AD-51. |
| SUP-48 | **Provisional, Medición pendiente:** muestreo de video: un fotograma cada `FRAME_EVERY_S=5` segundos y como máximo `FRAME_MAX=20` fotogramas, ambos configurables y validados (> 0). Sin dato medido que los fundamente. | Acota el costo de CPU y memoria de un video grande (RF-22) y es ajustable sin cambiar código; los valores no se midieron; ver AD-52. |
| SUP-49 | **Provisional:** un video sin pista de audio no es un error: su sub-tarea AUDIO termina `completed` sin hallazgos. El video se identifica por la extensión de la fuente y la ausencia de pista se comprueba con `ffprobe`. | Un video mudo es una entrada válida y marcarlo `failed` degradaría el caso sin causa real; ver AD-52 y SUP-11. |
| SUP-50 | **Provisional:** clasificación de fallos del worker tipado (`src/workers/fallos.py`). Transitorios, con reintento y espera: `TimeoutError`, `MemoryError`, `BlockingIOError`, `InterruptedError`, `PermissionError`, `ConnectionError`, `urllib3.exceptions.HTTPError`, `minio.error.S3Error` con estado 5xx y `KeyUnavailable`. Todo lo demás es permanente (`failed` de inmediato), incluidos `ValueError`, `FormatoDeChatInvalido`, `ExtensionSinParser`, `UnicodeDecodeError`, `KeyError`, `DecryptionError`, SHA-256 distinto y cualquier `ProcessingError` de FFmpeg. | Extiende la lista de F-11 con los fallos de red y de llave que el camino tipado puede ver; lo no clasificado es permanente para no repetir N veces un error de lógica; ver AD-49 y AD-51. |
| SUP-51 | **Provisional:** el límite de intentos N (SUP-45) se aplica al reclamar: una sub-tarea que llega a N reclamos sin reportar falla con `WorkerLostError`, igual que `recover_subtask` en el camino heredado. | `reencolar_huerfanas` no cuenta intentos y una sub-tarea que mata al worker (por ejemplo por OOM) volvería a la cola indefinidamente; ver AD-51. |

## 4. Discrepancias detectadas al contrastar con el documento

| Tema | Encargo | Documento | Tratamiento |
|---|---|---|---|
| Nodos | «tres nodos» | «tres nodos **worker**» [B.2] | Se aplica lo más estricto: los tres ejecutan workers. |
| Umbrales | «umbrales de evidencia» | Solo mínimos de cantidad, sin objetivos de rendimiento | Se usan esos mínimos; no se inventan objetivos numéricos. |
| SIGTERM y normalización | Prácticas de código limpio | No son requisitos del documento | Son reglas de diseño (`ARQUITECTURA.md` §9), no RF. |
| Duración | Entrega 04/nov/26 | «3 semanas» y 14 días | Entrega real 10/nov/26. Ver SUP-02 y SUP-03. |

## 5. Trazabilidad

| Sección | Requisitos |
|---|---|
| B.1 | RF-01, RF-13, RNF-25 |
| B.2 | RNF-01, RNF-02, RNF-03 |
| B.3 | RF-18 a RF-23, RNF-04, RNF-05, RNF-06 |
| B.4 | RF-01 a RF-17 |
| B.5 M1 | RF-24 a RF-27, RF-46, RNF-09 |
| B.5 M2 | RF-28 a RF-30, RNF-10 |
| B.5 M3 | RF-31 a RF-34, RNF-11 |
| B.5 M4 | RF-35 a RF-39, RNF-07, RNF-08, RNF-12 |
| B.5 M5 | RF-40, RF-41, RNF-13 |
| B.6 | RF-42 a RF-46, RNF-15 |
| B.7 | Sugerencias, no requisitos. Se usan como referencia en `ARQUITECTURA.md`. |
| B.8 | RNF-02, RNF-06, RNF-14, RNF-15, RNF-22, RNF-23 |
| B.9 | RNF-02, RNF-15, RNF-16, RNF-19 |
| B.10 | RNF-01, RNF-06, RNF-17, RNF-23 |
| Parte I | RNF-14, RNF-17 a RNF-21, RNF-23, RNF-24 |
| Anexos 1, 2, 3 | RNF-17, RNF-14, RNF-19 |
