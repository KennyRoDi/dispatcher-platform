import pytest

from scripts.flujo import (
    Feature,
    avanzar_spec,
    agregar_entrada,
    base_de_spec,
    bitacora_registra,
    clasificar,
    cuerpo_pr,
    devolver_spec,
    entrada_bitacora,
    entrada_sin_ia,
    es_conventional,
    estado_feature,
    fase_de,
    fijar_fase,
    generar_spec,
    generar_status,
    motivos_bloqueo,
    nombre_rama,
    parsear_backlog,
    ramas_por_feature,
    titulo_pr,
)

BACKLOG = """# Backlog

### US-01 · Crear caso (F-01) · P1 · H1
- **Responsable:** N · **Depende de:** —
Como analista, quiero crear un caso.

## Área: otra

### US-02 · Validar (F-02) · P1 · H1
- **Responsable:** K · **Depende de:** F-01, F-03
Como analista, quiero validar.
"""

SPEC = """# SPEC F-01: Crear caso

**Fase:** plan
**Base:** main

## Aprobaciones

| Fase | Aprobó | Fecha | Excepción |
|---|---|---|---|
"""


def features(**deps):
    return {f: Feature(f, "K", tuple(d), "") for f, d in deps.items()}


def test_sin_spec_ni_rama_esta_pendiente():
    assert estado_feature(None, None) == "pendiente"


def test_la_fase_de_la_rama_es_el_estado():
    assert estado_feature(None, SPEC.replace("plan", "tests", 1)) == "tests"


def test_la_rama_activa_manda_sobre_lo_fusionado():
    en_main = SPEC.replace("**Fase:** plan", "**Fase:** pr")
    en_rama = SPEC.replace("**Fase:** plan", "**Fase:** implementacion")
    assert estado_feature(en_main, en_rama) == "implementacion"


def test_parte_abierta_o_cierre_sin_fusionar_es_en_pr():
    assert estado_feature(None, SPEC.replace("**Fase:** plan", "**Fase:** pr")) == "en-pr"
    assert estado_feature(None, SPEC.replace("**Fase:** plan", "**Fase:** cerrada")) == "en-pr"


def test_solo_el_cierre_fusionado_en_main_es_hecha():
    cerrada = SPEC.replace("**Fase:** plan", "**Fase:** cerrada")
    assert estado_feature(cerrada, None) == "hecha"
    assert estado_feature(cerrada, cerrada) == "hecha"


def test_status_generado_solo_tiene_feature_y_estado_en_orden():
    texto = generar_status({"F-02": "tests", "F-01": "pendiente"})
    filas = [l for l in texto.splitlines() if l.startswith("| F-")]
    assert filas == ["| F-01 | pendiente |", "| F-02 | tests |"]
    assert "No editar" in texto


def test_aprobar_avanza_una_fase_y_registra_quien_y_cuando():
    texto = avanzar_spec(SPEC, "Ana", "2026-11-03")
    assert fase_de(texto) == "tests"
    assert "| plan | Ana | 2026-11-03 |  |" in texto


@pytest.mark.parametrize("actual, siguiente", [
    ("plan", "tests"),
    ("tests", "implementacion"),
    ("implementacion", "verificacion"),
    ("verificacion", "documentacion"),
    ("documentacion", "revision"),
    ("revision", "pr"),
])
def test_las_seis_fases_van_en_orden_sin_saltos(actual, siguiente):
    texto = SPEC.replace("**Fase:** plan", f"**Fase:** {actual}")
    assert fase_de(avanzar_spec(texto, "Ana", "2026-11-03")) == siguiente


def test_no_se_aprueba_lo_que_ya_paso_las_seis_fases():
    with pytest.raises(ValueError):
        avanzar_spec(SPEC.replace("**Fase:** plan", "**Fase:** pr"), "Ana", "2026-11-03")


def test_la_excepcion_queda_registrada_y_sin_romper_la_tabla():
    texto = avanzar_spec(SPEC, "Ana", "2026-11-03", excepcion="sin | logica")
    assert "| plan | Ana | 2026-11-03 | sin / logica |" in texto


def test_devolver_regresa_a_una_fase_anterior_y_registra_motivo():
    texto = devolver_spec(SPEC.replace("**Fase:** plan", "**Fase:** revision"),
                          "implementacion", "Ana", "2026-11-03", "falla en borde")
    assert fase_de(texto) == "implementacion"
    assert "| devuelta de revision | Ana | 2026-11-03 | falla en borde |" in texto


def test_no_se_devuelve_hacia_adelante():
    with pytest.raises(ValueError):
        devolver_spec(SPEC, "revision", "Ana", "2026-11-03", "x")


def test_nueva_parte_vuelve_a_tests_con_su_base():
    texto = fijar_fase(SPEC.replace("**Fase:** plan", "**Fase:** pr"), "tests", "feat/F-01-1-a")
    assert fase_de(texto) == "tests"
    assert base_de_spec(texto) == "feat/F-01-1-a"


def test_generar_spec_rellena_datos_de_la_historia():
    plantilla = "# SPEC {feature}: {titulo}\n**Base:** {base}\n{historia} {responsable}\n"
    feature = parsear_backlog(BACKLOG)["F-02"]
    texto = generar_spec(plantilla, feature, "main")
    assert texto == "# SPEC F-02: Validar\n**Base:** main\nUS-02 K\n"


def test_plan_incompleto_se_bloquea():
    assert motivos_bloqueo("plan", [], spec="Objetivo: …")
    assert not motivos_bloqueo("plan", [], spec="Objetivo: listo")


def test_fase_de_tests_exige_pruebas_y_prohibe_codigo():
    assert motivos_bloqueo("tests", ["docs/specs/F-01/SPEC.md"])
    assert motivos_bloqueo("tests", ["tests/unit/test_a.py", "src/domain/a.py"])
    assert not motivos_bloqueo("tests", ["tests/unit/test_a.py", "docs/specs/F-01/SPEC.md"])


def test_implementacion_exige_codigo():
    assert motivos_bloqueo("implementacion", ["tests/unit/test_a.py"])
    assert not motivos_bloqueo("implementacion", ["tests/unit/test_a.py", "src/domain/a.py"])


def test_documentacion_exige_entrada_en_la_bitacora():
    assert motivos_bloqueo("documentacion", ["docs/modulo-M1-memoria.md"], bitacora_registrada=False)
    assert not motivos_bloqueo("documentacion", [], bitacora_registrada=True)


def test_backlog_da_responsable_dependencias_e_historia():
    resultado = parsear_backlog(BACKLOG)
    assert resultado["F-01"].deps == ()
    assert resultado["F-02"].deps == ("F-01", "F-03")
    assert resultado["F-02"].responsable == "K"
    assert resultado["F-02"].titulo == "Validar"
    assert resultado["F-02"].historia_id == "US-02"
    assert "quiero validar" in resultado["F-02"].historia
    assert "quiero crear" not in resultado["F-02"].historia
    assert "Área" not in resultado["F-01"].historia


def test_ordena_partes_numericamente_e_ignora_otras_ramas():
    ramas = ["feat/F-20-10-z", "feat/F-20-2-b", "main", "chore/x"]
    assert ramas_por_feature(ramas) == {"F-20": ["feat/F-20-2-b", "feat/F-20-10-z"]}


def test_sin_dependencias_es_empezable_sobre_main():
    r = clasificar(features(**{"F-01": []}), {"F-01": "pendiente"}, {})
    assert (r["F-01"].tipo, r["F-01"].base) == ("empezable", "main")


def test_dependencia_hecha_libera_la_feature():
    r = clasificar(features(**{"F-01": [], "F-02": ["F-01"]}),
                   {"F-01": "hecha", "F-02": "pendiente"}, {})
    assert r["F-02"].tipo == "empezable"


@pytest.mark.parametrize("estado", ["tests", "implementacion", "verificacion", "documentacion", "revision", "en-pr"])
def test_dependencia_con_plan_aprobado_se_apila_sobre_su_ultima_parte(estado):
    r = clasificar(features(**{"F-01": [], "F-02": ["F-01"]}),
                   {"F-01": estado, "F-02": "pendiente"},
                   {"F-01": ["feat/F-01-1-a", "feat/F-01-2-b"]})
    assert (r["F-02"].tipo, r["F-02"].base) == ("apilable", "feat/F-01-2-b")


def test_dependencia_en_plan_bloquea_porque_su_diseno_puede_cambiar():
    r = clasificar(features(**{"F-01": [], "F-02": ["F-01"]}),
                   {"F-01": "plan", "F-02": "pendiente"}, {"F-01": ["feat/F-01-1-a"]})
    assert r["F-02"].tipo == "bloqueada"


def test_dos_dependencias_sin_terminar_bloquean_porque_una_pila_tiene_una_base():
    r = clasificar(features(**{"F-01": [], "F-03": [], "F-02": ["F-01", "F-03"]}),
                   {"F-01": "tests", "F-03": "tests", "F-02": "pendiente"},
                   {"F-01": ["feat/F-01-1-a"], "F-03": ["feat/F-03-1-a"]})
    assert r["F-02"].tipo == "bloqueada"
    assert "F-01" in r["F-02"].motivo and "F-03" in r["F-02"].motivo


def test_dependencia_pendiente_bloquea():
    r = clasificar(features(**{"F-01": [], "F-02": ["F-01"]}),
                   {"F-01": "pendiente", "F-02": "pendiente"}, {})
    assert r["F-02"].tipo == "bloqueada"


def test_feature_activa_u_hecha_no_se_ofrece():
    r = clasificar(features(**{"F-01": [], "F-02": []}), {"F-01": "tests", "F-02": "hecha"}, {})
    assert r["F-01"].tipo == "activa"
    assert r["F-02"].tipo == "hecha"


def test_nombre_de_rama_usa_la_siguiente_parte_y_normaliza():
    ramas = {"F-20": ["feat/F-20-1-a", "feat/F-20-2-b"]}
    assert nombre_rama("F-20", "Política de Aging", ramas) == "feat/F-20-3-politica-de-aging"
    assert nombre_rama("F-21", "fifo", ramas) == "feat/F-21-1-fifo"


@pytest.mark.parametrize("mensaje", [
    "feat(F-20): agregar politica de aging",
    "fix(F-06)!: cerrar ventana de perdida",
    "docs: actualizar readme",
    "chore(status): regenerar",
])
def test_acepta_conventional_commits(mensaje):
    assert es_conventional(mensaje)


@pytest.mark.parametrize("mensaje", [
    "agregar politica",
    "Feat(F-20): mayuscula",
    "feat(F-20) falta dos puntos",
    "feat(F-20): ",
    "wip: algo",
])
def test_rechaza_lo_que_no_es_conventional(mensaje):
    assert not es_conventional(mensaje)


def test_titulo_de_pr_es_conventional_con_la_feature_como_ambito():
    assert titulo_pr("feat", "F-20", "agregar aging") == "feat(F-20): agregar aging"


def test_titulo_de_pr_rechaza_tipo_invalido():
    with pytest.raises(ValueError):
        titulo_pr("wip", "F-20", "algo")


def test_cuerpo_de_pr_rellena_la_plantilla():
    plantilla = "F: {feature}\nBase: {base}\n{commits}\n"
    assert cuerpo_pr(plantilla, feature="F-01", base="main", commits="- a") == "F: F-01\nBase: main\n- a\n"


CAMPOS_BITACORA = dict(
    herramienta="Claude Code", proposito="implementar", consulta="pedir F-01",
    resultado="codigo", validado="aceptado", como="pytest",
)


def test_entrada_tiene_los_campos_del_anexo_3():
    entrada = entrada_bitacora("2026-11-03", "Ana", "F-01", "feat/F-01-1-a", **CAMPOS_BITACORA)
    assert entrada.startswith("## 2026-11-03 · Ana · F-01 (`feat/F-01-1-a`)\n")
    for campo in ("Herramienta", "Componente", "Propósito", "Consulta resumida", "Resultado obtenido",
                  "Validado / corregido / descartado", "Cómo se validó"):
        assert f"| {campo} |" in entrada
    assert "Error de la IA" not in entrada


def test_entrada_registra_el_error_de_la_ia_y_protege_la_tabla():
    entrada = entrada_bitacora("2026-11-03", "Ana", "F-01", "r", error_ia="a | b\nc", **CAMPOS_BITACORA)
    assert "| Error de la IA | a / b c |" in entrada


def test_entrada_sin_ia_lo_declara_explicitamente():
    entrada = entrada_sin_ia("2026-11-03", "Ana", "F-01", "feat/F-01-1-a")
    assert "No se usó IA" in entrada
    assert bitacora_registra(entrada, "feat/F-01-1-a")


def test_agregar_entrada_va_al_final_y_conserva_lo_anterior():
    assert agregar_entrada("# Bitacora\n\n## vieja\n", "## nueva\n") == "# Bitacora\n\n## vieja\n\n## nueva\n"


def test_bitacora_registra_solo_la_rama_exacta():
    texto = entrada_bitacora("2026-11-03", "Ana", "F-01", "feat/F-01-10-a", **CAMPOS_BITACORA)
    assert bitacora_registra(texto, "feat/F-01-10-a")
    assert not bitacora_registra(texto, "feat/F-01-1-a")
