import pytest

from src.infrastructure.model_memory import (
    ProcessMemory,
    read_cgroup_memory,
    read_process_memory,
    parse_smaps_rollup,
)


def test_parse_smaps_rollup_convierte_rss_y_pss_de_kib_a_bytes():
    texto = "Rss: 1200 kB\nPss: 800 kB\n"

    assert parse_smaps_rollup(texto) == ProcessMemory(rss_bytes=1_228_800, pss_bytes=819_200)


@pytest.mark.parametrize("texto", ["Rss: 10 kB\n", "Rss: x kB\nPss: 2 kB\n"])
def test_parse_smaps_rollup_rechaza_lecturas_ausentes_o_invalidas(texto):
    with pytest.raises(ValueError):
        parse_smaps_rollup(texto)


def test_read_process_memory_lee_smaps_rollup_del_pid(tmp_path):
    proceso = tmp_path / "123"
    proceso.mkdir()
    (proceso / "smaps_rollup").write_text("Rss: 3 kB\nPss: 2 kB\n", encoding="utf-8")

    assert read_process_memory(123, tmp_path) == ProcessMemory(rss_bytes=3072, pss_bytes=2048)


def test_read_cgroup_memory_conserva_limite_y_swap(tmp_path):
    (tmp_path / "memory.current").write_text("4096\n", encoding="utf-8")
    (tmp_path / "memory.max").write_text("16384\n", encoding="utf-8")
    (tmp_path / "memory.swap.max").write_text("0\n", encoding="utf-8")

    memoria = read_cgroup_memory(tmp_path)

    assert memoria.memory_current == 4096
    assert memoria.memory_max == 16384
    assert memoria.memory_swap_max == 0


def test_read_cgroup_memory_rechaza_limite_ausente_o_ilimitado(tmp_path):
    (tmp_path / "memory.current").write_text("4096\n", encoding="utf-8")
    (tmp_path / "memory.max").write_text("max\n", encoding="utf-8")
    (tmp_path / "memory.swap.max").write_text("0\n", encoding="utf-8")

    with pytest.raises(ValueError):
        read_cgroup_memory(tmp_path)
