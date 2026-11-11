"""Aceptacion de F-27 (criterio 5 y rechazo sin CA). La ejecuta la persona con sudo.

    F27_CAPTURA=1 COORDINATOR_URL=https://<ip>:8443 TLS_CA_FILE=<ca.pem> pytest tests/acceptance/test_tls_entre_nodos.py -q

Opcionales: F27_INTERFAZ (por defecto "any"), F27_LEVANTAR_NODO=1 (ejecuta `docker compose up -d --wait` y lo baja al terminar).
Terceros: tcpdump y tshark (https://www.wireshark.org/docs/man-pages/tshark.html), `docs/IMPLEMENTACION.md` §5.
"""
import os
import shutil
import socket
import ssl
import subprocess
import sys
import time
import wave
from pathlib import Path
from urllib.parse import urlparse

import pytest

pytestmark = pytest.mark.acceptance

PUERTOS_TLS = (8443, 6380, 9000)
FILTRO_CAPTURA = " or ".join(f"port {puerto}" for puerto in PUERTOS_TLS)
DECODIFICAR_COMO_TLS = [arg for puerto in PUERTOS_TLS for arg in ("-d", f"tcp.port=={puerto},tls")]
ESPERA_ARRANQUE_TCPDUMP = 2
RAIZ = Path(__file__).resolve().parents[2]


def _motivo_para_omitir() -> str | None:
    if os.environ.get("F27_CAPTURA") != "1":
        return "define F27_CAPTURA=1 para ejecutar la captura real"
    for variable in ("COORDINATOR_URL", "TLS_CA_FILE"):
        if not os.environ.get(variable):
            return f"define {variable}"
    faltan = [herramienta for herramienta in ("tcpdump", "tshark", "strings", "sudo") if not shutil.which(herramienta)]
    if faltan:
        return f"faltan herramientas: {', '.join(faltan)}"
    if subprocess.run(["sudo", "-n", "true"], capture_output=True).returncode != 0:
        return "sudo exige contrasena; ejecuta `sudo -v` antes o configura sudo sin contrasena"
    return None


@pytest.fixture(scope="module", autouse=True)
def _requisitos():
    motivo = _motivo_para_omitir()
    if motivo:
        pytest.skip(motivo)


@pytest.fixture(scope="module")
def nodo_a(_requisitos):
    levantar = os.environ.get("F27_LEVANTAR_NODO") == "1"
    if levantar:
        subprocess.run(["docker", "compose", "up", "-d", "--wait"], cwd=RAIZ, check=True)
    yield
    if levantar:
        subprocess.run(["docker", "compose", "down"], cwd=RAIZ, check=True)


def _caso_con_marcador(directorio: Path, marcador: str) -> Path:
    directorio.mkdir()
    audio = directorio / "marcador.wav"
    with wave.open(str(audio), "wb") as escritor:
        escritor.setnchannels(1)
        escritor.setsampwidth(2)
        escritor.setframerate(8000)
        escritor.writeframes(b"\x00\x00" * 8000)
    with audio.open("ab") as destino:
        destino.write(marcador.encode())
    return directorio


def _contar_marcador(pcap: Path, marcador: str) -> int:
    cadenas = subprocess.run(["strings", str(pcap)], capture_output=True, text=True, check=True).stdout
    return sum(marcador in linea for linea in cadenas.splitlines())


def _handshakes_cliente(pcap: Path) -> list[str]:
    salida = subprocess.run(
        ["tshark", "-r", str(pcap), *DECODIFICAR_COMO_TLS, "-Y", "tls.handshake.type==1"],
        capture_output=True, text=True, check=True,
    ).stdout
    return [linea for linea in salida.splitlines() if linea.strip()]


def test_captura_con_handshake_tls_y_sin_marcador(nodo_a, tmp_path):
    marcador = f"MARCADOR-F27-{os.getpid()}-{time.time_ns()}"
    caso = _caso_con_marcador(tmp_path / "caso", marcador)
    pcap = tmp_path / "m4.pcap"
    interfaz = os.environ.get("F27_INTERFAZ", "any")

    captura = subprocess.Popen(["sudo", "-n", "tcpdump", "-i", interfaz, "-w", str(pcap), FILTRO_CAPTURA],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        time.sleep(ESPERA_ARRANQUE_TCPDUMP)
        subprocess.run([sys.executable, "-m", "scripts.submit_case", "--dir", str(caso)], cwd=RAIZ, check=True)
    finally:
        captura.terminate()
        captura.wait(timeout=30)
    subprocess.run(["sudo", "-n", "chown", str(os.getuid()), str(pcap)], check=True)

    assert _handshakes_cliente(pcap), "la captura no contiene ningun ClientHello TLS"
    assert _contar_marcador(pcap, marcador) == 0, "el marcador sintetico aparece en claro en la captura"


def test_cliente_sin_la_ca_es_rechazado(nodo_a):
    destino = urlparse(os.environ["COORDINATOR_URL"])
    contexto = ssl.create_default_context()
    with pytest.raises(ssl.SSLCertVerificationError):
        with socket.create_connection((destino.hostname, destino.port or 443), timeout=10) as conexion:
            contexto.wrap_socket(conexion, server_hostname=destino.hostname)
