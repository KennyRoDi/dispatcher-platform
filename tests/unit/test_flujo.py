"""Lógica pura del ciclo de trabajo común (scripts/flujo.py)."""
import pytest

from scripts.flujo import (
    Feature,
    aprobar_spec,
    cambiar_status,
    clasificar,
    cuerpo_pr,
    es_conventional,
    features_cerradas,
    nombre_rama,
    parsear_backlog,
    parsear_status,
    ramas_por_feature,
    spec_aprobada,
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


def features(**deps):
    return {f: Feature(f, "K", tuple(d), "") for f, d in deps.items()}


def test_parsea_status_e_ignora_encabezados():
    texto = "# Estado\n\n| Feature | Estado |\n|---|---|\n| F-01 | pendiente |\n| F-02 | en-pr |\n"
    assert parsear_status(texto) == {"F-01": "pendiente", "F-02": "en-pr"}


def test_cambia_solo_la_fila_indicada():
    texto = "| F-01 | pendiente |\n| F-02 | pendiente |\n"
    assert cambiar_status(texto, "F-02", "spec") == "| F-01 | pendiente |\n| F-02 | spec |\n"


def test_rechaza_estado_desconocido_o_feature_inexistente():
    with pytest.raises(ValueError):
        cambiar_status("| F-01 | pendiente |\n", "F-01", "casi-lista")
    with pytest.raises(ValueError):
        cambiar_status("| F-01 | pendiente |\n", "F-99", "spec")


def test_backlog_da_responsable_dependencias_e_historia():
    resultado = parsear_backlog(BACKLOG)
    assert resultado["F-01"].deps == ()
    assert resultado["F-02"].deps == ("F-01", "F-03")
    assert resultado["F-02"].responsable == "K"
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


def test_dependencia_activa_con_rama_se_apila_sobre_su_ultima_parte():
    r = clasificar(features(**{"F-01": [], "F-02": ["F-01"]}),
                   {"F-01": "en-pr", "F-02": "pendiente"},
                   {"F-01": ["feat/F-01-1-a", "feat/F-01-2-b"]})
    assert (r["F-02"].tipo, r["F-02"].base) == ("apilable", "feat/F-01-2-b")


def test_dependencia_en_spec_bloquea_porque_su_diseno_puede_cambiar():
    r = clasificar(features(**{"F-01": [], "F-02": ["F-01"]}),
                   {"F-01": "spec", "F-02": "pendiente"}, {"F-01": ["feat/F-01-1-a"]})
    assert r["F-02"].tipo == "bloqueada"


def test_dos_dependencias_sin_terminar_bloquean_porque_una_pila_tiene_una_base():
    r = clasificar(features(**{"F-01": [], "F-03": [], "F-02": ["F-01", "F-03"]}),
                   {"F-01": "en-curso", "F-03": "en-curso", "F-02": "pendiente"},
                   {"F-01": ["feat/F-01-1-a"], "F-03": ["feat/F-03-1-a"]})
    assert r["F-02"].tipo == "bloqueada"
    assert "F-01" in r["F-02"].motivo and "F-03" in r["F-02"].motivo


def test_dependencia_pendiente_bloquea():
    r = clasificar(features(**{"F-01": [], "F-02": ["F-01"]}),
                   {"F-01": "pendiente", "F-02": "pendiente"}, {})
    assert r["F-02"].tipo == "bloqueada"


def test_feature_activa_u_hecha_no_se_ofrece():
    r = clasificar(features(**{"F-01": [], "F-02": []}),
                   {"F-01": "en-curso", "F-02": "hecha"}, {})
    assert r["F-01"].tipo == "activa"
    assert r["F-02"].tipo == "hecha"


def test_nombre_de_rama_usa_la_siguiente_parte_y_normaliza():
    ramas = {"F-20": ["feat/F-20-1-a", "feat/F-20-2-b"]}
    assert nombre_rama("F-20", "Política de Aging", ramas) == "feat/F-20-3-politica-de-aging"
    assert nombre_rama("F-21", "fifo", ramas) == "feat/F-21-1-fifo"


def test_spec_en_borrador_no_esta_aprobada():
    assert not spec_aprobada("# SPEC\n**Estado:** borrador\n")
    assert not spec_aprobada("# SPEC sin campo\n")


def test_aprobar_registra_quien_y_cuando():
    texto = aprobar_spec("**Estado:** borrador\n", "Ana", "2026-11-03")
    assert texto == "**Estado:** aprobado por Ana el 2026-11-03\n"
    assert spec_aprobada(texto)


def test_aprobar_falla_si_no_hay_borrador():
    with pytest.raises(ValueError):
        aprobar_spec("sin campo\n", "Ana", "2026-11-03")


def test_cuerpo_de_pr_rellena_la_plantilla():
    plantilla = "F: {feature}\nBase: {base}\n{commits}\n"
    assert cuerpo_pr(plantilla, feature="F-01", base="main", commits="- a") == "F: F-01\nBase: main\n- a\n"


@pytest.mark.parametrize("mensaje", [
    "feat(F-20): agregar politica de aging",
    "fix(F-06)!: cerrar ventana de perdida",
    "docs: actualizar readme",
    "chore(status): F-20 en-curso",
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


def test_detecta_features_cerradas_por_el_footer_de_la_pr():
    cuerpos = ["texto\nCierra-Feature: F-20\n", "parte intermedia", "Cierra-Feature: F-03"]
    assert features_cerradas(cuerpos) == {"F-20", "F-03"}
