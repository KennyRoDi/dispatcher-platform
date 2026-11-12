#!/usr/bin/env python3
"""Ciclo de trabajo común a todos los agentes y personas. Ver AGENTS.md y CONTRIBUTING.md.

    python scripts/flujo.py soy <usuario-github>
    python scripts/flujo.py empezables [--todas]
    python scripts/flujo.py trabajar F-XX ["descripcion"]
    python scripts/flujo.py fase
    python scripts/flujo.py verificar --herramienta "x" --resumen "qué se comprobó"
    python scripts/flujo.py aprobar [--excepcion "motivo"]
    python scripts/flujo.py devolver <fase> "motivo"
    python scripts/flujo.py bitacora --herramienta "x" --proposito "x" ... | --sin-ia
    python scripts/flujo.py cierre --tipo feat --resumen "texto" [--final]
    python scripts/flujo.py fusionar <numero-de-pr>
    python scripts/flujo.py status

docs/STATUS.md se deriva de la fase declarada en cada SPEC.md. Él y la bitácora se publican en la rama `estado`.
Solo usa la biblioteca estándar, git y, para abrir PR, gh.
"""
import argparse
import dataclasses
import datetime
import importlib.util
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile
import unicodedata

FASES = ("plan", "tests", "implementacion", "verificacion", "documentacion", "revision")
PR_ABIERTA = "pr"
CERRADA = "cerrada"
ORDEN_FASES = (*FASES, PR_ABIERTA)
EN_PR = "en-pr"
ACTIVOS = (*FASES, EN_PR)
APILABLES = tuple(e for e in ACTIVOS if e != "plan")
TIPOS = ("feat", "fix", "docs", "test", "refactor", "perf", "build", "ci", "chore", "style", "revert")
LIMITE_LINEAS = 400
STATUS = "docs/STATUS.md"
BACKLOG = "docs/backlog"
EQUIPO = "docs/EQUIPO.md"
RESPONSABLES_COMPARTIDOS = ("Todos", "Cada responsable")
USUARIO_SIN_CONFIRMAR = "por-confirmar"
RAMA_ESTADO = "estado"
BITACORA = "docs/BITACORA_IA.md"
PLANTILLA_SPEC = "docs/specs/PLANTILLA.md"
PLANTILLA_PR = ".github/pull_request_template.md"
EXCLUIDOS_DEL_TAMANO = (":!tests", ":!docs", ":!*.md")
PRUEBAS_RAPIDAS = ("-m", "not integration and not acceptance")
RAIZ = pathlib.Path(__file__).resolve().parents[1]

_TRABAJO_POR_FASE = {
    "plan": ("arquitecto", "Completa docs/specs/{feature}/SPEC.md: reemplaza cada … y define el plan de pila."),
    "tests": ("developer", "Escribe todas las pruebas de esta parte y déjalas en rojo. Sin código de implementación."),
    "implementacion": ("developer", "Implementa lo mínimo para ponerlas en verde y refactoriza."),
    "verificacion": ("qa-tester, medidor si el SPEC tiene mediciones", "Comprueba cada criterio, intenta romperlo y ejecuta las mediciones."),
    "documentacion": ("documentador", "Actualiza fichas, arquitectura, reutilización y README. Registra el uso de IA con `flujo.py bitacora`."),
    "revision": ("revisor", "Compara el diff con el SPEC e informa APROBADO o DEVUELTO."),
}

CAMPOS_BITACORA = ("herramienta", "proposito", "consulta", "resultado", "validado", "como")

_CONVENTIONAL = re.compile(rf"^({'|'.join(TIPOS)})(\([\w./-]+\))?!?: \S")
_ENCABEZADO_US = re.compile(r"^### (US-\d+) · .*\((F-\d+)\)", re.M)
_METADATOS = re.compile(r"\*\*Responsable:\*\* (.+?) · \*\*Depende de:\*\* (.+)")
_FILA_EQUIPO = re.compile(r"^\| ([\w-]+) \| ([A-Z]) \| ([^|]+?) \|", re.M)
_RAMA = re.compile(r"^feat/(F-\d+)-(\d+)-")
_CAMPO_FASE = re.compile(r"^\*\*Fase:\*\* ([\w-]+)$", re.M)
_CAMPO_BASE = re.compile(r"^\*\*Base:\*\* (\S+)$", re.M)
_CAMPO_VERIFICACION = re.compile(r"^\*\*Verificación IA:\*\* .*$", re.M)


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

    @property
    def historia_id(self):
        return self.historia.split(" · ", 1)[0].removeprefix("### ")


@dataclasses.dataclass(frozen=True)
class Integrante:
    usuario: str
    letra: str
    nombre: str


@dataclasses.dataclass(frozen=True)
class Clasificacion:
    tipo: str
    base: str = ""
    motivo: str = ""


def fase_de(spec):
    coincidencia = _CAMPO_FASE.search(spec)
    if not coincidencia:
        raise ValueError("el SPEC no declara **Fase:**")
    return coincidencia.group(1)


def base_de_spec(spec):
    coincidencia = _CAMPO_BASE.search(spec)
    return coincidencia.group(1) if coincidencia else "main"


def estado_feature(spec_main, spec_rama):
    if spec_main and fase_de(spec_main) == CERRADA:
        return "hecha"
    spec = spec_rama or spec_main
    if not spec:
        return "pendiente"
    fase = fase_de(spec)
    return EN_PR if fase in (PR_ABIERTA, CERRADA) else fase


def generar_status(estados):
    filas = "".join(f"| {f} | {estados[f]} |\n" for f in sorted(estados))
    return ("<!-- Generado por scripts/flujo.py. No editar. -->\n"
            f"# Estado\n\n| Feature | Estado |\n|---|---|\n{filas}")


def _registrar(spec, fase, nombre, fecha, nota=""):
    nota = nota.replace("|", "/")
    return f"{spec.rstrip()}\n| {fase} | {nombre} | {fecha} | {nota} |\n"


def fijar_fase(spec, fase, base=None):
    spec = _CAMPO_FASE.sub(f"**Fase:** {fase}", spec, count=1)
    return _CAMPO_BASE.sub(f"**Base:** {base}", spec, count=1) if base else spec


def avanzar_spec(spec, nombre, fecha, excepcion=""):
    fase = fase_de(spec)
    if fase not in FASES:
        raise ValueError(f"la fase {fase} no requiere aprobación")
    siguiente = ORDEN_FASES[ORDEN_FASES.index(fase) + 1]
    return fijar_fase(_registrar(spec, fase, nombre, fecha, excepcion), siguiente)


def devolver_spec(spec, destino, nombre, fecha, motivo):
    fase = fase_de(spec)
    if fase not in FASES or destino not in FASES or FASES.index(destino) >= FASES.index(fase):
        raise ValueError(f"no se puede devolver de {fase} a {destino}")
    return fijar_fase(_registrar(spec, f"devuelta de {fase}", nombre, fecha, motivo), destino)


def _asunto_verificacion(feature, fase):
    return f"docs({feature}): registrar verificacion {fase}"


def registrar_verificacion(spec, fase, sha, herramienta, fecha, resumen):
    if not _CAMPO_VERIFICACION.search(spec):
        raise ValueError("el SPEC no declara **Verificación IA:**")
    con_campo = _CAMPO_VERIFICACION.sub(f"**Verificación IA:** {fase} {sha}", spec, count=1)
    return _registrar(con_campo, f"verificación IA de {fase}", herramienta, fecha, f"{resumen} ({sha})")


def verificacion_vigente(spec, fase, asuntos_posteriores):
    campo = _CAMPO_VERIFICACION.search(spec)
    partes = campo.group(0).split()[2:] if campo else []
    if len(partes) != 2 or partes[0] != fase or len(asuntos_posteriores) != 1:
        return False
    return asuntos_posteriores[0].endswith(f"): registrar verificacion {fase}")


def _celda(texto):
    return " ".join(texto.replace("|", "/").split())


def _encabezado_entrada(fecha, integrante, componente, rama):
    return f"## {fecha} · {integrante} · {componente} (`{rama}`)\n\n| Campo | Contenido |\n|---|---|\n"


def entrada_bitacora(fecha, integrante, componente, rama, herramienta, proposito, consulta,
                     resultado, validado, como, error_ia=""):
    campos = [("Herramienta", herramienta), ("Componente", componente), ("Propósito", proposito),
              ("Consulta resumida", consulta), ("Resultado obtenido", resultado),
              ("Validado / corregido / descartado", validado), ("Cómo se validó", como)]
    if error_ia:
        campos.append(("Error de la IA", error_ia))
    filas = "".join(f"| {campo} | {_celda(valor)} |\n" for campo, valor in campos)
    return _encabezado_entrada(fecha, integrante, componente, rama) + filas


def entrada_sin_ia(fecha, integrante, componente, rama):
    return _encabezado_entrada(fecha, integrante, componente, rama) + f"| Uso de IA | No se usó IA en {_celda(componente)}. |\n"


def agregar_entrada(bitacora, entrada):
    return f"{bitacora.rstrip()}\n\n{entrada}"


def bitacora_registra(bitacora, rama):
    return f"(`{rama}`)" in bitacora


def generar_spec(plantilla, feature, base):
    campos = {"feature": feature.id, "titulo": feature.titulo, "base": base,
              "historia": feature.historia_id, "responsable": feature.responsable}
    return cuerpo_pr(plantilla, **campos)


def _es_prueba(archivo):
    return archivo.startswith("tests/")


def _es_codigo(archivo):
    return not (_es_prueba(archivo) or archivo.startswith(("docs/", ".agents/", ".claude/", ".github/"))
                or archivo.endswith(".md"))


def motivos_bloqueo(fase, archivos, spec="", bitacora_registrada=True):
    if fase == "plan" and "…" in spec:
        return ["el SPEC aún tiene campos … sin completar"]
    if fase == "tests":
        motivos = []
        if not any(_es_prueba(a) for a in archivos):
            motivos.append("no hay pruebas nuevas")
        codigo = [a for a in archivos if _es_codigo(a)]
        if codigo:
            motivos.append(f"la fase de tests no admite código: {', '.join(codigo)}")
        return motivos
    if fase == "implementacion" and not any(_es_codigo(a) for a in archivos):
        return ["no hay código de implementación"]
    if fase == "documentacion" and not bitacora_registrada:
        return [f"falta la entrada de esta rama en {BITACORA}; usa `flujo.py bitacora`"]
    return []


def parsear_backlog(texto):
    encabezados = list(_ENCABEZADO_US.finditer(texto))
    features = {}
    for i, encabezado in enumerate(encabezados):
        fin = encabezados[i + 1].start() if i + 1 < len(encabezados) else len(texto)
        historia = re.split(r"^## ", texto[encabezado.start():fin], flags=re.M)[0].strip()
        metadatos = _METADATOS.search(historia)
        feature_id = encabezado.group(2)
        if not metadatos:
            raise ValueError(f"{feature_id} no declara responsable y dependencias")
        deps = tuple(re.findall(r"F-\d+", metadatos.group(2)))
        features[feature_id] = Feature(feature_id, metadatos.group(1), deps, historia)
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


def clasificar(features, estados, ramas):
    return {f.id: _clasificar_una(f, estados, ramas) for f in features.values()}


def _clasificar_una(feature, estados, ramas):
    estado = estados.get(feature.id, "pendiente")
    if estado == "hecha":
        return Clasificacion("hecha")
    if estado in ACTIVOS:
        return Clasificacion("activa", motivo=estado)
    faltantes = [d for d in feature.deps if estados.get(d, "pendiente") != "hecha"]
    if not faltantes:
        return Clasificacion("empezable", base="main")
    if len(faltantes) == 1 and estados.get(faltantes[0]) in APILABLES and ramas.get(faltantes[0]):
        return Clasificacion("apilable", base=ramas[faltantes[0]][-1], motivo=f"sobre {faltantes[0]}")
    return Clasificacion("bloqueada", motivo="falta " + ", ".join(faltantes))


def parsear_equipo(texto):
    filas = _FILA_EQUIPO.findall(texto)
    return {u.lower(): Integrante(u, l, n) for u, l, n in filas if u != USUARIO_SIN_CONFIRMAR}


def letras_de_equipo(texto):
    return {letra for _usuario, letra, _nombre in _FILA_EQUIPO.findall(texto)}


def corresponde_a(feature, letra):
    return feature.responsable == letra or feature.responsable in RESPONSABLES_COMPARTIDOS


def desbloqueadoras(features, clases, letra):
    encontradas, pendientes, vistas = set(), [f.id for f in features.values() if corresponde_a(f, letra)], set()
    while pendientes:
        actual = pendientes.pop()
        for dep in features[actual].deps:
            if dep in vistas:
                continue
            vistas.add(dep)
            pendientes.append(dep)
            if clases[dep].tipo in ("empezable", "apilable") and not corresponde_a(features[dep], letra):
                encontradas.add(dep)
    return sorted(encontradas)


def hijas_de(prs, rama):
    return [pr["number"] for pr in prs if pr["baseRefName"] == rama]


def partes_cerradas(spec):
    return spec.count("\n| revision |")


def nombre_rama(feature, descripcion, ramas, cerradas=0):
    sin_acentos = unicodedata.normalize("NFKD", descripcion).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", sin_acentos.lower()).strip("-")
    partes = [int(_RAMA.match(r).group(2)) for r in ramas.get(feature, [])]
    return f"feat/{feature}-{max([*partes, cerradas]) + 1}-{slug}"


def es_conventional(mensaje):
    return bool(_CONVENTIONAL.match(mensaje))


def titulo_pr(tipo, feature, resumen):
    titulo = f"{tipo}({feature}): {resumen}"
    if not es_conventional(titulo):
        raise ValueError(f"título fuera de Conventional Commits: {titulo}")
    return titulo


def cuerpo_pr(plantilla, **campos):
    for clave, valor in campos.items():
        plantilla = plantilla.replace("{" + clave + "}", valor)
    return plantilla


def _ejecutar(*comando, cwd=RAIZ, entrada=None):
    resultado = subprocess.run(comando, cwd=cwd, input=entrada, capture_output=True, text=True, encoding="utf-8")
    if resultado.returncode:
        raise subprocess.CalledProcessError(resultado.returncode, comando, resultado.stdout, resultado.stderr)
    return resultado.stdout.strip()


def git(*args, cwd=RAIZ):
    return _ejecutar("git", *args, cwd=cwd)


def _fallar(mensaje):
    raise SystemExit(f"flujo: {mensaje}")


def _leer_referencia(referencia, ruta):
    try:
        return git("show", f"{referencia}:{ruta}") + "\n"
    except subprocess.CalledProcessError:
        return None


def _leer_main(ruta):
    texto = _leer_referencia("origin/main", ruta)
    if texto is None:
        _fallar(f"{ruta} no existe en origin/main; fusiona primero la pila del flujo")
    return texto


def _leer_backlog_main():
    salida = git("ls-tree", "--name-only", "origin/main", f"{BACKLOG}/")
    rutas = [r for r in salida.splitlines() if r.endswith(".md") and not r.endswith("README.md")]
    if not rutas:
        _fallar(f"{BACKLOG} no existe en origin/main")
    return parsear_backlog("\n".join(_leer_main(r) for r in rutas))


def _integrante_actual():
    equipo = parsear_equipo(_leer_main(EQUIPO))
    try:
        usuario = git("config", "flujo.usuario")
    except subprocess.CalledProcessError:
        _fallar("¿quién eres? Indica tu usuario de GitHub: python scripts/flujo.py soy <usuario>")
    if usuario.lower() not in equipo:
        _fallar(f"{usuario} no está en {EQUIPO}; agrégalo o corrige con `flujo.py soy <usuario>`")
    return equipo[usuario.lower()]


def _ruta_spec(feature):
    return f"docs/specs/{feature}/SPEC.md"


def _ramas_remotas():
    salida = git("ls-remote", "--heads", "origin", "feat/*")
    return [linea.split("refs/heads/")[1] for linea in salida.splitlines()]


def _rama_actual():
    return git("branch", "--show-current")


def _feature_actual():
    rama = _rama_actual()
    coincidencia = _RAMA.match(rama)
    if not coincidencia:
        _fallar(f"la rama {rama!r} no es de una feature; usa `trabajar F-XX`")
    return coincidencia.group(1)


def _leer_spec_local(feature):
    ruta = RAIZ / _ruta_spec(feature)
    if not ruta.exists():
        _fallar(f"falta {_ruta_spec(feature)}")
    return ruta.read_text(encoding="utf-8")


def _guardar_y_confirmar(feature, spec, mensaje):
    ruta = RAIZ / _ruta_spec(feature)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(spec, encoding="utf-8", newline="\n")
    git("add", _ruta_spec(feature))
    git("commit", "-q", "-m", mensaje)


def _exigir_sin_cambios(incluir_nuevos=True):
    opciones = () if incluir_nuevos else ("--untracked-files=no",)
    if git("status", "--porcelain", *opciones):
        _fallar("hay cambios sin commit")


def _base_vigente(spec):
    base = base_de_spec(spec)
    return base if git("ls-remote", "--heads", "origin", base) else "main"


def _estados_actuales(features):
    git("fetch", "-q", "--prune", "origin")
    ramas = ramas_por_feature(_ramas_remotas())
    estados = {}
    for feature_id in features:
        spec_main = _leer_referencia("origin/main", _ruta_spec(feature_id))
        ultima = ramas.get(feature_id, [None])[-1]
        spec_rama = _leer_referencia(f"origin/{ultima}", _ruta_spec(feature_id)) if ultima else None
        estados[feature_id] = estado_feature(spec_main, spec_rama)
    return estados, ramas


def _publicar_en_estado(ruta, generar, mensaje, intentos=3):
    error = ""
    for _ in range(intentos):
        git("fetch", "-q", "origin", RAMA_ESTADO)
        actual = _leer_referencia(f"origin/{RAMA_ESTADO}", ruta)
        nuevo = generar(actual)
        if nuevo == actual:
            return ""
        with tempfile.TemporaryDirectory() as tmp:
            arbol = pathlib.Path(tmp) / "publicacion"
            git("worktree", "add", "-q", "--detach", str(arbol), f"origin/{RAMA_ESTADO}")
            try:
                (arbol / ruta).parent.mkdir(parents=True, exist_ok=True)
                (arbol / ruta).write_text(nuevo, encoding="utf-8", newline="\n")
                git("add", ruta, cwd=arbol)
                git("commit", "-q", "-m", mensaje, cwd=arbol)
                git("push", "-q", "origin", f"HEAD:{RAMA_ESTADO}", cwd=arbol)
                return ""
            except subprocess.CalledProcessError as fallo:
                error = fallo.stderr
            finally:
                git("worktree", "remove", "--force", str(arbol))
    return error or "reintentos agotados"


def publicar_status():
    def generar(_actual):
        estados, _ramas = _estados_actuales(_leer_backlog_main())
        return generar_status(estados)

    error = _publicar_en_estado(STATUS, generar, "chore(status): regenerar")
    if error:
        print(f"aviso: no se pudo publicar {STATUS}: {error}")


def _rama_en_bitacora(rama):
    git("fetch", "-q", "origin", RAMA_ESTADO)
    return bitacora_registra(_leer_referencia(f"origin/{RAMA_ESTADO}", BITACORA) or "", rama)


def _archivos_cambiados(base):
    salida = git("diff", "--name-only", f"origin/{base}...HEAD")
    return salida.splitlines()


def _validar_commits(base):
    asuntos = git("log", "--no-merges", "--format=%s", f"origin/{base}..HEAD").splitlines()
    invalidos = [a for a in asuntos if not es_conventional(a)]
    if invalidos:
        _fallar("commits fuera de Conventional Commits; corrígelos:\n  " + "\n  ".join(invalidos))
    return asuntos


def _validar_tamano(base):
    numstat = git("diff", "--numstat", f"origin/{base}...HEAD", "--", ".", *EXCLUIDOS_DEL_TAMANO)
    lineas = sum(int(a) + int(b) for a, b, *_ in (f.split("\t") for f in numstat.splitlines()) if a != "-")
    if lineas > LIMITE_LINEAS:
        _fallar(f"{lineas} líneas sin contar pruebas ni documentos (límite {LIMITE_LINEAS}); "
                "divide con otra parte de la pila")


def _correr_pytest(*argumentos):
    if not importlib.util.find_spec("pytest"):
        _fallar("pytest no está instalado: pip install -r requirements-dev.txt")
    resultado = subprocess.run([sys.executable, "-m", "pytest", "-q", *argumentos], cwd=RAIZ,
                               capture_output=True, text=True, encoding="utf-8", errors="replace",
                               env={**os.environ, "PYTHONUTF8": "1"})
    return resultado.returncode, "\n".join((resultado.stdout or "").splitlines()[-15:])


def _exigir_pruebas_en_verde():
    codigo, salida = _correr_pytest(*PRUEBAS_RAPIDAS)
    if codigo:
        _fallar(f"las pruebas fallan:\n{salida}")


def _exigir_pruebas_en_rojo(archivos):
    pruebas = [a for a in archivos if re.search(r"^tests/.*test_[^/]*\.py$", a) and (RAIZ / a).exists()]
    if not pruebas:
        _fallar("no hay archivos test_*.py nuevos o modificados")
    codigo, salida = _correr_pytest(*pruebas)
    if codigo == 0:
        _fallar(f"las pruebas nuevas ya pasan; deben estar en rojo:\n{salida}")
    if codigo == 5:
        _fallar("los archivos de prueba no contienen pruebas")


def _imprimir_fase(feature, fase):
    if fase in (PR_ABIERTA, CERRADA):
        print(f"{feature}: fases aprobadas. Siguiente: `cierre`, o `trabajar {feature}` para la siguiente parte.")
        return
    rol, trabajo = _TRABAJO_POR_FASE[fase]
    print(f"{feature} · fase {FASES.index(fase) + 1}/{len(FASES)}: {fase}")
    print(f"Subagente: {rol} (.agents/roles/)")
    print(f"Debe hacer: {trabajo.format(feature=feature)}")
    print("Orquestador: verifica su trabajo según .agents/roles/orquestador.md y registra con `flujo.py verificar`.")
    print("Luego DETENTE a pedir aprobación. Solo con un sí explícito de la persona: python scripts/flujo.py aprobar")


def cmd_soy(args):
    git("fetch", "-q", "origin", "main")
    integrante = parsear_equipo(_leer_main(EQUIPO)).get(args.usuario.lower())
    if not integrante:
        _fallar(f"{args.usuario} no está en {EQUIPO}")
    git("config", "flujo.usuario", integrante.usuario)
    print(f"Hola, {integrante.nombre} ({integrante.usuario}). Responsable: {integrante.letra}")


def _imprimir_grupo(titulo, filas, clases):
    print(titulo)
    for feature in filas:
        clase = clases[feature.id]
        detalle = clase.motivo if clase.tipo in ("activa", "bloqueada") else f"base {clase.base}"
        print(f"  {feature.id} [{feature.responsable}] {feature.titulo}: {detalle}")
    if not filas:
        print("  (ninguna)")


def cmd_empezables(args):
    git("fetch", "-q", "--prune", "origin")
    integrante = None if args.todas else _integrante_actual()
    publicar_status()
    features = _leer_backlog_main()
    estados, ramas = _estados_actuales(features)
    clases = clasificar(features, estados, ramas)
    visibles = list(features.values())
    if integrante:
        print(f"{integrante.nombre} ({integrante.usuario})\n")
        visibles = [f for f in visibles if corresponde_a(f, integrante.letra)]
    for tipo, titulo in (("empezable", "EMPEZABLES"), ("apilable", "APILABLES"), ("activa", "ACTIVAS"), ("bloqueada", "BLOQUEADAS")):
        _imprimir_grupo(titulo, [f for f in visibles if clases[f.id].tipo == tipo], clases)
    if integrante:
        ajenas = desbloqueadoras(features, clases, integrante.letra)
        _imprimir_grupo("AJENAS QUE TE DESBLOQUEAN", [features[f] for f in ajenas], clases)


def cmd_status(_args):
    git("fetch", "-q", "--prune", "origin")
    publicar_status()
    print(f"{STATUS} al día en origin/{RAMA_ESTADO}")


def cmd_trabajar(args):
    feature_id = args.feature
    _exigir_sin_cambios(incluir_nuevos=False)
    git("fetch", "-q", "--prune", "origin")
    features = _leer_backlog_main()
    if feature_id not in features:
        _fallar(f"{feature_id} no está en {BACKLOG}")
    feature = features[feature_id]
    integrante = _integrante_actual()
    if not corresponde_a(feature, integrante.letra):
        print(f"aviso: {feature_id} es de {feature.responsable}; la tomas como apoyo\n")
    estados, ramas = _estados_actuales(features)
    if estados[feature_id] == "hecha":
        _fallar(f"{feature_id} ya está hecha")
    descripcion = args.descripcion or feature.titulo

    if ramas.get(feature_id) or _rama_actual().startswith(f"feat/{feature_id}-"):
        _continuar_en_rama(feature_id, descripcion, ramas)
    else:
        _iniciar_sin_rama(feature, descripcion, features, estados, ramas)
    publicar_status()
    print(feature.historia, "\n")
    _imprimir_fase(feature_id, fase_de(_leer_spec_local(feature_id)))


def _continuar_en_rama(feature_id, descripcion, ramas):
    if not _rama_actual().startswith(f"feat/{feature_id}-"):
        print(f"aviso: {feature_id} ya está activa; retomas su rama {ramas[feature_id][-1]}\n")
        git("switch", "-q", ramas[feature_id][-1])
    elif ramas.get(feature_id) and _rama_actual() != ramas[feature_id][-1]:
        git("switch", "-q", ramas[feature_id][-1])
    actual = _rama_actual()
    git("pull", "-q", "--ff-only", "origin", actual)
    fase = fase_de(_leer_spec_local(feature_id))
    if fase == PR_ABIERTA:
        _crear_parte(feature_id, descripcion, actual, f"origin/{actual}", ramas)
    elif fase == CERRADA:
        _fallar(f"{feature_id} está cerrada; falta revisar y fusionar su PR")


def _iniciar_sin_rama(feature, descripcion, features, estados, ramas):
    spec_main = _leer_referencia("origin/main", _ruta_spec(feature.id))
    if spec_main:
        if fase_de(spec_main) != PR_ABIERTA:
            _fallar(f"{feature.id} no tiene rama y su SPEC en main está en fase {fase_de(spec_main)}")
        _crear_parte(feature.id, descripcion, "main", "origin/main", ramas)
        return
    clase = clasificar(features, estados, ramas)[feature.id]
    if clase.tipo == "bloqueada":
        _fallar(f"{feature.id} está bloqueada: {clase.motivo}")
    rama = nombre_rama(feature.id, descripcion, ramas)
    git("switch", "-q", "--no-track", "-c", rama, f"origin/{clase.base}")
    plantilla = (RAIZ / PLANTILLA_SPEC).read_text(encoding="utf-8")
    _guardar_y_confirmar(feature.id, generar_spec(plantilla, feature, clase.base), f"docs({feature.id}): iniciar spec")
    git("push", "-q", "-u", "origin", rama)


def _crear_parte(feature_id, descripcion, base, referencia, ramas):
    spec_base = _leer_referencia(referencia, _ruta_spec(feature_id)) or ""
    rama = nombre_rama(feature_id, descripcion, ramas, partes_cerradas(spec_base))
    git("switch", "-q", "--no-track", "-c", rama, referencia)
    spec = fijar_fase(_leer_spec_local(feature_id), "tests", base)
    _guardar_y_confirmar(feature_id, spec, f"docs({feature_id}): iniciar nueva parte")
    git("push", "-q", "-u", "origin", rama)


def cmd_fase(_args):
    feature_id = _feature_actual()
    _imprimir_fase(feature_id, fase_de(_leer_spec_local(feature_id)))


def cmd_verificar(args):
    feature_id = _feature_actual()
    _exigir_sin_cambios()
    spec = _leer_spec_local(feature_id)
    fase = fase_de(spec)
    if fase not in FASES:
        _fallar(f"la fase {fase} no requiere verificación")
    sha = git("rev-parse", "--short", "HEAD")
    hoy = datetime.date.today().isoformat()
    nuevo = registrar_verificacion(spec, fase, sha, args.herramienta, hoy, args.resumen)
    _guardar_y_confirmar(feature_id, nuevo, _asunto_verificacion(feature_id, fase))
    git("push", "-q", "origin", _rama_actual())
    print(f"{feature_id}: verificación de {fase} registrada sobre {sha}. Pide la aprobación de la persona.")


def _sha_verificado(spec):
    return _CAMPO_VERIFICACION.search(spec).group(0).split()[-1]


def _exigir_verificacion(spec, fase):
    campo = _CAMPO_VERIFICACION.search(spec)
    if not campo or len(campo.group(0).split()) != 4:
        _fallar(f"falta la verificación de IA de la fase {fase}; usa `flujo.py verificar`")
    try:
        asuntos = git("log", "--format=%s", f"{_sha_verificado(spec)}..HEAD").splitlines()
    except subprocess.CalledProcessError:
        asuntos = []
    if not verificacion_vigente(spec, fase, asuntos):
        _fallar(f"la verificación de IA de la fase {fase} no está vigente: "
                "hubo cambios después o es de otra fase; verifica de nuevo")


def cmd_aprobar(args):
    feature_id = _feature_actual()
    _exigir_sin_cambios()
    spec = _leer_spec_local(feature_id)
    fase = fase_de(spec)
    if fase not in FASES:
        _fallar(f"la fase {fase} no requiere aprobación")
    _exigir_verificacion(spec, fase)
    base = _base_vigente(spec)
    git("fetch", "-q", "origin", base)
    _validar_commits(base)
    if not args.excepcion:
        _comprobar_fase(fase, _archivos_cambiados(base), spec, base, _rama_actual())
    nombre = git("config", "user.name")
    hoy = datetime.date.today().isoformat()
    nuevo = avanzar_spec(spec, nombre, hoy, args.excepcion or "")
    _guardar_y_confirmar(feature_id, nuevo, f"docs({feature_id}): aprobar fase {fase}")
    git("push", "-q", "origin", _rama_actual())
    publicar_status()
    _imprimir_fase(feature_id, fase_de(nuevo))


def _comprobar_fase(fase, archivos, spec, base, rama):
    registrada = fase != "documentacion" or _rama_en_bitacora(rama)
    motivos = motivos_bloqueo(fase, archivos, spec, registrada)
    if motivos:
        _fallar(f"la fase {fase} no se puede aprobar: " + "; ".join(motivos))
    if fase == "tests":
        _exigir_pruebas_en_rojo(archivos)
    if fase in ("implementacion", "verificacion"):
        _exigir_pruebas_en_verde()
        _validar_tamano(base)


def cmd_devolver(args):
    feature_id = _feature_actual()
    _exigir_sin_cambios()
    spec = _leer_spec_local(feature_id)
    hoy = datetime.date.today().isoformat()
    try:
        nuevo = devolver_spec(spec, args.fase, git("config", "user.name"), hoy, args.motivo)
    except ValueError as error:
        _fallar(str(error))
    _guardar_y_confirmar(feature_id, nuevo, f"docs({feature_id}): devolver a {args.fase}")
    git("push", "-q", "origin", _rama_actual())
    publicar_status()
    _imprimir_fase(feature_id, args.fase)


def cmd_bitacora(args):
    rama = _rama_actual()
    coincidencia = _RAMA.match(rama)
    componente = args.componente or (coincidencia and coincidencia.group(1))
    if not componente:
        _fallar("fuera de una rama de feature, indica --componente")
    fecha = datetime.date.today().isoformat()
    integrante = git("config", "user.name")
    if args.sin_ia:
        entrada = entrada_sin_ia(fecha, integrante, componente, rama)
    else:
        faltantes = [c for c in CAMPOS_BITACORA if not getattr(args, c)]
        if faltantes:
            _fallar("faltan campos: " + ", ".join(f"--{c}" for c in faltantes) + "; o usa --sin-ia")
        campos = {c: getattr(args, c) for c in CAMPOS_BITACORA}
        entrada = entrada_bitacora(fecha, integrante, componente, rama, error_ia=args.error_ia or "", **campos)
    error = _publicar_en_estado(BITACORA, lambda actual: agregar_entrada(actual, entrada),
                              f"docs(bitacora): registrar {componente}")
    if error:
        _fallar(f"no se pudo publicar {BITACORA}: {error}")
    print(f"{BITACORA}: entrada de {componente} publicada en la rama {RAMA_ESTADO}")


def cmd_cierre(args):
    rama = _rama_actual()
    feature_id = _feature_actual()
    _exigir_sin_cambios()
    spec = _leer_spec_local(feature_id)
    if fase_de(spec) not in (PR_ABIERTA, CERRADA):
        _fallar(f"faltan aprobaciones; la feature está en fase {fase_de(spec)}")
    try:
        titulo = titulo_pr(args.tipo, feature_id, args.resumen)
    except ValueError as error:
        _fallar(str(error))
    base = _base_vigente(spec)
    git("fetch", "-q", "origin", base)
    _validar_tamano(base)
    _exigir_pruebas_en_verde()
    if not _rama_en_bitacora(rama):
        _fallar(f"falta la entrada de esta rama en {BITACORA}; usa `flujo.py bitacora`")
    if args.final and fase_de(spec) != CERRADA:
        _guardar_y_confirmar(feature_id, fijar_fase(spec, CERRADA), f"docs({feature_id}): cerrar feature")
    asuntos = _validar_commits(base)
    git("push", "-q", "-u", "origin", rama)
    print(_abrir_pr(rama, base, titulo, feature_id, asuntos, args.final))
    publicar_status()


def cmd_fusionar(args):
    pr = json.loads(_ejecutar("gh", "pr", "view", args.numero, "--json", "number,headRefName,baseRefName,state"))
    if pr["state"] != "OPEN":
        _fallar(f"la PR #{pr['number']} no está abierta")
    if pr["baseRefName"] != "main":
        _fallar(f"la PR #{pr['number']} va sobre {pr['baseRefName']}; fusiona primero la de abajo")
    rama = pr["headRefName"]
    _ejecutar("gh", "pr", "merge", args.numero, "--merge")
    abiertas = json.loads(_ejecutar("gh", "pr", "list", "--state", "open", "--limit", "200", "--json", "number,baseRefName"))
    repo = _ejecutar("gh", "repo", "view", "--json", "nameWithOwner", "--jq", ".nameWithOwner")
    # Borrar la rama antes de cambiar la base hace que GitHub cierre las PR apiladas encima.
    # `gh pr edit --base` falla con Projects classic; la API REST no.
    for hija in hijas_de(abiertas, rama):
        _ejecutar("gh", "api", "-X", "PATCH", f"repos/{repo}/pulls/{hija}", "-f", "base=main", "--silent")
        print(f"PR #{hija}: base cambiada a main")
    git("push", "-q", "origin", "--delete", rama)
    publicar_status()
    print(f"PR #{pr['number']} fusionada y rama {rama} borrada")


def _abrir_pr(rama, base, titulo, feature_id, asuntos, final):
    existente = json.loads(_ejecutar("gh", "pr", "list", "--head", rama, "--state", "open", "--json", "url"))
    if existente:
        return f"PR existente actualizada: {existente[0]['url']}"
    cuerpo = cuerpo_pr(
        (RAIZ / PLANTILLA_PR).read_text(encoding="utf-8"),
        feature=feature_id,
        base=base,
        commits="\n".join(f"- {a}" for a in asuntos),
        cierre="Esta PR cierra la feature." if final else "Parte de la pila; la feature sigue abierta.",
    )
    return _ejecutar("gh", "pr", "create", "--base", base, "--head", rama, "--title", titulo,
                     "--body-file", "-", entrada=cuerpo)


def _analizador():
    analizador = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    comandos = analizador.add_subparsers(dest="comando", required=True)
    identidad = comandos.add_parser("soy", help="registra tu usuario de GitHub en este clon")
    identidad.add_argument("usuario")
    identidad.set_defaults(accion=cmd_soy)
    lista = comandos.add_parser("empezables", help="lista lo que se puede tomar")
    lista.add_argument("--todas", action="store_true", help="muestra las de todo el equipo")
    lista.set_defaults(accion=cmd_empezables)
    comandos.add_parser("status", help="regenera docs/STATUS.md").set_defaults(accion=cmd_status)
    toma = comandos.add_parser("trabajar", help="inicia o retoma una feature, o abre su siguiente parte")
    toma.add_argument("feature", type=str.upper)
    toma.add_argument("descripcion", nargs="?")
    toma.set_defaults(accion=cmd_trabajar)
    comandos.add_parser("fase", help="muestra la fase actual y qué hacer").set_defaults(accion=cmd_fase)
    verificar = comandos.add_parser("verificar", help="registra la verificación de IA del orquestador")
    verificar.add_argument("--herramienta", required=True)
    verificar.add_argument("--resumen", required=True, help="qué se comprobó y con qué comandos")
    verificar.set_defaults(accion=cmd_verificar)
    aprobar = comandos.add_parser("aprobar", help="registra la aprobación humana y avanza una fase")
    aprobar.add_argument("--excepcion", help="motivo para omitir las comprobaciones; autorizado por una persona")
    aprobar.set_defaults(accion=cmd_aprobar)
    devolver = comandos.add_parser("devolver", help="regresa a una fase anterior")
    devolver.add_argument("fase", choices=FASES)
    devolver.add_argument("motivo")
    devolver.set_defaults(accion=cmd_devolver)
    registro = comandos.add_parser("bitacora", help="publica una entrada en la bitácora de IA")
    registro.add_argument("--componente", help="por defecto, la feature de la rama actual")
    registro.add_argument("--sin-ia", action="store_true", help="declara que no se usó IA")
    registro.add_argument("--error-ia", help="error o imprecisión de la IA detectado y cómo se resolvió")
    for campo in CAMPOS_BITACORA:
        registro.add_argument(f"--{campo}")
    registro.set_defaults(accion=cmd_bitacora)
    cerrar = comandos.add_parser("cierre", help="valida, publica y abre la PR")
    cerrar.add_argument("--tipo", required=True, choices=TIPOS)
    cerrar.add_argument("--resumen", required=True)
    cerrar.add_argument("--final", action="store_true", help="última parte: la PR cierra la feature")
    cerrar.set_defaults(accion=cmd_cierre)
    fusion = comandos.add_parser("fusionar", help="fusiona una PR sobre main y reubica las apiladas encima")
    fusion.add_argument("numero")
    fusion.set_defaults(accion=cmd_fusionar)
    return analizador


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    args = _analizador().parse_args()
    try:
        args.accion(args)
    except subprocess.CalledProcessError as error:
        _fallar(f"{' '.join(map(str, error.cmd))}\n{error.stderr.strip()}")
    except FileNotFoundError as error:
        _fallar(f"falta {error.filename}; instala git y gh")
    except ValueError as error:
        _fallar(str(error))


if __name__ == "__main__":
    main()
