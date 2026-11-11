from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from src.application.chunked_upload import ChunkedUpload
from src.domain.chunks import ChunkRejected, IntegrityMismatch, MissingChunks, UploadNotFound

router = APIRouter(prefix="/uploads", tags=["Archivos"])
_subidas: ChunkedUpload | None = None


class InicioSubida(BaseModel):
    sha256: str
    size: int
    chunk_size: int


def configurar(subidas: ChunkedUpload | None) -> None:
    global _subidas
    _subidas = subidas


def obtener_subidas() -> ChunkedUpload:
    if _subidas is None:
        raise HTTPException(503, "almacén de objetos no configurado")
    return _subidas


def _no_existe(upload_id: str) -> HTTPException:
    return HTTPException(404, f"la subida {upload_id} no existe")


@router.post("", status_code=201)
def iniciar(cuerpo: InicioSubida, subidas: ChunkedUpload = Depends(obtener_subidas)) -> dict:
    try:
        upload_id, cantidad = subidas.start(cuerpo.sha256, cuerpo.size, cuerpo.chunk_size)
    except ValueError as error:
        raise HTTPException(422, str(error)) from None
    return {"upload_id": upload_id, "chunk_count": cantidad}


@router.put("/{upload_id}/chunks/{index}", status_code=204)
async def recibir(upload_id: str, index: int, request: Request,
                  x_chunk_sha256: str = Header(...), subidas: ChunkedUpload = Depends(obtener_subidas)) -> Response:
    datos = await request.body()
    try:
        subidas.receive(upload_id, index, datos, x_chunk_sha256)
    except UploadNotFound:
        raise _no_existe(upload_id) from None
    except ChunkRejected as error:
        raise HTTPException(422, str(error)) from None
    return Response(status_code=204)


@router.get("/{upload_id}")
def estado(upload_id: str, subidas: ChunkedUpload = Depends(obtener_subidas)) -> dict:
    try:
        recibidos, faltantes = subidas.status(upload_id)
    except UploadNotFound:
        raise _no_existe(upload_id) from None
    return {"received": recibidos, "missing": faltantes}


@router.post("/{upload_id}/complete", status_code=201)
def completar(upload_id: str, subidas: ChunkedUpload = Depends(obtener_subidas)):
    try:
        sha256, size = subidas.complete(upload_id)
    except UploadNotFound:
        raise _no_existe(upload_id) from None
    except MissingChunks as error:
        return JSONResponse({"missing": error.missing}, status_code=409)
    except IntegrityMismatch as error:
        raise HTTPException(422, str(error)) from None
    return {"sha256": sha256, "size": size}
