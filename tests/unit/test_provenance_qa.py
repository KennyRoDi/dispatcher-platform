import pytest

from src.domain.provenance import SourceRecord, validate_provenance


@pytest.mark.xfail(
    strict=True,
    raises=AttributeError,
    reason="QA F-04 parte 2: licencia no str (5, b'MIT', ['MIT']) lanza AttributeError opaco en vez de un defecto con la ruta",
)
@pytest.mark.parametrize("license_value", [5, b"MIT", ["MIT"]])
def test_licencia_que_no_es_texto_da_un_defecto_con_la_ruta(license_value):
    defects = validate_provenance([SourceRecord("a.png", "sintetico", license_value)])

    assert len(defects) == 1
    assert defects[0].startswith("a.png: ")


@pytest.mark.xfail(
    strict=True,
    raises=AttributeError,
    reason="QA F-04 parte 2: origen no str (5, b'x') lanza AttributeError opaco en vez de un defecto con la ruta",
)
@pytest.mark.parametrize("origin_value", [5, b"propio"])
def test_origen_que_no_es_texto_da_un_defecto_con_la_ruta(origin_value):
    defects = validate_provenance([SourceRecord("a.png", origin_value, "MIT")])

    assert len(defects) == 1
    assert defects[0].startswith("a.png: ")


@pytest.mark.xfail(
    strict=True,
    reason="QA F-04 parte 2: 'sin  licencia' (dos espacios) y 'sin\\xa0licencia' (NBSP interno) pasan como licencia valida; solo se recortan los espacios exteriores",
)
@pytest.mark.parametrize("filler", ["sin  licencia", "sin licencia", "sin\tlicencia"])
def test_licencia_de_relleno_con_espacios_interiores_raros_falla(filler):
    defects = validate_provenance([SourceRecord("b.png", "propio", filler)])

    assert len(defects) == 1


@pytest.mark.xfail(
    strict=True,
    reason="QA F-04 parte 2: una licencia de solo caracteres invisibles (U+200B, U+FEFF) pasa; str.strip no los quita",
)
@pytest.mark.parametrize("invisible", ["​", "﻿", "​​"])
def test_licencia_de_solo_caracteres_invisibles_cuenta_como_faltante(invisible):
    defects = validate_provenance([SourceRecord("c.png", "sintetico", invisible)])

    assert defects == ["c.png: falta la licencia"]
