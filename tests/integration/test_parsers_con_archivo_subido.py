"""Prueba de integracion: parser lee un archivo subido por el flujo real de chunks (F-02/F-22)."""
import hashlib

import pytest

from src.application.chunked_upload import ChunkedUpload
from src.adapters.chat_export_generator import generate_chat, render_whatsapp
from tests.dobles import FakeChunkStaging, FakeObjectStore


@pytest.mark.integration
class TestParsersConArchivoSubido:
    def test_parsers_leen_archivo_subido_por_chunks(self, tmp_path):
        from src.adapters.whatsapp_parser import WhatsAppParser

        contenido = render_whatsapp(generate_chat(seed=3, count=6)).encode("utf-8")
        sha256 = hashlib.sha256(contenido).hexdigest()

        almacen = FakeObjectStore()
        subidas = ChunkedUpload(FakeChunkStaging(), almacen, max_chunk_size=1 << 20)
        upload_id, _cantidad = subidas.start_if_missing(sha256, len(contenido), len(contenido))
        assert upload_id is not None
        subidas.receive(upload_id, 0, contenido, hashlib.sha256(contenido).hexdigest())
        sha_final, _size = subidas.complete(upload_id)
        assert sha_final == sha256

        # Recuperar del almacen (como lo haria un worker real) y parsear.
        destino = tmp_path / "recuperado.txt"
        destino.write_bytes(almacen.open(sha256).read())

        mensajes = WhatsAppParser().parse(destino)

        assert len(mensajes) == 6


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
