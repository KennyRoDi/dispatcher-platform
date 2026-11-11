import pytest

from scripts.comparar_transcripcion import generar_markdown
from src.adapters.whisper_transcriber import ConfigWhisper

CONFIG = ConfigWhisper("base", "ebe41f70d5b6dfa9166e2c581c45c9c0cfc57b66", "es", "int8", 5, 0)


@pytest.mark.parametrize("faltante", ["faster-whisper", "ctranslate2"])
def test_versiones_incompletas_fallan_con_value_error_que_nombra_la_biblioteca(faltante):
    versiones = {"faster-whisper": "1.2.1", "ctranslate2": "4.7.1"}
    del versiones[faltante]

    # main solo captura ValueError y OSError: un KeyError saldría como traza en vez de «error: ...».
    with pytest.raises(ValueError, match=faltante):
        generar_markdown("cmd", CONFIG, versiones, [], [])
