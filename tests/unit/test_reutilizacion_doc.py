import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT / "docs" / "reutilizacion.md"
ARQUITECTURA = ROOT / "docs" / "ARQUITECTURA.md"
DECISIONES = ROOT / "docs" / "DECISIONES_DISENO.md"
I_PROYECTO_COMMIT = "bc6bab6"

PATH_PREFIXES = (
    "src/", "scripts/", "tests/", "docs/", "deploy/",
    "dashboard/", "config/", "scenarios/", "benchmarks/",
)
CODE_PREFIXES = ("src/", "scripts/", "deploy/", "docs/evidencia")
STATES_COMPONENTES = {"reutilizado", "modificado", "nuevo"}
STATES_DEFICIENCIAS = {"corregida", "parcial", "pendiente", "no aplica"}
BACKTICKED = re.compile(r"`([^`]+)`")
LINK = re.compile(r"AD-\d+|F-\d+|#\d+|tests/\S+|docs/evidencia\S*")

TERCEROS_HEADER = ["Feature", "Componente", "Fuente", "Licencia", "Cambio"]
TERCEROS_FILAS_ORIGINALES = [
    "| F-12 | Sin terceros en F-12 | F-12 usa solo biblioteca estándar (`signal`, `shutil`, `threading`, `logging`) | — | — |",
    "| F-36 | Sin terceros en F-36 | F-36 usa solo biblioteca estándar de Python | — | — |",
    "| F-06 | Sin terceros en F-06 | F-06 usa Redis (ya dependencia) vía `redis-py`; la corrección de la ventana de pérdida se documenta en AD-03, `docs/ARQUITECTURA.md` | — | — |",
]

LIMITACIONES_PALABRAS_CLAVE = [
    ["BLPOP"],
    ["alta disponibilidad"],
    ["FFmpeg"],
    ["estricta", "NPU"],
    ["sin GPU"],
]


def read(path):
    return path.read_text(encoding="utf-8")


def sections(text):
    parts = re.split(r"(?m)^## (\d+)\.[^\n]*\n", text)
    return {int(number): body for number, body in zip(parts[1::2], parts[2::2])}


def heading(text, number):
    return re.search(rf"(?m)^## {number}\.[^\n]*", text).group(0)


def table_rows(body):
    lines = [ln.strip() for ln in body.splitlines()]
    rows = []
    for index, line in enumerate(lines):
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if all(re.fullmatch(r":?-+:?", c) for c in cells):
            continue
        following = lines[index + 1] if index + 1 < len(lines) else ""
        if re.fullmatch(r"\|[\s:|-]+\|", following):
            continue
        rows.append((line, cells))
    return rows


def normalized_state(cell):
    return cell.replace("`", "").replace("*", "").strip().lower()


def row_state(cells, allowed):
    return [c for c in cells if normalized_state(c) in allowed]


def expand_braces(token):
    match = re.search(r"\{([^{}]*)\}", token)
    if not match:
        return [token]
    return [
        expanded
        for option in match.group(1).split(",")
        for expanded in expand_braces(token[:match.start()] + option + token[match.end():])
    ]


def checkable_path(token):
    token = re.sub(r":\d+(-\d+)?$", "", token.strip())
    if re.search(r"[*<>\s]|\{", token):
        return None
    return token if token.startswith(PATH_PREFIXES) else None


def backticked(text):
    return BACKTICKED.findall(text)


@pytest.fixture(scope="module")
def doc():
    return read(DOC)


@pytest.fixture(scope="module")
def doc_sections(doc):
    found = sections(doc)
    assert sorted(found) == [1, 2, 3, 4, 5], "docs/reutilizacion.md sin reescribir en cinco secciones"
    return found


def test_el_documento_tiene_las_cinco_secciones(doc):
    assert sorted(sections(doc)) == [1, 2, 3, 4, 5]
    assert "Terceros por feature" in heading(doc, 5)


def test_el_documento_declara_el_comando_para_repetir_la_clasificacion(doc_sections):
    origen = doc_sections[1]
    assert I_PROYECTO_COMMIT in origen
    assert "git diff" in origen


def test_toda_ruta_citada_existe_en_el_arbol(doc):
    inexistentes = []
    for token in backticked(doc):
        path = checkable_path(token)
        if path and not (ROOT / path).exists():
            inexistentes.append(path)
    assert inexistentes == []


def test_cada_fila_de_componentes_tiene_estado_y_ruta(doc_sections):
    rows = table_rows(doc_sections[2])
    assert rows, "la sección 2 no tiene filas"
    sin_estado = [line for line, cells in rows if len(row_state(cells, STATES_COMPONENTES)) != 1]
    sin_ruta = [line for line, _ in rows if not backticked(line)]
    assert sin_estado == []
    assert sin_ruta == []


def test_la_seccion_de_componentes_usa_los_tres_estados(doc_sections):
    usados = {
        normalized_state(c)
        for _, cells in table_rows(doc_sections[2])
        for c in row_state(cells, STATES_COMPONENTES)
    }
    assert usados == STATES_COMPONENTES


def test_cada_deficiencia_tiene_estado_y_enlace(doc_sections):
    rows = table_rows(doc_sections[4])
    assert rows, "la sección 4 no tiene filas"
    sin_estado = [line for line, cells in rows if len(row_state(cells, STATES_DEFICIENCIAS)) != 1]
    sin_enlace = [line for line, cells in rows if not LINK.search(" ".join(cells))]
    assert sin_estado == []
    assert sin_enlace == []


def test_toda_ad_y_feature_citada_en_deficiencias_existe(doc_sections):
    arquitectura = read(ARQUITECTURA)
    backlog = "\n".join(read(p) for p in (ROOT / "docs" / "backlog").glob("*.md"))
    citas = " ".join(line for line, _ in table_rows(doc_sections[4]))
    ads_existentes = set(re.findall(r"(?m)^\| (AD-\d+) \|", arquitectura))
    ads = set(re.findall(r"AD-\d+", citas))
    features = set(re.findall(r"\bF-\d+", citas))
    features_sin_historia = [
        f for f in features
        if not (ROOT / "docs" / "specs" / f).is_dir() and f"({f})" not in backlog
    ]
    assert sorted(ads - ads_existentes) == []
    assert sorted(features_sin_historia) == []


def test_una_deficiencia_corregida_cita_ruta_de_codigo_o_evidencia_existente(doc_sections):
    sin_ruta = []
    for line, cells in table_rows(doc_sections[4]):
        if not [c for c in cells if normalized_state(c).startswith("corregida")]:
            continue
        rutas = [
            expanded
            for token in backticked(line)
            for expanded in expand_braces(token)
            if (path := checkable_path(expanded)) and path.startswith(CODE_PREFIXES)
        ]
        if not any((ROOT / checkable_path(r)).exists() for r in rutas):
            sin_ruta.append(line)
    assert sin_ruta == []


def test_la_seccion_de_deficiencias_tiene_al_menos_una_corregida(doc_sections):
    estados = {
        normalized_state(c)
        for _, cells in table_rows(doc_sections[4])
        for c in row_state(cells, STATES_DEFICIENCIAS)
    }
    assert "corregida" in estados


def test_terceros_conserva_encabezado_de_cinco_columnas(doc_sections):
    rows = table_rows(doc_sections[5])
    assert rows, "la sección 5 no tiene filas"
    raw_header = next(
        ln.strip() for ln in doc_sections[5].splitlines() if ln.strip().startswith("|")
    )
    header = [c.strip() for c in raw_header.strip("|").split("|")]
    assert header == TERCEROS_HEADER
    assert all(len(cells) == 5 for _, cells in rows)


@pytest.mark.parametrize("fila", TERCEROS_FILAS_ORIGINALES, ids=["F-12", "F-36", "F-06"])
def test_terceros_conserva_las_filas_originales(doc_sections, fila):
    lineas = [ln.strip() for ln in doc_sections[5].splitlines()]
    assert fila in lineas


def test_terceros_declara_el_origen_del_i_proyecto(doc_sections):
    filas = [cells for _, cells in table_rows(doc_sections[5]) if cells[0] == "F-39"]
    assert len(filas) == 1
    texto = " ".join(filas[0])
    assert "nahum0804/distributed-processing-platform" in texto
    assert I_PROYECTO_COMMIT in texto


def lineas_arquitectura_1():
    cuerpo = sections(read(ARQUITECTURA))[1]
    return [cells[0] for _, cells in table_rows(cuerpo)]


def test_cada_elemento_de_arquitectura_1_aparece(doc):
    elementos = lineas_arquitectura_1()
    assert len(elementos) == 11
    ausentes = [e for e in elementos if e not in doc]
    assert ausentes == []


def viñetas_limitaciones():
    texto = read(DECISIONES)
    cuerpo = texto.split("## Limitaciones conocidas", 1)[1].split("\n## ", 1)[0]
    return [ln[2:].strip() for ln in cuerpo.splitlines() if ln.startswith("- ")]


def test_las_limitaciones_conocidas_son_las_que_la_prueba_conoce():
    assert len(viñetas_limitaciones()) == len(LIMITACIONES_PALABRAS_CLAVE)


@pytest.mark.parametrize("claves", LIMITACIONES_PALABRAS_CLAVE, ids=lambda c: "+".join(c))
def test_cada_limitacion_conocida_aparece_en_deficiencias(doc_sections, claves):
    texto = doc_sections[4]
    assert all(clave in texto for clave in claves)


def archivos_del_i_proyecto():
    listado = subprocess.run(
        ["git", "ls-tree", "-r", "--name-only", I_PROYECTO_COMMIT],
        cwd=ROOT, capture_output=True, text=True, check=True,
    ).stdout.splitlines()
    return [
        f for f in listado
        if "/" not in f or f.startswith(("src/", "scripts/", "dashboard/", "deploy/", "benchmarks/"))
    ]


def commit_disponible():
    result = subprocess.run(
        ["git", "cat-file", "-e", f"{I_PROYECTO_COMMIT}^{{commit}}"],
        cwd=ROOT, capture_output=True,
    )
    return result.returncode == 0


def test_cubre_cada_archivo_del_i_proyecto(doc_sections):
    if not commit_disponible():
        pytest.skip(f"{I_PROYECTO_COMMIT} no está en este clon")
    tokens = {
        expanded
        for token in backticked(doc_sections[2])
        for expanded in expand_braces(token.strip())
    }
    directorios = {t for t in tokens if t.endswith("/")}
    sin_clasificar = [
        archivo for archivo in archivos_del_i_proyecto()
        if archivo not in tokens and not any(archivo.startswith(d) for d in directorios)
    ]
    assert sin_clasificar == []
