"""Prueba de aceptacion: todas las conversaciones del dataset se parsean sin errores (F-02).

Genera varias conversaciones con el generador sintetico de F-03 (WhatsApp y
Telegram) y confirma que ninguna lanza FormatoDeChatInvalido. El conteo de
mensajes validos es la evidencia pedida por US-02.
"""
import pytest

from src.adapters.chat_export_generator import generate_chat, render_telegram, render_whatsapp


@pytest.mark.acceptance
class TestDatasetSeAnalizaSinErrores:
    def test_dataset_se_analiza_sin_errores(self, tmp_path):
        from src.adapters.telegram_parser import TelegramParser
        from src.adapters.whatsapp_parser import WhatsAppParser

        whatsapp_parser = WhatsAppParser()
        telegram_parser = TelegramParser()

        total_mensajes_validos = 0
        total_conversaciones = 0
        rechazadas = []

        for seed in range(1, 11):
            conteo = 3 + (seed % 5)
            mensajes = generate_chat(seed=seed, count=conteo)

            archivo_wa = tmp_path / f"conversacion-{seed}-chat.txt"
            archivo_wa.write_text(render_whatsapp(mensajes), encoding="utf-8")
            archivo_tg = tmp_path / f"conversacion-{seed}-chat.json"
            archivo_tg.write_text(render_telegram(mensajes), encoding="utf-8")

            for archivo, parser in ((archivo_wa, whatsapp_parser), (archivo_tg, telegram_parser)):
                total_conversaciones += 1
                try:
                    parseados = parser.parse(archivo)
                except Exception as error:  # noqa: BLE001 — evidencia explicita de cualquier rechazo
                    rechazadas.append((archivo.name, str(error)))
                    continue
                assert len(parseados) == conteo
                total_mensajes_validos += len(parseados)

        assert not rechazadas, f"conversaciones rechazadas inesperadamente: {rechazadas}"
        assert total_conversaciones == 20
        assert total_mensajes_validos > 0
        print(f"Evidencia F-02: {total_mensajes_validos} mensajes válidos en "
              f"{total_conversaciones} conversaciones, 0 rechazadas")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
