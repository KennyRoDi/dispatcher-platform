from pathlib import Path

from src.adapters import media_generator

LICENSE_FILE = Path(__file__).resolve().parents[2] / "LICENSE"


def test_los_medios_se_declaran_con_licencia_mit():
    assert media_generator.LICENSE_NAME == "MIT"


def test_el_origen_de_los_medios_sigue_siendo_sintetico():
    assert media_generator.ORIGIN == "sintetico"


def test_la_raiz_del_repo_tiene_el_texto_de_la_licencia_mit():
    assert LICENSE_FILE.is_file()
    text = LICENSE_FILE.read_text(encoding="utf-8")

    assert "MIT License" in text
    assert "Copyright (c)" in text
    assert "Permission is hereby granted, free of charge" in text
