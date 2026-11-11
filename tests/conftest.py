import pytest

import src.coordinator.main as main
from src.coordinator.seguridad import autorizar


@pytest.fixture
def sin_autorizacion():
    main.app.dependency_overrides[autorizar] = lambda: None
    yield
    main.app.dependency_overrides.pop(autorizar, None)
