import os

import pytest

# TLS es obligatorio por defecto (F-27). Las pruebas que no tratan de TLS lo apagan; las que
# sí, lo activan con monkeypatch. Se fija también al importar porque algunos módulos
# (src/coordinator/conexion.py) crean su cliente Redis al importarse, antes de cualquier fixture.
os.environ["TLS_ENABLED"] = "false"


@pytest.fixture(autouse=True)
def tls_apagado_por_defecto(monkeypatch):
    monkeypatch.setenv("TLS_ENABLED", "false")
    monkeypatch.delenv("TLS_CA_FILE", raising=False)


@pytest.fixture
def sin_autorizacion():
    import src.coordinator.main as main
    from src.coordinator.seguridad import autorizar

    main.app.dependency_overrides[autorizar] = lambda: None
    yield
    main.app.dependency_overrides.pop(autorizar, None)
