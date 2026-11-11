def crear_caso(client, cantidad=1):
    cuerpo = {"subtasks": [{"task_type": "auto", "file_path": f"videos/sintetico-{n}.mp4"} for n in range(cantidad)]}
    datos = client.post("/cases", json=cuerpo).json()
    return datos["case_id"], datos["subtask_ids"]


def reportar(client, case_id, subtask_id, status="completed", **extra):
    cuerpo = {
        "subtask_id": subtask_id,
        "case_id": case_id,
        "status": status,
        "worker_id": "w1",
        "host": "h1",
        "processing_s": 2.0,
        "outputs": [f"out/{subtask_id}.mp4"] if status == "completed" else None,
    }
    cuerpo.update(extra)
    return client.post("/subtasks/report", json=cuerpo)
