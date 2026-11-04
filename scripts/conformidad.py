#!/usr/bin/env python3
"""Comprueba patrón y piezas del proyecto, sin compilar ni ejecutar el sistema.

    python -m scripts.conformidad repo
    PR_TITULO=... PR_RAMA=... PR_BASE=... PR_BASE_SHA=... python -m scripts.conformidad pr [check ...]
"""
import os
import pathlib
import re
import subprocess
import sys

from scripts.flujo import (
    BACKLOG,
    BITACORA,
    CERRADA,
    EN_PR,
    EXCLUIDOS_DEL_TAMANO,
    FASES,
    LIMITE_LINEAS,
    PLANTILLA_PR,
    PLANTILLA_SPEC,
    PR_ABIERTA,
    RAIZ,
    RAMA_ESTADO,
    STATUS,
    _RAMA,
    base_de_spec,
    bitacora_registra,
    es_conventional,
    fase_de,
    parsear_backlog,
)

ROLES = ("orquestador", "arquitecto", "developer", "qa-tester", "medidor", "documentador", "revisor")
COMANDOS = ("empezables", "trabajar", "cierre")
PIEZAS_COMUNES = (
    "AGENTS.md", "CONTRIBUTING.md", "README.md", ".claude/CLAUDE.md", "scripts/flujo.py", BACKLOG, BITACORA,
    PLANTILLA_SPEC, PLANTILLA_PR, "docs/ENUNCIADO.md", "docs/REQUERIMIENTOS.md", "docs/ARQUITECTURA.md",
    "docs/IMPLEMENTACION.md",
    *(f".agents/roles/{r}.md" for r in ROLES),
    *(f".agents/skills/{c}/SKILL.md" for c in COMANDOS),
    *(f".claude/skills/{c}/SKILL.md" for c in COMANDOS),
)
PIEZAS_POR_FEATURE = {
    "F-04": ("docs/dataset.md",),
    "F-39": ("docs/reutilizacion.md",),
    "F-40": ("docs/responsabilidades.md",),
    "F-41": ("docs/modulo-M1-memoria.md", "docs/modulo-M2-planificacion.md", "docs/modulo-M3-es-almacenamiento.md",
             "docs/modulo-M4-seguridad.md", "docs/modulo-M5-computo.md"),
}
ESTADOS = ("pendiente", *FASES, EN_PR, "hecha")
CAMPOS_ANEXO_3 = ("Herramienta", "Componente", "Propósito", "Consulta resumida", "Resultado obtenido",
                  "Validado / corregido / descartado", "Cómo se validó")
SECCIONES_FICHA = ("Qué se implementó", "Concepto de Sistemas Operativos", "Método de medición",
                   "Resultados", "Interpretación")
CODIGO_DE_PRODUCTO = ("src/", "deploy/", "dashboard/")
RAMAS_CON_CODIGO = ("fix/", "refactor/")
_RAMA_VALIDA = re.compile(r"^(feat/F-\d+-\d+-[a-z0-9-]+|(chore|docs|fix|refactor|test|ci|build)/[\w./-]+)$")
_FILA_STATUS = re.compile(r"^\| (F-\d+) \| ([\w-]+) \|$", re.M)
_LLAVE_PRIVADA = re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")


def revisar_rama(rama):
    return [] if _RAMA_VALIDA.match(rama) else [f"rama fuera del patrón de CONTRIBUTING.md: {rama}"]


def _feature_de(rama):
    coincidencia = _RAMA.match(rama)
    return coincidencia.group(1) if coincidencia else None


def revisar_titulo(titulo, rama):
    if not es_conventional(titulo):
        return [f"título fuera de Conventional Commits: {titulo}"]
    feature = _feature_de(rama)
    if feature and f"({feature})" not in titulo:
        return [f"el título debe usar el ámbito ({feature})"]
    return []


def revisar_commits(asuntos):
    return [f"commit fuera de Conventional Commits: {a}" for a in asuntos if not es_conventional(a)]


def revisar_tamano(numstat, rama):
    if not _feature_de(rama):
        return []
    filas = (fila.split("\t") for fila in numstat.splitlines())
    lineas = sum(int(f[0]) + int(f[1]) for f in filas if f[0] != "-")
    return [f"{lineas} líneas superan el límite de {LIMITE_LINEAS}; divide la PR"] if lineas > LIMITE_LINEAS else []


def revisar_spec(spec, base_pr):
    motivos = []
    if fase_de(spec) not in (PR_ABIERTA, CERRADA):
        motivos.append(f"el SPEC sigue en fase {fase_de(spec)}")
    if base_pr not in (base_de_spec(spec), "main"):
        motivos.append(f"la base de la PR ({base_pr}) no coincide con la del SPEC ({base_de_spec(spec)})")
    for fase in FASES:
        if f"\n| verificación IA de {fase} |" not in spec:
            motivos.append(f"falta la verificación de IA de {fase}")
        if f"\n| {fase} |" not in spec:
            motivos.append(f"falta la aprobación humana de {fase}")
    return motivos


def revisar_alcance(rama, archivos):
    motivos = []
    if _feature_de(rama) and BITACORA in archivos:
        motivos.append(f"{BITACORA} se publica con `flujo.py bitacora`, no en la PR")
    if not _feature_de(rama) and not rama.startswith(RAMAS_CON_CODIGO):
        codigo = [a for a in archivos if a.startswith(CODIGO_DE_PRODUCTO)]
        if codigo:
            motivos.append("el código de producto entra por una feature: " + ", ".join(codigo))
    return motivos


def revisar_status(texto, features):
    motivos = [] if "Generado por scripts/flujo.py" in texto else [f"{STATUS} no tiene la marca de generado"]
    estados = dict(_FILA_STATUS.findall(texto))
    if set(estados) != set(features):
        diferencia = sorted(set(estados) ^ set(features))
        motivos.append(f"{STATUS} no coincide con el backlog: {', '.join(diferencia)}")
    motivos += [f"estado desconocido en {f}: {e}" for f, e in estados.items() if e not in ESTADOS]
    return motivos


def revisar_backlog(features):
    return [f"{f.id} depende de {d}, que no existe" for f in features.values() for d in f.deps if d not in features]


def revisar_bitacora(texto):
    motivos = []
    for entrada in re.split(r"^## ", texto, flags=re.M)[1:]:
        if "| Uso de IA |" in entrada:
            continue
        faltan = [c for c in CAMPOS_ANEXO_3 if f"| {c} |" not in entrada]
        if faltan:
            motivos.append(f"entrada «{entrada.splitlines()[0]}» sin: {', '.join(faltan)}")
    return motivos


def revisar_ficha(texto):
    return [f"falta la sección «{s}»" for s in SECCIONES_FICHA if s not in texto]


def revisar_piezas(existentes, estados):
    requeridas = list(PIEZAS_COMUNES)
    for feature, piezas in PIEZAS_POR_FEATURE.items():
        if estados.get(feature) == "hecha":
            requeridas.extend(piezas)
    return [f"falta {p}" for p in requeridas if p not in existentes]


def revisar_comandos(contenidos):
    return [f".claude/skills/{c} debe apuntar a .agents/skills/{c}" for c, texto in contenidos.items()
            if f".agents/skills/{c}/SKILL.md" not in texto]


def revisar_secretos(lineas_agregadas):
    return ["se agregó una llave privada"] if any(_LLAVE_PRIVADA.search(l) for l in lineas_agregadas) else []


def _git(*args):
    return subprocess.run(("git", *args), cwd=RAIZ, capture_output=True, text=True, encoding="utf-8", check=True).stdout


def _leer(ruta):
    return (RAIZ / ruta).read_text(encoding="utf-8")


def conformidad_repo():
    backlog = parsear_backlog(_leer(BACKLOG))
    status = _git("show", f"origin/{RAMA_ESTADO}:{STATUS}")
    bitacora = _git("show", f"origin/{RAMA_ESTADO}:{BITACORA}")
    existentes = {p.relative_to(RAIZ).as_posix() for p in RAIZ.rglob("*") if p.is_file() and ".git" not in p.parts}
    fichas = pathlib.Path(RAIZ / "docs").glob("modulo-M*.md")
    motivos = revisar_piezas(existentes, dict(_FILA_STATUS.findall(status)))
    motivos += revisar_status(status, backlog) + revisar_backlog(backlog) + revisar_bitacora(bitacora)
    motivos += revisar_comandos({c: _leer(f".claude/skills/{c}/SKILL.md") for c in COMANDOS
                                 if f".claude/skills/{c}/SKILL.md" in existentes})
    if STATUS in existentes:
        motivos.append(f"{STATUS} vive en la rama {RAMA_ESTADO}, no aquí")
    for ficha in fichas:
        motivos += [f"{ficha.name}: {m}" for m in revisar_ficha(ficha.read_text(encoding="utf-8"))]
    return motivos


def _rango():
    return f"{os.environ['PR_BASE_SHA']}...HEAD"


def _rama():
    return os.environ["PR_RAMA"]


def _check_titulo():
    return revisar_titulo(os.environ["PR_TITULO"], _rama())


def _check_rama():
    return revisar_rama(_rama())


def _check_commits():
    return revisar_commits(_git("log", "--no-merges", "--format=%s", f"{os.environ['PR_BASE_SHA']}..HEAD").splitlines())


def _check_tamano():
    return revisar_tamano(_git("diff", "--numstat", _rango(), "--", ".", *EXCLUIDOS_DEL_TAMANO), _rama())


def _check_alcance():
    return revisar_alcance(_rama(), _git("diff", "--name-only", _rango()).splitlines())


def _check_secretos():
    return revisar_secretos([l for l in _git("diff", _rango()).splitlines() if l.startswith("+")])


def _check_estado_feature():
    feature = _feature_de(_rama())
    if not feature:
        return []
    ruta = f"docs/specs/{feature}/SPEC.md"
    return revisar_spec(_leer(ruta), os.environ["PR_BASE"]) if (RAIZ / ruta).exists() else [f"falta {ruta}"]


def _check_bitacora():
    if not _feature_de(_rama()) or bitacora_registra(_git("show", f"origin/{RAMA_ESTADO}:{BITACORA}"), _rama()):
        return []
    return [f"falta la entrada de {_rama()} en {BITACORA}"]


CHECKS_PR = {
    "titulo": _check_titulo,
    "rama": _check_rama,
    "commits": _check_commits,
    "tamano": _check_tamano,
    "alcance": _check_alcance,
    "secretos": _check_secretos,
    "estado-feature": _check_estado_feature,
    "bitacora": _check_bitacora,
}


def conformidad_pr(nombres):
    return [motivo for nombre in nombres or CHECKS_PR for motivo in CHECKS_PR[nombre]()]


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    motivos = conformidad_pr(sys.argv[2:]) if sys.argv[1:2] == ["pr"] else conformidad_repo()
    for motivo in motivos:
        print(f"::error::{motivo}")
    print(f"Conformidad: {len(motivos)} problema(s)")
    sys.exit(1 if motivos else 0)


if __name__ == "__main__":
    main()
