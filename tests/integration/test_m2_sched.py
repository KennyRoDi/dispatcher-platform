"""Prueba de integración: simulador de carga de F-21 produce CSV por política."""
import csv
import os
import subprocess
import sys

import pytest

SCRIPT = os.path.join("scripts", "measure", "m2_sched.py")


@pytest.mark.integration
class TestMedicionComparativa:
    def test_medicion_corta_produce_csv_por_politica(self, tmp_path):
        """Corrida corta del simulador con ambas políticas produce un CSV con columnas esperadas."""
        for politica in ("fifo", "aging"):
            salida = tmp_path / f"m2_{politica}.csv"
            resultado = subprocess.run(
                [
                    sys.executable,
                    SCRIPT,
                    "--high-rate",
                    "5",
                    "--low",
                    "1",
                    "--seed",
                    "1",
                    "--out",
                    str(salida),
                ],
                env={**os.environ, "SCHED_POLICY": politica},
                capture_output=True,
                text=True,
                stdin=subprocess.DEVNULL,
            )

            assert resultado.returncode == 0, resultado.stderr
            assert salida.exists(), f"no se generó {salida}"

            with open(salida, newline="", encoding="utf-8") as f:
                filas = list(csv.DictReader(f))

            assert filas, f"CSV de {politica} está vacío"
            columnas_esperadas = {"politica", "nivel", "espera_ms", "turnaround_ms", "throughput_cps"}
            assert columnas_esperadas.issubset(filas[0].keys())
            assert all(fila["politica"] == politica for fila in filas)
