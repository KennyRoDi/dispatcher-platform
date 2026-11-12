"""QA F-15: la vista Monitor renderiza «Por nodo» sin excepciones con datos raros de /workers."""
import re

import pytest
import responses
from streamlit.testing.v1 import AppTest

BASE = "http://localhost:8000"


def _app():
    import sys
    from pathlib import Path
    import streamlit as st
    sys.path.insert(0, str(Path.cwd() / "dashboard"))
    st.session_state.setdefault("base_url", "http://localhost:8000")
    st.session_state.setdefault("refresh", 3600)
    from views import monitor
    monitor.render()


def _w(i, host, alive=True, **extra):
    base = {"worker_id": f"w{i}", "host": host, "alive": alive, "cpu_percent": 10.0 * i,
            "mem_percent": 20.0, "active_subtasks": 1, "gpu": "none"}
    base.update(extra)
    return base


CASOS = {
    "con_y_sin_cgroup": [_w(1, "a", cgroup_memory_current=1 << 30, cgroup_memory_max=2 << 30), _w(2, "a"),
                         _w(3, "b")],
    "hosts_none": [_w(1, None), {"worker_id": "x", "alive": True}],
    "muchos_nodos": [_w(i, f"n{i:03d}", cgroup_memory_current="1024", cgroup_memory_max="max") for i in range(150)],
    "todos_muertos": [_w(1, "a", alive=False), _w(2, "b", alive=False)],
    "gpu_presente": [_w(1, "a", gpu="RTX 3060", gpu_percent=55.5), _w(2, "a", gpu="RTX 3060", gpu_percent="")],
    "vacio": [],
}


@pytest.mark.parametrize("nombre", list(CASOS))
@responses.activate
def test_monitor_por_nodo_no_lanza(nombre):
    responses.add(responses.GET, re.compile(rf"{BASE}/workers.*"), json=CASOS[nombre])
    responses.add(responses.GET, re.compile(rf"{BASE}/stats.*"), json={})
    responses.add(responses.GET, re.compile(rf"{BASE}/hardware.*"), json=[])
    responses.add(responses.GET, re.compile(rf"{BASE}/.*"), json={})
    at = AppTest.from_function(_app, default_timeout=30).run()
    assert not at.exception, [e.value for e in at.exception]
    if CASOS[nombre]:
        assert len(at.dataframe) >= 2  # «Por nodo» + «Workers»
