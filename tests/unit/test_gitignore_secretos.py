from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]


def lineas_gitignore():
    return {linea.strip() for linea in (RAIZ / ".gitignore").read_text().splitlines()}


def test_env_esta_ignorado():
    assert ".env" in lineas_gitignore()


def test_el_archivo_de_secreto_jwt_esta_ignorado():
    patrones = lineas_gitignore()
    assert {"*.key", "jwt.secret", "*.secret"} & patrones
