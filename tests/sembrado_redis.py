"""Siembra en Redis las claves que escribe el coordinador (mismos nombres que `rutas_casos`)."""


def sembrar_caso(cliente, caso, extra_por_subtarea=None):
    clave = f"case:{caso.case_id}"
    campos = {"case_id": caso.case_id, "status": caso.status, "total_subtasks": len(caso.sources)}
    if caso.created_at:
        campos["created_at"] = caso.created_at.isoformat()
    if caso.finished_at:
        campos["finished_at"] = caso.finished_at.isoformat()
    cliente.hset(clave, mapping=campos)
    for posicion, fuente in enumerate(caso.sources):
        sid = f"{caso.case_id}-s{posicion}"
        cliente.rpush(f"{clave}:subtasks", sid)
        cliente.hset(
            f"subtask:{sid}",
            mapping={
                "file_path": fuente.file_path,
                "status": fuente.status,
                "error_type": fuente.error_type or "",
                "kind": fuente.kind,
                **({"source_sha256": fuente.sha256} if fuente.sha256 else {}),
                **((extra_por_subtarea or {}).get(posicion, {})),
            },
        )
