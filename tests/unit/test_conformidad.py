import pytest

from scripts.conformidad import (
    CHECKS_PR,
    revisar_alcance,
    revisar_backlog,
    revisar_bitacora,
    revisar_comandos,
    revisar_commits,
    revisar_ficha,
    revisar_piezas,
    revisar_rama,
    revisar_responsables,
    revisar_secretos,
    revisar_spec,
    revisar_status,
    revisar_tamano,
    revisar_titulo,
)
from scripts.flujo import FASES, RAIZ, Feature, generar_status

RAMA = "feat/F-01-1-crear-caso"


def spec_completo(fase="pr", base="main"):
    filas = "".join(f"| verificación IA de {f} | C | d | x |\n| {f} | Ana | d |  |\n" for f in FASES)
    return f"**Fase:** {fase}\n**Base:** {base}\n\n{filas}"


@pytest.mark.parametrize("rama", [RAMA, "chore/x", "docs/planificacion", "fix/y"])
def test_acepta_ramas_del_patron(rama):
    assert not revisar_rama(rama)


@pytest.mark.parametrize("rama", ["feat/x", "F-01", "feat/F-01-crear", "mi-rama"])
def test_rechaza_ramas_fuera_del_patron(rama):
    assert revisar_rama(rama)


def test_titulo_de_feature_debe_usar_su_ambito():
    assert not revisar_titulo("feat(F-01): crear caso", RAMA)
    assert revisar_titulo("feat(F-02): crear caso", RAMA)
    assert revisar_titulo("crear caso", "chore/x")
    assert not revisar_titulo("chore: ordenar", "chore/x")


def test_commits_fuera_de_formato_se_listan():
    assert revisar_commits(["feat(F-01): a"]) == []
    assert "wip" in revisar_commits(["feat(F-01): a", "wip"])[0]


def test_tamano_ignora_binarios_y_respeta_limite():
    assert not revisar_tamano("200\t200\ta.py\n-\t-\tb.png", RAMA)
    assert revisar_tamano("201\t200\ta.py", RAMA)
    assert not revisar_tamano("9000\t0\ta.py", "chore/importar")


def test_spec_completo_de_feature_pasa():
    assert not revisar_spec(spec_completo(), "main")
    assert not revisar_spec(spec_completo("cerrada", "feat/F-01-1-a"), "main")


def test_spec_sin_todas_las_fases_o_sin_terminar_falla():
    assert revisar_spec(spec_completo("tests"), "main")
    sin_humana = spec_completo().replace("| revision | Ana | d |  |\n", "")
    assert any("revision" in m for m in revisar_spec(sin_humana, "main"))
    sin_ia = spec_completo().replace("| verificación IA de plan | C | d | x |\n", "")
    assert any("plan" in m for m in revisar_spec(sin_ia, "main"))


def test_spec_con_base_distinta_a_la_pr_falla():
    assert revisar_spec(spec_completo(base="feat/F-01-1-a"), "feat/F-09-1-b")


def test_ramas_sin_feature_no_tocan_codigo_de_producto():
    assert revisar_alcance("chore/x", ["src/domain/a.py"])
    assert not revisar_alcance("fix/x", ["src/domain/a.py"])
    assert not revisar_alcance("chore/x", ["scripts/flujo.py"])


def test_una_feature_no_edita_la_bitacora():
    assert revisar_alcance(RAMA, ["docs/BITACORA_IA.md"])


def test_status_debe_cubrir_exactamente_el_backlog():
    features = {"F-01": Feature("F-01", "K", (), "")}
    assert not revisar_status(generar_status({"F-01": "tests"}), features)
    assert revisar_status(generar_status({"F-01": "casi"}), features)
    assert revisar_status(generar_status({"F-02": "tests"}), features)
    assert revisar_status("| F-01 | tests |\n", features)


def test_backlog_con_dependencia_inexistente_falla():
    assert not revisar_backlog({"F-01": Feature("F-01", "K", (), "")})
    assert revisar_backlog({"F-01": Feature("F-01", "K", ("F-99",), "")})


def test_bitacora_exige_campos_del_anexo_3():
    assert not revisar_bitacora("# B\n\n## d · a · c (`r`)\n\n| Uso de IA | No |\n")
    assert revisar_bitacora("# B\n\n## d · a · c (`r`)\n\n| Herramienta | x |\n")


def test_ficha_exige_las_cinco_secciones():
    secciones = ["Qué se implementó", "Concepto de Sistemas Operativos", "Método de medición", "Resultados", "Interpretación"]
    completa = "".join(f"## {i}. {s}\n" for i, s in enumerate(secciones, 1))
    assert not revisar_ficha(completa)
    assert revisar_ficha(completa.replace("## 4. Resultados\n", ""))


def test_piezas_comunes_y_entregables_de_features_hechas():
    faltan = revisar_piezas({"AGENTS.md"}, {"F-39": "hecha"})
    assert "CONTRIBUTING.md" in faltan[0] or any("CONTRIBUTING.md" in m for m in faltan)
    assert any("docs/reutilizacion.md" in m for m in faltan)
    assert not any("docs/reutilizacion.md" in m for m in revisar_piezas(set(), {"F-39": "tests"}))


def test_comando_de_claude_debe_apuntar_al_comun():
    assert not revisar_comandos({"cierre": "Lee `.agents/skills/cierre/SKILL.md`"})
    assert revisar_comandos({"cierre": "instrucciones copiadas"})


def test_detecta_llave_privada_agregada():
    assert revisar_secretos(["+-----BEGIN RSA " + "PRIVATE KEY-----"])
    assert not revisar_secretos(["+texto normal"])


def test_cada_check_de_pr_tiene_su_entrada_en_el_workflow():
    workflow = (RAIZ / ".github/workflows/pr.yml").read_text(encoding="utf-8")
    for nombre in CHECKS_PR:
        assert f"- {nombre}\n" in workflow


def test_responsable_sin_integrante_falla():
    features = {"F-01": Feature("F-01", "Z", (), ""), "F-02": Feature("F-02", "Todos", (), "")}
    motivos = revisar_responsables(features, {"K"})
    assert len(motivos) == 1 and "F-01" in motivos[0]
