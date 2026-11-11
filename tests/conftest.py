import pytest


@pytest.fixture
def sin_autorizacion():
    import src.coordinator.main as main
    from src.coordinator.seguridad import autorizar

    main.app.dependency_overrides[autorizar] = lambda: None
    yield
    main.app.dependency_overrides.pop(autorizar, None)
