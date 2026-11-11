import pytest

from src.domain.provenance import ProvenancePolicy, SourceRecord, validate_provenance


def _record(origin="sintetico", license="MIT", path="imagenes/objetos_001.png"):
    return SourceRecord(path=path, origin=origin, license=license)


def test_fuente_sin_licencia_falla_validacion():
    for missing in (None, "", "  "):
        defects = validate_provenance([_record(license=missing, path="a.png")])

        assert len(defects) == 1
        assert defects[0].startswith("a.png: ")


@pytest.mark.parametrize("filler", ["desconocida", "N/A", "n/a", "-", " Desconocida ", "NINGUNA", "Sin Licencia"])
def test_licencia_de_relleno_falla_validacion(filler):
    defects = validate_provenance([_record(origin="propio", license=filler, path="b.png")])

    assert len(defects) == 1
    assert defects[0].startswith("b.png: ")


@pytest.mark.parametrize("origin", ["real", "tercero", None, "", "  "])
def test_origen_no_admitido_falla_validacion(origin):
    defects = validate_provenance([_record(origin=origin, path="c.png")])

    assert len(defects) == 1
    assert defects[0].startswith("c.png: ")


def test_fuente_publica_exige_licencia_admitida():
    rejected = validate_provenance([_record(origin="publico", license="CC-BY-NC-4.0", path="d.png")])
    accepted = validate_provenance([_record(origin="publico", license="CC-BY-4.0", path="d.png")])

    assert len(rejected) == 1
    assert rejected[0].startswith("d.png: ")
    assert accepted == []


def test_licencia_publica_se_compara_sin_distinguir_mayusculas_ni_espacios():
    assert validate_provenance([_record(origin="publico", license="  cc-by-4.0 ")]) == []


def test_fuentes_sinteticas_y_propias_con_licencia_pasan():
    records = [
        _record(origin="sintetico", license="MIT"),
        _record(origin="propio", license="CC-BY-4.0", path="propias/foto.png"),
    ]

    assert validate_provenance(records) == []


def test_lista_vacia_no_tiene_defectos():
    assert validate_provenance([]) == []


def test_validador_reporta_todos_los_defectos():
    records = [
        _record(license=None, path="a.png"),
        _record(origin="real", path="b.png"),
        _record(origin="publico", license="CC-BY-NC-4.0", path="c.png"),
        _record(path="ok.png"),
    ]

    defects = validate_provenance(records)

    assert [d.split(":")[0] for d in defects] == ["a.png", "b.png", "c.png"]


def test_fuente_con_origen_y_licencia_malos_reporta_los_dos_defectos():
    defects = validate_provenance([_record(origin="real", license="", path="e.png")])

    assert len(defects) == 2
    assert all(d.startswith("e.png: ") for d in defects)


def test_politica_personalizada_cambia_lo_admitido():
    policy = ProvenancePolicy(
        admitted_origins=("publico",),
        public_licenses=("CC0-1.0",),
        rejected_licenses=("desconocida",),
    )

    assert validate_provenance([_record(origin="sintetico")], policy)
    assert validate_provenance([_record(origin="publico", license="MIT")], policy)
    assert validate_provenance([_record(origin="publico", license="CC0-1.0")], policy) == []
