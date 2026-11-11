import pytest


@pytest.fixture
def symlink_capable(tmp_path):
    target = tmp_path / "symlink-probe-target"
    target.mkdir()
    link = tmp_path / "symlink-probe"
    try:
        link.symlink_to(target, target_is_directory=True)
    except OSError as error:
        if getattr(error, "winerror", None) == 1314:
            pytest.skip("Windows requiere privilegio para crear enlaces simbólicos")
        raise
    else:
        link.unlink()
    finally:
        target.rmdir()
