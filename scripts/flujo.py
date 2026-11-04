#!/usr/bin/env python3
"""Ciclo de trabajo común a todos los agentes y personas. Ver CONTRIBUTING.md.

    python scripts/flujo.py empezables [--responsable K]
    python scripts/flujo.py trabajar F-XX "descripcion corta"
    python scripts/flujo.py aprobar
    python scripts/flujo.py cierre --tipo feat --resumen "texto" [--final]

Solo usa la biblioteca estándar, git y gh.
"""
import argparse
import dataclasses
import datetime
import json
import pathlib
import re
import subprocess
import sys
import tempfile
import unicodedata

ESTADOS = ("pendiente", "spec", "en-curso", "en-pr", "hecha")
ACTIVOS = ("spec", "en-curso", "en-pr")
APILABLES = ("en-curso", "en-pr")
TIPOS = ("feat", "fix", "docs", "test", "refactor", "perf", "build", "ci", "chore", "style", "revert")
LIMITE_LINEAS = 400
STATUS = "docs/STATUS.md"
BACKLOG = "docs/BACKLOG.md"
PLANTILLA_PR = ".github/pull_request_template.md"
EXCLUIDOS_DEL_TAMANO = (":!tests", ":!docs")
PRUEBAS = ("-m", "pytest", "-q", "-m", "not integration and not acceptance")
RAIZ = pathlib.Path(__file__).resolve().parents[1]

_CONVENTIONAL = re.compile(rf"^({'|'.join(TIPOS)})(\([\w./-]+\))?!?: \S")
_FILA_STATUS = re.compile(r"^\| (F-\d+) \| ([\w-]+) \|$", re.M)
_ENCABEZADO_US = re.compile(r"^### US-\d+ · .*\((F-\d+)\)", re.M)
_METADATOS = re.compile(r"\*\*Responsable:\*\* (.+?) · \*\*Depende de:\*\* (.+)")
_RAMA = re.compile(r"^feat/(F-\d+)-(\d+)-")
_BORRADOR = "**Estado:** borrador"
_APROBADO = "**Estado:** aprobado"


@dataclasses.dataclass(frozen=True)
class Feature:
    id: str
    responsable: str
    deps: tuple
    historia: str

    @property
    def titulo(self):
        primera = self.historia.split("\n", 1)[0]
        return primera.split(" · ", 1)[-1].split(" (F-")[0]


@dataclasses.dataclass(frozen=True)
class Clasificacion:
    tipo: str
    base: str = ""
    motivo: str = ""


# --- Lógica pura ---

def parsear_status(texto):
    return dict(_FILA_STATUS.findall(texto))


def cambiar_status(texto, feature, estado):
    if estado not in ESTADOS:
        raise ValueError(f"estado desconocido: {estado}")
    nuevo, cambios = re.subn(rf"^\| {feature} \| [\w-]+ \|$", f"| {feature} | {estado} |", texto, flags=re.M)
    if not cambios:
        raise ValueError(f"{feature} no está en {STATUS}")
    return nuevo


def parsear_backlog(texto):
    encabezados = list(_ENCABEZADO_US.finditer(texto))
    features = {}
    for i, encabezado in enumerate(encabezados):
        fin = encabezados[i + 1].start() if i + 1 < len(encabezados) else len(texto)
        historia = re.split(r"^## ", texto[encabezado.start():fin], flags=re.M)[0].strip()
        metadatos = _METADATOS.search(historia)
        if not metadatos:
            raise ValueError(f"{encabezado.group(1)} no declara responsable y dependencias")
        deps = tuple(re.findall(r"F-\d+", metadatos.group(2)))
        features[encabezado.group(1)] = Feature(encabezado.group(1), metadatos.group(1), deps, historia)
    return features


def ramas_por_feature(ramas):
    agrupadas = {}
    for rama in ramas:
        coincidencia = _RAMA.match(rama)
        if coincidencia:
            agrupadas.setdefault(coincidencia.group(1), []).append(rama)
    for lista in agrupadas.values():
        lista.sort(key=lambda r: int(_RAMA.match(r).group(2)))
    return agrupadas


def clasificar(features, status, ramas):
    return {f.id: _clasificar_una(f, status, ramas) for f in features.values()}


def _clasificar_una(feature, status, ramas):
    estado = status.get(feature.id, "pendiente")
    if estado == "hecha":
        return Clasificacion("hecha")
    if estado in ACTIVOS:
        return Clasificacion("activa", motivo=estado)
    faltantes = [d for d in feature.deps if status.get(d, "pendiente") != "hecha"]
    if not faltantes:
        return Clasificacion("empezable", base="main")
    motivo = "falta " + ", ".join(faltantes)
    if len(faltantes) == 1:
        dep = faltantes[0]
        if status.get(dep) in APILABLES and ramas.get(dep):
            return Clasificacion("apilable", base=ramas[dep][-1], motivo=f"sobre {dep}")
    return Clasificacion("bloqueada", motivo=motivo)


def nombre_rama(feature, descripcion, ramas):
    sin_acentos = unicodedata.normalize("NFKD", descripcion).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", sin_acentos.lower()).strip("-")
    partes = [int(_RAMA.match(r).group(2)) for r in ramas.get(feature, [])]
    return f"feat/{feature}-{max(partes, default=0) + 1}-{slug}"


def spec_aprobada(texto):
    return _APROBADO in texto


def aprobar_spec(texto, nombre, fecha):
    if _BORRADOR not in texto:
        raise ValueError("el SPEC no está en borrador")
    return texto.replace(_BORRADOR, f"{_APROBADO} por {nombre} el {fecha}")


def es_conventional(mensaje):
    return bool(_CONVENTIONAL.match(mensaje))


def titulo_pr(tipo, feature, resumen):
    titulo = f"{tipo}({feature}): {resumen}"
    if not es_conventional(titulo):
        raise ValueError(f"título no cumple Conventional Commits: {titulo}")
    return titulo


def features_cerradas(cuerpos):
    return {f for cuerpo in cuerpos for f in re.findall(r"^Cierra-Feature: (F-\d+)", cuerpo, re.M)}


def cuerpo_pr(plantilla, **campos):
    for clave, valor in campos.items():
        plantilla = plantilla.replace("{" + clave + "}", valor)
    return plantilla


# --- Git y GitHub ---

def _ejecutar(*comando, cwd=RAIZ, entrada=None):
    resultado = subprocess.run(comando, cwd=cwd, input=entrada, capture_output=True, text=True, encoding="utf-8")
    if resultado.returncode:
        raise subprocess.CalledProcessError(resultado.returncode, comando, resultado.stdout, resultado.stderr)
    return resultado.stdout.strip()


def git(*args, cwd=RAIZ):
    return _ejecutar("git", *args, cwd=cwd)


def _fallar(mensaje):
    raise SystemExit(f"flujo: {mensaje}")


def _leer_main(ruta):
    try:
        return git("show", f"origin/main:{ruta}") + "\n"
    except subprocess.CalledProcessError:
        _fallar(f"{ruta} no existe en origin/main; fusiona primero la pila del flujo")


def _ramas_remotas():
    salida = git("ls-remote", "--heads", "origin", "feat/*")
    return [linea.split("refs/heads/")[1] for linea in salida.splitlines()]


def _rama_actual():
    return git("branch", "--show-current")


def _feature_de(rama):
    coincidencia = _RAMA.match(rama)
    if not coincidencia:
        _fallar(f"la rama {rama!r} no es de una feature; usa `trabajar F-XX`")
    return coincidencia.group(1)


def _ruta_spec(feature):
    return RAIZ / "docs" / "specs" / feature / "SPEC.md"


def _exigir_sin_cambios():
    if git("status", "--porcelain", "--untracked-files=no"):
        _fallar("hay cambios sin commit")


def publicar_estado(feature, estado, intentos=3):
    """Publica el estado en main al instante: es el tablero que leen todos."""
    for _ in range(intentos):
        git("fetch", "-q", "origin", "main")
        with tempfile.TemporaryDirectory() as tmp:
            arbol = pathlib.Path(tmp) / "status"
            git("worktree", "add", "-q", "--detach", str(arbol), "origin/main")
            try:
                ruta = arbol / STATUS
                actual = ruta.read_text(encoding="utf-8")
                nuevo = cambiar_status(actual, feature, estado)
                if nuevo == actual:
                    return
                ruta.write_text(nuevo, encoding="utf-8", newline="\n")
                git("commit", "-q", "-m", f"chore(status): {feature} {estado}", "--", STATUS, cwd=arbol)
                git("push", "-q", "origin", "HEAD:main", cwd=arbol)
                return
            except subprocess.CalledProcessError as error:
                ultimo_error = error.stderr
            finally:
                git("worktree", "remove", "--force", str(arbol))
    _fallar(f"no se pudo publicar el estado de {feature}: {ultimo_error}")


def _sincronizar_cerradas(status):
    """Marca `hecha` lo que tiene su PR final fusionada. Sin gh, solo avisa."""
    try:
        salida = _ejecutar("gh", "pr", "list", "--state", "merged", "--search", "Cierra-Feature in:body",
                           "--limit", "200", "--json", "body")
    except (OSError, subprocess.CalledProcessError):
        print("aviso: sin gh no se detectan PR finales fusionadas\n")
        return status
    for feature in sorted(features_cerradas(pr["body"] for pr in json.loads(salida))):
        if status.get(feature) == "en-pr":
            publicar_estado(feature, "hecha")
            status = {**status, feature: "hecha"}
    return status


# --- Comandos ---

def empezables(args):
    git("fetch", "-q", "origin", "main")
    status = _sincronizar_cerradas(parsear_status(_leer_main(STATUS)))
    features = parsear_backlog(_leer_main(BACKLOG))
    ramas = ramas_por_feature(_ramas_remotas())
    clases = clasificar(features, status, ramas)

    def corresponde(feature):
        if not args.responsable:
            return True
        return feature.responsable == args.responsable or feature.responsable in ("Todos", "Cada responsable")

    for tipo, titulo in (("empezable", "EMPEZABLES"), ("apilable", "APILABLES"), ("activa", "ACTIVAS")):
        print(titulo)
        filas = [f for f in features.values() if clases[f.id].tipo == tipo and corresponde(f)]
        for feature in filas:
            detalle = clases[feature.id].base if tipo != "activa" else clases[feature.id].motivo
            print(f"  {feature.id} [{feature.responsable}] {feature.titulo} -> {detalle}")
        if not filas:
            print("  (ninguna)")


def trabajar(args):
    feature_id = args.feature
    _exigir_sin_cambios()
    git("fetch", "-q", "origin")
    status = parsear_status(_leer_main(STATUS))
    features = parsear_backlog(_leer_main(BACKLOG))
    if feature_id not in features:
        _fallar(f"{feature_id} no está en {BACKLOG}")
    ramas = ramas_por_feature(_ramas_remotas())
    base = _elegir_base(feature_id, features, status, ramas)
    rama = nombre_rama(feature_id, args.descripcion, ramas)
    referencia = base if base == _rama_actual() else f"origin/{base}"
    git("switch", "-q", "--no-track", "-c", rama, referencia)
    git("config", f"branch.{rama}.flujo-base", base)
    git("push", "-q", "-u", "origin", rama)
    if status.get(feature_id, "pendiente") == "pendiente":
        publicar_estado(feature_id, "spec")
    print(f"Rama: {rama}\nBase de la PR: {base}\nSPEC: docs/specs/{feature_id}/SPEC.md\n")
    print(features[feature_id].historia)


def _elegir_base(feature_id, features, status, ramas):
    actual = _rama_actual()
    estado = status.get(feature_id, "pendiente")
    if estado == "hecha":
        _fallar(f"{feature_id} ya está hecha")
    if actual.startswith(f"feat/{feature_id}-"):
        if not _spec_aprobada_en_disco(feature_id):
            _fallar("el SPEC aún no está aprobado; no se abren más partes")
        return actual
    if estado in ACTIVOS:
        if ramas.get(feature_id):
            _fallar(f"{feature_id} ya está activa en {ramas[feature_id][-1]}; si es tuya, cámbiate a esa rama")
        return "main"
    clase = clasificar(features, status, ramas)[feature_id]
    if clase.tipo == "bloqueada":
        _fallar(f"{feature_id} está bloqueada: {clase.motivo}")
    return clase.base


def _spec_aprobada_en_disco(feature_id):
    ruta = _ruta_spec(feature_id)
    return ruta.exists() and spec_aprobada(ruta.read_text(encoding="utf-8"))


def aprobar(_args):
    rama = _rama_actual()
    feature_id = _feature_de(rama)
    ruta = _ruta_spec(feature_id)
    if not ruta.exists():
        _fallar(f"falta {ruta.relative_to(RAIZ)}")
    _exigir_sin_cambios()
    hoy = datetime.date.today().isoformat()
    ruta.write_text(aprobar_spec(ruta.read_text(encoding="utf-8"), git("config", "user.name"), hoy), encoding="utf-8", newline="\n")
    git("commit", "-q", "-m", f"docs({feature_id}): aprobar spec", "--", str(ruta))
    git("push", "-q", "origin", rama)
    publicar_estado(feature_id, "en-curso")
    print(f"{feature_id}: SPEC aprobado; estado en-curso")


def cierre(args):
    rama = _rama_actual()
    feature_id = _feature_de(rama)
    _exigir_sin_cambios()
    if not _spec_aprobada_en_disco(feature_id):
        _fallar("el SPEC no está aprobado")
    titulo = _validar_titulo(args.tipo, feature_id, args.resumen)
    base = _base_de(rama)
    comparacion = f"origin/{base}...HEAD"
    git("fetch", "-q", "origin", base)
    commits = _validar_commits(f"origin/{base}..HEAD")
    _validar_tamano(comparacion, args.motivo_grande)
    print("Ejecutando pruebas...")
    if subprocess.run([sys.executable, *PRUEBAS], cwd=RAIZ).returncode:
        _fallar("las pruebas fallan; no se abre la PR")
    git("push", "-q", "-u", "origin", rama)
    print(_abrir_pr(rama, base, titulo, feature_id, commits, args))
    if args.final:
        publicar_estado(feature_id, "en-pr")


def _validar_titulo(tipo, feature_id, resumen):
    try:
        return titulo_pr(tipo, feature_id, resumen)
    except ValueError as error:
        _fallar(str(error))


def _base_de(rama):
    try:
        base = git("config", f"branch.{rama}.flujo-base")
    except subprocess.CalledProcessError:
        base = "main"
    return base if git("ls-remote", "--heads", "origin", base) else "main"


def _validar_commits(rango):
    asuntos = git("log", "--no-merges", "--format=%s", rango).splitlines()
    if not asuntos:
        _fallar("no hay commits nuevos respecto a la base")
    invalidos = [a for a in asuntos if not es_conventional(a)]
    if invalidos:
        _fallar("commits fuera de Conventional Commits:\n  " + "\n  ".join(invalidos))
    return asuntos


def _validar_tamano(comparacion, motivo):
    numstat = git("diff", "--numstat", comparacion, "--", ".", *EXCLUIDOS_DEL_TAMANO)
    lineas = sum(int(a) + int(b) for a, b, *_ in (f.split("\t") for f in numstat.splitlines()) if a != "-")
    if lineas > LIMITE_LINEAS and not motivo:
        _fallar(f"{lineas} líneas sin contar tests ni docs (límite {LIMITE_LINEAS}); divide con otra parte de la pila")
    print(f"Tamaño: {lineas} líneas sin contar tests ni docs")


def _abrir_pr(rama, base, titulo, feature_id, commits, args):
    existente = json.loads(_ejecutar("gh", "pr", "list", "--head", rama, "--state", "open", "--json", "url"))
    if existente:
        return f"PR existente actualizada: {existente[0]['url']}"
    plantilla = (RAIZ / PLANTILLA_PR).read_text(encoding="utf-8")
    cuerpo = cuerpo_pr(
        plantilla,
        feature=feature_id,
        base=base,
        commits="\n".join(f"- {c}" for c in commits),
        excepcion=f"Excepción de tamaño: {args.motivo_grande}" if args.motivo_grande else "",
        cierre=f"Cierra-Feature: {feature_id}" if args.final else "Parte de la pila; no cierra la feature.",
    )
    return _ejecutar("gh", "pr", "create", "--base", base, "--head", rama, "--title", titulo, "--body-file", "-", entrada=cuerpo)


def _analizador():
    analizador = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    comandos = analizador.add_subparsers(dest="comando", required=True)
    lista = comandos.add_parser("empezables", help="lista lo que se puede tomar")
    lista.add_argument("--responsable", help="K, N o J")
    lista.set_defaults(accion=empezables)
    toma = comandos.add_parser("trabajar", help="crea la rama de la feature o de su siguiente parte")
    toma.add_argument("feature", type=str.upper)
    toma.add_argument("descripcion")
    toma.set_defaults(accion=trabajar)
    comandos.add_parser("aprobar", help="registra la aprobación humana del SPEC").set_defaults(accion=aprobar)
    cerrar = comandos.add_parser("cierre", help="valida, publica y abre la PR")
    cerrar.add_argument("--tipo", required=True, choices=TIPOS)
    cerrar.add_argument("--resumen", required=True)
    cerrar.add_argument("--final", action="store_true", help="última parte: la PR cierra la feature")
    cerrar.add_argument("--motivo-grande", help="justifica superar el límite de tamaño")
    cerrar.set_defaults(accion=cierre)
    return analizador


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    args = _analizador().parse_args()
    try:
        args.accion(args)
    except subprocess.CalledProcessError as error:
        _fallar(f"{' '.join(error.cmd)}\n{error.stderr}")


if __name__ == "__main__":
    main()
