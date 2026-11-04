**IC-6600 · PRINCIPIOS DE SISTEMAS OPERATIVOS**

*Instituto Tecnológico de Costa Rica — Campus San Carlos · II Semestre 2026*

**II Proyecto Programado**

Enunciado con dos alternativas

|  | Alternativa A — Vocación académica | Alternativa B — Vocación profesional |
| :---- | ----- | ----- |
| Proyecto | **Construcción de una distribución personalizada de Linux sobre Arch** | **Plataforma distribuida de análisis de datos de mensajería: memoria, E/S, almacenamiento y seguridad** |
| Naturaleza | Configuración e instrumentación del sistema operativo “desde adentro”: instalación manual, kernel, arranque, servicios, memoria, sistema de archivos, dispositivos y seguridad. | Ingeniería de una infraestructura distribuida “desde afuera”: administración de memoria, planificación, E/S, almacenamiento y protección de cargas de trabajo pesadas. |
| Entregable central | Repositorio de dotfiles, scripts, unit files y documentación, reproducible en la máquina de cada integrante. | Sistema distribuido funcional (mínimo 3 nodos), repositorio de código, informe de pruebas y documentación. |
| Unidades del curso que moviliza | Todas, con énfasis en 2 (componentes del SO), 4–9 (procesos, planificación, IPC), 10–15 (memoria, E/S, archivos, protección). | Con énfasis en 10–15 (memoria, E/S, archivos, protección), sobre la base de 4–9 trabajada en el I Proyecto. |

| Aspecto | Definición |
| :---- | :---- |
| Modalidad | En equipo. Se mantienen **los mismos equipos del I Proyecto Programado**. |
| Duración | 3 semanas, del **21/oct/26** al **04/nov/26**. |
| Elección de alternativa | Cada equipo elige **una** alternativa y la registra a más tardar el **22/oct/26 en el Telegram, tópico II Proyecto**. La elección no puede cambiarse después. |
| Valor | Forma parte del rubro **Proyectos Programados** del programa del curso. |

| 📝 Equivalencia de exigencia Las dos alternativas tienen el mismo nivel de exigencia y comparten el mismo marco de evaluación (Parte I): la misma escala 0–5, los mismos rubros comunes, la misma política de IA y la misma defensa oral individual. Ninguna alternativa es la “fácil”: A exige profundidad en el funcionamiento interno del sistema operativo; B exige profundidad en la administración de recursos de un sistema distribuido real. Elijan según el tipo de problema que les interese resolver, no según la carga de trabajo que perciban. |
| :---- |

# **Parte I · Marco común a ambas alternativas**

Esta parte aplica a todos los equipos, sin importar la alternativa elegida. Las Partes II y III detallan los requisitos técnicos específicos de cada alternativa.

## **1\. Propósito**

El I Proyecto Programado se centró en la gestión de procesos, la concurrencia, la planificación y la comunicación entre procesos en un entorno distribuido. El II Proyecto lleva esa base hacia la segunda mitad del curso —**gestión de memoria, entrada/salida, sistemas de archivos, protección y seguridad**— y exige que cada decisión técnica se sostenga con **evidencia medible**, no solo con una descripción.

Ambas alternativas comparten una premisa: en un contexto donde la IA puede producir con facilidad configuraciones, código y documentación, el valor del proyecto está en **demostrar que el equipo entiende lo que construyó**: por qué funciona, cómo se comporta bajo carga y qué concepto de Sistemas Operativos lo explica.

## **2\. Calendario y hitos**

El proyecto dura tres semanas y se organiza en tres hitos. Los hitos 1 y 2 son **controles de avance**: no tienen nota propia, pero se verifican en el historial del repositorio y su cumplimiento se considera en el rubro común *Documentación técnica y repositorio*.

| Hito | Fecha | Alternativa A — Distro | Alternativa B — Plataforma |
| :---- | :---- | :---- | :---- |
| **H1** · Base funcionando | Fin de semana 1 | Instalación manual completa en la máquina de cada integrante; DE/WM funcionando; repositorio creado; temas de la Capa 2 elegidos; matriz de responsabilidades. | Declaración de reutilización del I Proyecto; arquitectura actualizada; dataset sintético construido; pipeline base procesando texto, imagen y audio; matriz de responsabilidades. |
| **H2** · Núcleo de SO | Fin de semana 2 | Al menos 4 temas de la Capa 2 implementados con su ficha de evidencia; script de bootstrap funcional. | Módulos M1, M2 y M3 implementados con mediciones preliminares; estados, reintentos y cancelación funcionando. |
| **H3** · Entrega final | Fin de semana 3 | Los 7 temas, Capa 3 completa, reproducibilidad demostrada, informe final, demo y defensa. | Módulos M4 y M5, pruebas de carga y tolerancia a fallos, informe final, demo y defensa. |

## **3\. Organización del equipo y responsabilidad individual**

Cada equipo debe entregar una **matriz de responsabilidades** (docs/responsabilidades.md, plantilla en el Anexo 1\) que indique qué integrante es **responsable principal** de cada tema o módulo técnico. Todo integrante debe ser responsable principal de al menos los componentes que indique su alternativa (Parte II o III).

* El responsable principal de un componente debe poder explicarlo, modificarlo en vivo y defenderlo sin apoyo de sus compañeros.

* El historial de Git debe reflejar la matriz: se espera ver contribuciones de cada integrante en los componentes que declaró, distribuidas a lo largo de las tres semanas.

* Un historial con uno o pocos commits masivos al final del proyecto se considera evidencia insuficiente de proceso.

## **4\. Uso de Inteligencia Artificial: se declara y se documenta**

Se mantiene el modelo del curso: la IA **no se prohíbe, se declara y se documenta**. Puede usarse como tutor, como apoyo para depurar, para explorar alternativas técnicas o para generar datos sintéticos de prueba. No puede sustituir la comprensión del equipo: todo artefacto entregado (configuración, script, código, texto) debe poder ser explicado por su responsable.

### **Bitácora de uso de IA**

Cada equipo mantiene docs/bitacora\_ia.md con el formato del Anexo 3\. Requisitos mínimos:

* Al menos **una entrada por cada tema o módulo técnico** en el que se haya usado IA, registrada por su responsable principal.

* Cada entrada indica: herramienta, propósito, consulta resumida, qué se obtuvo, **qué se validó, corrigió o descartó** y **cómo se validó** (comando ejecutado, documentación oficial consultada, prueba realizada).

* Debe incluir al menos **dos casos documentados de error o imprecisión de la IA** detectados por el equipo y cómo los resolvieron. Una bitácora donde la IA “nunca se equivocó” se considera poco creíble.

* Si un equipo declara no haber usado IA en algún componente, lo indica explícitamente en la bitácora.

## **5\. Evidencia cuantitativa obligatoria**

Cada tema (Alternativa A) o módulo (Alternativa B) debe acompañarse de una **ficha de evidencia** en docs/ (plantilla en el Anexo 2\) con cinco elementos:

| Elemento | Contenido esperado |
| :---- | :---- |
| 1\. Qué se implementó | Descripción concreta de la configuración, script o componente, con ruta en el repositorio. |
| 2\. Concepto de SO | Qué concepto del curso queda demostrado y en qué capítulo de la bibliografía se sustenta. |
| 3\. Método de medición | Herramienta y comando exactos usados para medir (reproducibles por cualquier persona). |
| 4\. Resultados | Datos medidos en tabla o gráfico; cuando aplique, comparación antes/después o entre alternativas. |
| 5\. Interpretación | Qué dicen los datos, si coinciden con la teoría y, si no, por qué. |

| ⚠️ Regla de evidencia Un tema o módulo implementado sin ficha de evidencia con datos medidos se califica con un máximo de 2 (Básico) en la escala 0–5, aunque funcione. Las capturas de pantalla aisladas no sustituyen la medición; deben acompañarse del comando y de la interpretación. |
| :---- |

## **6\. Demostración y defensa oral individual**

La evaluación final incluye una sesión por equipo con dos partes:

* **Demostración (equipo):** el sistema funcionando, en vivo, sobre el entorno real del equipo. No se aceptan videos pregrabados como sustituto de la demostración.

* **Defensa oral (individual):** cada integrante responde preguntas **no ensayadas** sobre los componentes de los que es responsable principal y al menos una pregunta sobre un componente de otro integrante. La defensa puede incluir **tareas en vivo**, por ejemplo: modificar una configuración y mostrar su efecto, interpretar un log, provocar una falla y explicar la reacción del sistema.

La nota del rubro *Defensa oral individual* es **individual**. Además, si un integrante no logra explicar un componente del que se declaró responsable principal, la calificación de ese componente **se ajusta para ese integrante**.

## **7\. Entregables comunes**

* **Repositorio Git** (público o compartido con el profesor y el asistente) con historial completo.

* **README.md** con descripción (texto e imágenes), requisitos, instrucciones de instalación o despliegue y mapa del repositorio.

* Carpeta **docs/** con: fichas de evidencia, matriz de responsabilidades y bitácora de IA.

* **Informe final** en PDF (máximo 20 páginas sin anexos) que integre decisiones técnicas, resultados de mediciones, limitaciones encontradas y lecciones aprendidas. Se nombra según la convención de nombres del curso.

* Los entregables específicos de cada alternativa se detallan en las Partes II y III.

## **8\. Escala de desempeño y cálculo de la nota**

Cada rubro se califica con la misma escala 0–5 del I Proyecto. La nota del rubro se obtiene como (puntaje / 5\) × peso del rubro.

| Nivel | Descripción |
| :---- | :---- |
| 0 – Nulo | El aspecto no fue implementado ni considerado. |
| 1 – Deficiente | Implementación incompleta, con múltiples errores y sin cumplir el objetivo. |
| 2 – Básico | Implementación funcional mínima, sin profundidad, sin robustez o sin evidencia medida. |
| 3 – Aceptable | Cumple lo requerido, con evidencia, aunque con margen de mejora técnica o conceptual. |
| 4 – Bueno | Implementación clara y robusta, evidencia sólida e interpretación correcta. |
| 5 – Sobresaliente | Excelente implementación, evidencia rigurosa, interpretación profunda y alineada con los principios del curso. |

**Rubros comunes (35 %)**, idénticos en ambas alternativas:

| Rubro común | Peso | Qué se evalúa |
| :---- | :---- | :---- |
| Documentación técnica y repositorio | 10 % | Calidad del README, fichas de evidencia, informe final, organización del repositorio, historial de commits coherente con la matriz de responsabilidades y cumplimiento de los hitos H1 y H2. |
| Defensa oral individual | 15 % | Dominio individual de los componentes propios y del sistema en conjunto; capacidad de responder preguntas no ensayadas y de ejecutar tareas en vivo. |
| Bitácora de uso de IA | 10 % | Completitud, honestidad y valor crítico de la bitácora: qué se validó, corrigió o descartó y cómo; errores de la IA detectados por el equipo. |

El **65 % restante** corresponde a los rubros técnicos propios de cada alternativa (secciones A.8 y B.9).

## **9\. Integridad académica**

* Se permite reutilizar código o configuraciones de terceros (proyectos open source, documentación oficial, Arch Wiki) siempre que se **cite la fuente** en el código y en la documentación.

* No se permite compartir implementaciones entre equipos. Similitudes sustanciales no justificadas entre entregas se tratarán según el reglamento institucional.

* En la Alternativa B, la reutilización del propio I Proyecto está permitida y regulada (sección B.2).

# **Parte II · Alternativa A — Distribución personalizada de Linux sobre Arch**

## **A.1 Descripción general**

Cada equipo construirá su propia **distribución personalizada de Linux** partiendo de una instalación base de Arch Linux realizada manualmente. Sobre esa base instalará y configurará un entorno de escritorio o gestor de ventanas (DE/WM) y aplicará un conjunto de configuraciones, herramientas y servicios propios que demuestren comprensión práctica —y medida— de los conceptos del curso.

El proyecto combina una **base común obligatoria**, para que todos los equipos trabajen sobre los mismos fundamentos de Sistemas Operativos, con un espacio amplio de **personalización**, de forma que cada distro resultante sea distinta. No se solicita generar ni empaquetar una imagen ISO instalable: el foco está en la configuración, los scripts, la instrumentación y la comprensión del sistema.

## **A.2 Entorno de trabajo**

* Se recomienda trabajar en **máquina virtual** (QEMU/KVM con virt-manager, VirtualBox o VMware). Se permite instalación en hardware real bajo responsabilidad del equipo.

* La máquina debe arrancar en **modo UEFI** (no BIOS heredado), para que el proceso de arranque estudiado corresponda al de los equipos actuales.

* Recursos mínimos sugeridos por VM: 2 vCPU, 4 GB de RAM y 30 GB de disco.

* Se recomienda tomar **snapshots** de la VM antes de pasos riesgosos (bootloader, particionamiento, sistema de archivos).

* **Cada integrante mantiene su propia instalación.** El equipo comparte un único repositorio, que debe poder aplicarse sobre la instalación de cualquier integrante.

## **A.3 Capa 1 — Base común de instalación (obligatoria)**

| Requisito | Detalle y evidencia exigida |
| :---- | :---- |
| Instalación manual de Arch | Particionamiento, formato, montaje, pacstrap, fstab, chroot, locale, bootloader, kernel e initramfs, realizados a mano. **No se acepta** archinstall ni scripts de instalación de terceros. Evidencia por integrante: lsblk \-f, /etc/fstab, bootctl status o efibootmgr \-v, journalctl \--list-boots. |
| Bitácora de instalación | Documentación paso a paso (docs/instalacion.md) que explique **por qué** se ejecuta cada comando, no solo cuál. Debe registrar al menos los problemas encontrados y cómo se resolvieron. |
| DE/WM justificado | Elección libre (GNOME, KDE Plasma, Hyprland, Sway, i3, dwm, etc.), justificada por escrito **con datos**: consumo de memoria en reposo y número de procesos del DE/WM elegido comparados con al menos una alternativa (free, smem o ps). |
| Sistema de init | systemd como sistema de init, o justificación técnica documentada si se usa una alternativa (OpenRC, runit, s6) y adaptación de los requisitos que dependan de systemd. |
| Reproducibilidad | Un script de bootstrap (p. ej. install.sh) que, sobre una instalación base limpia, instale los paquetes (pkglist.txt), enlace los dotfiles, habilite los servicios y deje la distro operativa. **Cada integrante debe aplicarlo en su propia instalación** y adjuntar el log de ejecución. El script debe ser idempotente: ejecutarlo dos veces no debe romper el sistema. |

## **A.4 Capa 2 — Requisitos técnicos ligados a Sistemas Operativos**

Es el núcleo del proyecto. Cada tema conecta directamente con contenidos del curso. El equipo debe **implementar 7 de los 9 temas** siguientes, y **cada integrante debe ser responsable principal de al menos 2 temas**. Cada tema elegido requiere su ficha de evidencia (Parte I, sección 5).

| Tema de SO | Requisito concreto | Evidencia mínima exigida |
| :---- | :---- | :---- |
| 1\. Procesos y planificación | Herramienta propia que liste procesos con PID, PPID, estado, valor *nice*, política de planificación (SCHED\_OTHER, SCHED\_FIFO, SCHED\_RR, SCHED\_IDLE) y uso de CPU, y que permita modificar prioridad y política. Identificar el planificador del kernel en uso (EEVDF en kernels ≥ 6.6) y explicar su funcionamiento. | Experimento: dos o más procesos CPU-bound fijados al mismo núcleo (taskset) con distintos valores *nice*; medir la proporción de CPU obtenida y compararla con la tabla de pesos del kernel. Repetir con una política de tiempo real y explicar la diferencia. |
| 2\. Memoria | Configurar swap (partición o archivo) **y** zram (zram-generator), con prioridades justificadas. Herramienta propia en tiempo real que muestre memoria física, swap, zram (tasa de compresión) y fallos de página *minor*/*major* por proceso. | Provocar presión de memoria (stress-ng \--vm) y registrar si/so de vmstat, fallos de página y uso de zram, con y sin zram activo. Explicar paginación por demanda, swapping y el comportamiento observado del OOM killer si se activa. |
| 3\. Sistema de archivos | Usar como raíz un sistema de archivos distinto de ext4 (btrfs, XFS, ZFS, F2FS, bcachefs) y justificar ventajas y desventajas. Si es btrfs o ZFS: esquema de subvolúmenes/datasets y snapshots automáticos. | Benchmark con fio frente a ext4 (en partición o imagen *loop*) en al menos dos cargas: secuencial y aleatoria de 4 KiB. Si aplica: demostración en vivo de snapshot y *rollback* tras un cambio destructivo. |
| 4\. Gestión de servicios | Al menos un servicio systemd propio (unit file) que automatice algo útil, con dependencias (After=, Wants=), política de reinicio y **límites de recursos** (CPUQuota=, MemoryMax=), más un *timer* o activación por socket. | Evidenciar con systemctl status, journalctl \-u y systemd-cgls que el servicio corre en su cgroup; demostrar que el límite de recursos se aplica (el servicio no supera la cuota bajo carga) y que se reinicia tras una falla provocada. |
| 5\. Concurrencia e IPC | Mini-programa propio (C, Rust, Go o Python) que resuelva un problema concreto con un esquema productor/consumidor usando **al menos dos** mecanismos de IPC (pipes, FIFOs, señales, sockets Unix, memoria compartida) y sincronización explícita. Debe manejar SIGTERM/SIGCHLD sin dejar procesos zombie. | Traza con strace \-f que muestre las llamadas al sistema relevantes (fork, pipe, socket, kill, etc.) y su interpretación; evidencia con ps de que no quedan zombies; prueba de condición de carrera evitada. |
| 6\. Gestión de paquetes | Documentar el funcionamiento interno de pacman: base de datos local, resolución de dependencias, verificación de firmas y hooks de ALPM. Crear **un hook propio** útil y **empaquetar** con PKGBUILD/makepkg al menos uno de los comandos propios de la Capa 3\. | Log que muestre el hook ejecutándose en una transacción real; pacman \-Qi y pacman \-Ql del paquete propio; explicación del árbol de dependencias de un paquete elegido (pactree). |
| 7\. Proceso de arranque | Explicar y demostrar el flujo completo: firmware UEFI → bootloader (systemd-boot o GRUB) → kernel → initramfs (hooks de mkinitcpio) → systemd (targets) → login. | systemd-analyze, blame y critical-chain; **una optimización medida** del tiempo de arranque (antes/después). Demostración en vivo de arranque en rescue.target o emergency.target mediante parámetros del kernel. |
| 8\. E/S y dispositivos | Inspeccionar, cargar y descargar módulos del kernel (lsmod, modinfo, modprobe), crear una lista negra justificada y **una regla udev propia** que reaccione a la conexión de un dispositivo ejecutando una acción. Identificar el driver de la GPU (y de la NPU, si existe) y explicar su rol. | udevadm monitor y dmesg durante la conexión del dispositivo; /proc/interrupts antes/después de una operación de E/S intensiva; lspci \-k con interpretación. **Conexión con Unidad 1** (CPU/GPU/NPU). |
| 9\. Protección y seguridad | Usuarios y grupos con privilegio mínimo, sudoers restringido por comando, permisos y ACL sobre un directorio compartido, firewall nftables con política de denegación por defecto y endurecimiento de SSH. Opcional: perfil AppArmor. | **Pruebas negativas**: accesos denegados documentados; nft list ruleset interpretado; escaneo con nmap desde otra máquina o VM mostrando solo los puertos permitidos. |

| 🔗 Conexión con Unidad 1 La distro debe hacer visible la heterogeneidad de cómputo estudiada al inicio del curso: el comando obligatorio de la Capa 3 reporta CPU, GPU y NPU (si existe) con el driver que controla cada una, y el tema 8 explica cómo el sistema operativo expone esos dispositivos mediante módulos del kernel, sysfs e interrupciones. |
| :---- |

## **A.5 Capa 3 — Personalización: comandos y atajos propios**

### **Comandos de terminal**

* **Obligatorio:** un comando propio (nombre libre, p. ej. midistro-info) que muestre información del sistema obtenida **directamente** de /proc, /sys y llamadas al sistema: kernel, uptime, CPU (modelo y núcleos), GPU y NPU con su driver, memoria/swap/zram, procesos activos, planificador y sistema de archivos raíz. **No se acepta** un envoltorio de neofetch, fastfetch o herramientas equivalentes. Debe apoyarse en lo implementado en la Capa 2\.

* **Libres:** al menos **2 comandos por integrante** (mínimo 6 por equipo), inventados por el equipo, que resuelvan algo útil. Cada uno debe interactuar con al menos una interfaz del sistema operativo (/proc, /sys, systemd, señales, sockets, cgroups) y documentar cuál usa.

### **Atajos de teclado**

Configurados a nivel de WM/DE y versionados en el repositorio.

| Tipo | Atajos |
| :---- | :---- |
| Base obligatoria | Super \+ Enter → abrir terminal · Super \+ W (o Super \+ Q) → cerrar ventana activa · Super \+ D → launcher de aplicaciones (rofi, wofi, dmenu…) · Super \+ \[1-9\] → cambiar de workspace. |
| Atajos libres | **Exactamente 3 por integrante** (9 por equipo), inventados por el equipo, que resuelvan algo útil de su flujo de trabajo. Al menos uno por integrante debe invocar uno de los comandos propios o una función de la Capa 2\. No se entregan ejemplos para no condicionar la creatividad. |

Se entrega un **cheatsheet** (imagen, PDF o sección del README) con todos los atajos, obligatorios y libres, explicando qué hace cada uno y quién lo diseñó.

## **A.6 Estructura de referencia del repositorio**

Estructura ilustrativa, no obligatoria en su forma exacta; cada equipo puede organizar su repositorio como prefiera, siempre que sea claro y esté documentado.

| midistro/ ├── README.md ├── install.sh              \# bootstrap reproducible e idempotente ├── pkglist.txt             \# paquetes oficiales y de AUR ├── dotfiles/               \# configuración del WM/DE, shell, terminal, launcher ├── bin/                    \# comandos propios (midistro-info, etc.) ├── systemd/                \# unit files, timers, sockets ├── pacman/                 \# hooks y PKGBUILD ├── udev/                   \# reglas udev ├── security/               \# sudoers, nftables, sshd\_config, ACL ├── src/                    \# mini-programa de IPC └── docs/     ├── instalacion.md     ├── responsabilidades.md     ├── bitacora\_ia.md     ├── cheatsheet.md     └── tema-XX-\*.md        \# una ficha de evidencia por tema |
| :---- |

## **A.7 Entregables específicos**

* Repositorio con dotfiles, scripts, unit files, hooks, reglas y código fuente, según A.6.

* Bitácora de instalación y logs de ejecución del bootstrap de **cada integrante**.

* Siete fichas de evidencia (una por tema de la Capa 2 implementado).

* Cheatsheet de atajos.

* Demostración en vivo sobre la instalación de al menos un integrante, elegido por el profesor el día de la defensa.

## **A.8 Rúbrica de la Alternativa A (escala 0–5)**

| Rubro | Peso | Qué se evalúa |
| :---- | ----- | :---- |
| Capa 1 — Instalación base y reproducibilidad | 15 % | Instalación manual correcta en las máquinas de todos los integrantes; bitácora de instalación que explica el porqué; DE/WM justificado con datos; bootstrap idempotente aplicado con éxito por cada integrante. |
| Capa 2 — Temas de SO: implementación y evidencia | 40 % | Promedio de los 7 temas elegidos. En cada uno se evalúa implementación correcta, ficha de evidencia con datos medidos e interpretación del concepto de SO. Se evalúa el “por qué”, no solo el “qué”. Aplica la regla de evidencia de la sección 5\. |
| Capa 3 — Comandos y atajos propios | 10 % | Funcionalidad del comando obligatorio (leído desde /proc y /sys) y de los comandos y atajos libres; uso real de interfaces del SO; utilidad y creatividad; cheatsheet. |
| Documentación técnica y repositorio | 10 % | Rubro común (Parte I, sección 8). |
| Defensa oral individual | 15 % | Rubro común (Parte I, sección 8). |
| Bitácora de uso de IA | 10 % | Rubro común (Parte I, sección 8). |
| **Total** | **100 %** |  |

## **A.9 Resumen de requisitos mínimos**

* Instalación manual de Arch Linux en modo UEFI por **cada integrante**, más un DE/WM elegido y justificado con datos.

* Script de bootstrap reproducible e idempotente, aplicado por cada integrante.

* **7 de 9** temas de la Capa 2 implementados, cada uno con ficha de evidencia medida; mínimo 2 temas por integrante como responsable principal.

* 1 comando obligatorio (sin envoltorios de neofetch/fastfetch) \+ **2 comandos libres por integrante**.

* 4 atajos obligatorios \+ **exactamente 3 atajos libres por integrante**, con cheatsheet.

* Repositorio Git con historial coherente, matriz de responsabilidades, bitácora de IA e informe final.

* Demostración en vivo y defensa oral individual.

# **Parte III · Alternativa B — Plataforma distribuida de análisis de datos de mensajería**

*Gestión de memoria, E/S, almacenamiento y seguridad en cargas de trabajo distribuidas*

## **B.1 Descripción general**

El objetivo es desarrollar una **infraestructura distribuida y multiproceso** capaz de recibir, gestionar y procesar cargas de trabajo de análisis de datos provenientes de aplicaciones de mensajería. Cada carga de trabajo es un **caso de análisis** que agrupa las fuentes de uno o varios usuarios: historiales de conversación, mensajes de texto, notas de voz, imágenes, videos y documentos adjuntos.

Los casos se procesan de forma concurrente, asíncrona y distribuida entre workers especializados, y al finalizar el sistema genera **reportes consolidados** con hallazgos, categorías, patrones de actividad, incidencias detectadas y evidencias asociadas.

| ⚠️ Requisito central de esta alternativa El análisis de datos es la carga de trabajo, no el objetivo. El proyecto no consiste en entrenar modelos de IA, sino en diseñar la infraestructura que administra eficientemente esa carga. A diferencia del I Proyecto —centrado en colas, workers, concurrencia y sincronización—, aquí la exigencia está en cómo el sistema administra recursos escasos y protege información sensible: memoria limitada frente a modelos pesados, planificación justa entre prioridades, E/S de archivos grandes, almacenamiento eficiente, cifrado, control de acceso y cadena de custodia de la evidencia. |
| :---- |

## **B.2 Relación con el I Proyecto Programado**

* Se **motiva a reutilizar** la infraestructura del I Proyecto del propio equipo (cola, coordinador, workers, dashboard, cliente de carga).

* El equipo debe entregar docs/reutilizacion.md indicando con precisión **qué se reutiliza, qué se modifica y qué es nuevo**. La evaluación técnica de esta alternativa se concentra en lo nuevo (secciones B.5 a B.7).

* Se mantiene la exigencia de **distribución real** del I Proyecto: al menos tres nodos worker en entidades de ejecución separadas (preferiblemente una computadora física por integrante), con comunicación por red. No se aceptan implementaciones donde todo corre en una sola máquina.

* Si la infraestructura del I Proyecto presentó deficiencias señaladas en su evaluación, el equipo debe corregirlas como parte de este proyecto.

## **B.3 Consideraciones éticas y de datos**

| 🔒 Datos sintéticos o públicos únicamente Este sistema procesa información potencialmente sensible (conversaciones privadas, imágenes, voz) y busca indicios de violencia, amenazas o actividades ilícitas. Por esa razón: Queda prohibido usar conversaciones, audios o imágenes reales de terceros, incluyendo exportaciones de chats propios que contengan mensajes de otras personas. Las conversaciones deben ser sintéticas (generadas por el equipo, con o sin IA; si se usa IA, se declara en la bitácora) o provenir de datasets públicos con licencia que permita su uso académico. Las imágenes y audios deben provenir de datasets públicos con licencia documentada o ser producidos por el propio equipo. El documento docs/dataset.md debe declarar la procedencia y licencia de cada fuente de datos. |
| :---- |

### **Dataset mínimo**

| Elemento | Mínimo exigido |
| :---- | :---- |
| Casos de análisis | 40 casos, de los cuales al menos 10 heterogéneos (texto \+ imagen \+ audio \+ video/documento). |
| Mensajes de texto | 20 000 mensajes en total, en formato de exportación realista (p. ej. el formato de exportación de WhatsApp o Telegram, con timestamps y remitentes). |
| Imágenes | 300 imágenes en total, con proporción conocida de contenido “positivo” para las categorías detectadas. |
| Audios | 150 notas de voz en total, de distintas duraciones. |
| Casos pesados | Al menos 5 casos con archivos de video o adjuntos ≥ 200 MB, para estresar E/S y almacenamiento. |
| Verdad de referencia | Etiquetas esperadas (*ground truth*) para al menos una muestra, de modo que se puedan reportar aciertos y errores del análisis. |

## **B.4 Pipeline funcional (requisitos base)**

El sistema debe contemplar, como mínimo, los siguientes componentes. Muchos pueden provenir del I Proyecto (B.2), pero deben quedar operativos para este dominio.

| Componente | Requisito |
| :---- | :---- |
| Recepción de casos | Creación de casos con múltiples fuentes; validación de formatos; registro y almacenamiento de la carga. |
| Cola y distribución | Colas de trabajo con descomposición del caso en sub-tareas y **routing por tipo de contenido** hacia workers especializados. |
| Workers de análisis | Workers especializados para **texto, imagen y audio** (los tres obligatorios). Texto: palabras clave, clasificación temática, sentimiento, lenguaje ofensivo o amenazas. Imagen: clasificación o detección de objetos/contenido sensible. Audio: speech-to-text y análisis del texto transcrito. |
| Estados del caso | queued, processing, completed, partially\_completed, failed, retrying, cancelled, con cierre del caso mediante sincronización tipo barrier/join. |
| Reintentos y cancelación | Reintentos con *backoff* y número máximo configurable. La **cancelación debe ser real**: detiene las sub-tareas en curso y libera recursos (procesos, memoria, archivos temporales). |
| Reporte consolidado | Hallazgos, categorías detectadas, línea temporal de actividad, incidencias y **fragmentos de evidencia** (mensaje, imagen o segmento de audio con timestamp) enlazados a su fuente original. |
| Alertas | Notificación asíncrona cuando un caso finaliza o cuando se detecta una incidencia de severidad alta. |
| Dashboard | Monitoreo en tiempo real de casos, sub-tareas, workers, colas y **uso de recursos por nodo** (CPU, memoria, GPU si existe). |

## **B.5 Módulos de Sistemas Operativos (núcleo de la alternativa)**

Los **cinco módulos son obligatorios**. Cada integrante debe ser **responsable principal de al menos un módulo**; los restantes se asignan en la matriz de responsabilidades. Cada módulo requiere su ficha de evidencia (Parte I, sección 5).

| Módulo | Requisito concreto | Evidencia mínima exigida |
| :---- | :---- | :---- |
| **M1 · Gestión de memoria** | Cada worker corre bajo un **límite de memoria** (cgroups v2, mediante Docker \--memory, systemd MemoryMax= o equivalente). Medir la huella de memoria (RSS/PSS) de cada modelo usado y, con esos datos, implementar **control de admisión**: el nodo solo acepta tantos workers o sub-tareas como su memoria permite. Detectar terminaciones por OOM y reencolar con una política definida. Justificar la estrategia de carga de modelos (un modelo por proceso frente a modelo compartido mediante fork después de cargar / *copy-on-write* o mmap). | Tabla de huella de memoria por modelo; gráfico de memoria por worker en el tiempo durante una ráfaga; prueba de OOM provocado y recuperación del sistema; comparación de memoria total entre las dos estrategias de carga de modelos. |
| **M2 · Planificación de cargas** | Niveles de prioridad (baja, media, alta, crítica) con un **algoritmo de planificación explícito y documentado** (p. ej. colas multinivel con retroalimentación y *aging*, o *weighted fair queuing*). El algoritmo debe evitar la inanición (*starvation*) de casos de baja prioridad. | Experimento comparando **al menos dos políticas** (p. ej. FIFO frente a prioridad con aging) bajo un flujo sostenido de casos de alta prioridad: tiempo de espera, tiempo de retorno (*turnaround*) y *throughput* por nivel de prioridad. Debe demostrarse con datos la ausencia de inanición. |
| **M3 · E/S y almacenamiento** | Transferencia de archivos grandes en **bloques (chunks)** de tamaño justificado, con reensamblado verificado por hash. Almacenamiento **direccionado por contenido** (SHA-256) con **deduplicación**. **Contrapresión** (*backpressure*): colas acotadas que bloquean o rechazan a los productores cuando se llenan. Recepción de archivos con E/S asíncrona o no bloqueante. | Throughput (MB/s) frente a tamaño de chunk (al menos 3 tamaños); tasa de deduplicación sobre el dataset; gráfico de profundidad de cola y tiempos de respuesta durante una ráfaga, con y sin backpressure. |
| **M4 · Protección y seguridad** | Autenticación y **control de acceso por roles** (mínimo: analista, supervisor, administrador). **Cifrado en tránsito** (TLS) entre nodos y **cifrado en reposo** de las evidencias, con gestión de llaves justificada (nunca llaves en el código). **Cadena de custodia**: cada evidencia registra su hash al ingresar y en cada transformación, en un log de solo-anexión encadenado por hash y verificable. Workers ejecutándose **sin privilegios** (usuario no root, contenedor con sistema de archivos de solo lectura o equivalente). | Prueba de manipulación: alterar una evidencia o una entrada del log y mostrar que la verificación lo detecta; accesos denegados por rol; captura de tráfico que muestre que la comunicación entre nodos va cifrada; evidencia de que los workers no corren como root. |
| **M5 · Cómputo heterogéneo** | Comparar al menos una carga de inferencia (p. ej. Whisper o YOLO) en **dos o más configuraciones de cómputo**: CPU frente a GPU (local o en un servicio gratuito como Google Colab o Kaggle). Si ningún integrante tiene acceso a GPU, comparar CPU con distinto número de hilos y modelo cuantizado frente a no cuantizado. Usar los resultados para definir la **política de routing** del coordinador. | Tabla de latencia, throughput y memoria por configuración; justificación de la política de routing basada en esos datos (qué sub-tareas van a qué tipo de nodo y por qué). **Conexión con Unidad 1** (CPU/GPU/NPU). |

| 🔗 Conexión con Unidad 1 El módulo M5 retoma la discusión sobre heterogeneidad de cómputo del inicio del curso: así como una GPU es más eficiente para paralelismo masivo y una NPU para inferencia, el coordinador debe decidir —con datos medidos, no por intuición— qué sub-tareas asignar a qué tipo de nodo. |
| :---- |

## **B.6 Pruebas de carga y tolerancia a fallos**

El informe final debe documentar, con métricas y gráficos, al menos los siguientes escenarios:

| Escenario | Qué se debe mostrar |
| :---- | :---- |
| Ráfaga de carga | Envío concurrente de al menos 20 casos; throughput, latencia por caso y uso de recursos por nodo durante la ráfaga. |
| Caída de un worker | Un worker se detiene abruptamente durante un caso en proceso: detección, reasignación de sus sub-tareas y estado final correcto del caso. |
| Reinicio del coordinador | El coordinador se reinicia con casos en curso: el estado persistido permite retomar sin perder ni duplicar sub-tareas. |
| Cancelación en curso | Cancelación de un caso pesado a mitad de procesamiento: los recursos se liberan (memoria, procesos, archivos temporales). |
| Saturación de memoria | Carga que supera la memoria disponible de un nodo: el control de admisión (M1) evita el colapso del nodo. |

## **B.7 Tecnologías sugeridas**

Los equipos pueden usar otras herramientas siempre que las justifiquen técnicamente.

| Área | Herramientas |
| :---- | :---- |
| Texto | spaCy, NLTK, HuggingFace Transformers |
| Imagen | OpenCV, YOLO (Ultralytics), modelos preentrenados de clasificación |
| Audio | Whisper / faster-whisper, Vosk |
| Infraestructura | RabbitMQ, Redis / RQ, Kafka, Celery, Docker, Docker Compose |
| Memoria y recursos | cgroups v2, Docker resource limits, psutil, smem, Prometheus \+ Grafana |
| Almacenamiento | MinIO (compatible con S3), PostgreSQL, SQLite, sistemas de archivos compartidos |
| Seguridad | TLS (OpenSSL / mkcert), cryptography (AES-GCM), JWT, HashiCorp Vault o archivos de llaves con permisos restringidos |
| Cómputo acelerado | CUDA / ROCm, Google Colab, Kaggle Notebooks, ONNX Runtime, cuantización (int8) |

## **B.8 Entregables específicos**

* Repositorio con código fuente, configuración de despliegue (p. ej. Docker Compose por nodo) e instrucciones de despliegue distribuido.

* Documento de arquitectura actualizado (diagramas de componentes, despliegue y flujo de un caso).

* docs/reutilizacion.md y docs/dataset.md.

* Cinco fichas de evidencia (una por módulo M1–M5).

* Informe de pruebas de carga y tolerancia a fallos (B.6), integrado en el informe final.

* Demostración en vivo del sistema distribuido sobre los nodos reales del equipo.

## **B.9 Rúbrica de la Alternativa B (escala 0–5)**

| Rubro | Peso | Qué se evalúa |
| :---- | ----- | :---- |
| Pipeline funcional y análisis multimedia | 15 % | Pipeline completo de B.4 operando de forma distribuida: workers de texto, imagen y audio integrados; estados, reintentos y cancelación real; reporte consolidado con evidencias enlazadas; dashboard y alertas; dataset conforme a B.3. |
| Módulos de SO M1–M5: implementación y evidencia | 40 % | Promedio de los cinco módulos (8 % cada uno). En cada uno se evalúa implementación correcta, ficha de evidencia con datos medidos e interpretación del concepto de SO. Aplica la regla de evidencia de la sección 5\. |
| Pruebas de carga y tolerancia a fallos | 10 % | Ejecución y documentación de los cinco escenarios de B.6, con métricas, gráficos e interpretación del comportamiento observado. |
| Documentación técnica y repositorio | 10 % | Rubro común (Parte I, sección 8). Incluye la declaración de reutilización y la documentación del dataset. |
| Defensa oral individual | 15 % | Rubro común (Parte I, sección 8). |
| Bitácora de uso de IA | 10 % | Rubro común (Parte I, sección 8). |
| **Total** | **100 %** |  |

## **B.10 Resumen de requisitos mínimos**

* Distribución real en al menos tres nodos, con declaración precisa de lo reutilizado del I Proyecto.

* Dataset sintético o público conforme a B.3, con procedencia y licencias declaradas.

* Pipeline completo con workers de texto, imagen y audio, estados, reintentos, cancelación real, reportes con evidencias, alertas y dashboard.

* Cinco módulos de SO (memoria, planificación, E/S y almacenamiento, seguridad, cómputo heterogéneo), cada uno con ficha de evidencia medida; mínimo un módulo por integrante como responsable principal.

* Cinco escenarios de pruebas de carga y tolerancia a fallos documentados.

* Repositorio Git con historial coherente, matriz de responsabilidades, bitácora de IA e informe final.

* Demostración en vivo y defensa oral individual.

# **Anexos · Plantillas**

## **Anexo 1 · Matriz de responsabilidades**

Archivo docs/responsabilidades.md. Una fila por tema (A) o módulo (B).

| Tema / módulo | Responsable principal | Apoyo | Ruta en el repositorio | Ficha de evidencia |
| :---- | :---- | :---- | :---- | :---- |
| Ej.: Tema 2 · Memoria | Nombre Apellido | Nombre Apellido | bin/memwatch, systemd/zram | docs/tema-02-memoria.md |
|  |  |  |  |  |
|  |  |  |  |  |

## **Anexo 2 · Ficha de evidencia**

Archivo docs/tema-XX-nombre.md (A) o docs/modulo-MX-nombre.md (B).

| \# Tema/Módulo: \<nombre\>          Responsable: \<nombre\> \#\# 1\. Qué se implementó \<descripción concreta \+ rutas en el repositorio\> \#\# 2\. Concepto de Sistemas Operativos \<concepto demostrado \+ referencia bibliográfica (autor, capítulo)\> \#\# 3\. Método de medición \<herramienta, comandos exactos, condiciones del experimento, n.º de repeticiones\> \#\# 4\. Resultados \<tabla o gráfico; antes/después o comparación entre alternativas\> \#\# 5\. Interpretación \<¿coinciden los datos con la teoría? ¿por qué sí o por qué no?\> |
| :---- |

## **Anexo 3 · Bitácora de uso de IA**

Archivo docs/bitacora\_ia.md. Una entrada por consulta relevante.

| Campo | Contenido |
| :---- | :---- |
| Fecha · integrante | Quién realizó la consulta y cuándo. |
| Herramienta | Asistente o modelo utilizado. |
| Componente | Tema o módulo al que corresponde. |
| Propósito | Qué se buscaba (entender, depurar, explorar alternativas, generar datos sintéticos…). |
| Consulta resumida | Qué se le preguntó, en una o dos líneas. |
| Resultado obtenido | Qué respondió o produjo la IA. |
| Validado / corregido / descartado | Qué parte se aceptó, qué se corrigió y qué se descartó. |
| Cómo se validó | Comando ejecutado, documentación oficial (man pages, Arch Wiki, documentación del proyecto) o prueba realizada. |

