"""Управление задачами: статус, отмена, скачивание результатов."""

import os
import zipfile

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from api import jobs as job_store

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.get("/{job_id}")
def job_status(job_id: str):
    """Состояние задачи: статус, прогресс, логи, файлы результата."""
    job = job_store.get_job(job_id)
    if not job:
        raise HTTPException(404, "Задача не найдена")
    job_store.collect_outputs(job)
    return job_store.public_state(job)


@router.post("/{job_id}/cancel")
def job_cancel(job_id: str):
    if not job_store.cancel_job(job_id):
        raise HTTPException(404, "Задача не найдена")
    return {"ok": True}


@router.get("/{job_id}/files/{rel_path:path}")
def job_file(job_id: str, rel_path: str):
    """Скачивание одного файла результата."""
    if not job_store.get_job(job_id):
        raise HTTPException(404, "Задача не найдена")
    full = job_store.resolve_output_file(job_id, rel_path)
    if not full:
        raise HTTPException(404, "Файл не найден")
    return FileResponse(full, filename=os.path.basename(full))


@router.get("/{job_id}/archive")
def job_archive(job_id: str):
    """Все результаты задачи одним ZIP-архивом."""
    job = job_store.get_job(job_id)
    if not job:
        raise HTTPException(404, "Задача не найдена")
    job_store.collect_outputs(job)
    if not job["files"]:
        raise HTTPException(404, "У задачи нет файлов результата")
    zip_path = os.path.join(job_store.outputs_dir(job_id),
                            f"results_{job_id}.zip")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in job["files"]:
            if f["name"].endswith(".zip"):
                continue
            full = job_store.resolve_output_file(job_id, f["name"])
            if full:
                zf.write(full, arcname=f["name"])
    return FileResponse(zip_path, filename=f"results_{job_id}.zip")
