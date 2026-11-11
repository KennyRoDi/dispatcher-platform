# F-12 · Evidencia de cancelación real (2026-11-10)

Entorno: contenedor `python:3.13-slim` (Linux), `procps` instalado, repositorio montado en `/app`.
Alcance: `ProcessSupervisor` con `PosixProcessRunner`, aislado; no incluye worker con Redis.
Subproceso: `sh -c "trap '' TERM; sleep 60 & sleep 60"` (ignora SIGTERM), gracia 0.5 s, temporal `/scratch/t1/parcial.bin`.
Salida real de la ejecución (en DESPUÉS las dos líneas `sh`/`grep` son el propio comando de consulta, no zombies):

```
== ANTES
3
t1

== DESPUES
    116 S    /bin/sh -c ps -eo pid,stat,cmd | grep -E '[s]leep 60|Z' ; echo procs=$(ps -eo cmd | grep -c '[s]leep 60'); ls /scratch; echo ls_ok
    118 S    grep -E [s]leep 60|Z
procs=0
ls_ok

```
