"""
Менеджер фоновых задач Flet-версии VUI ToolKit.

Перенесён из api/jobs.py бэкенда веб-версии: задача выполняется в отдельном
потоке, состояние хранится в памяти, файлы — на диске в workspace/jobs/<id>/.
"""

import os
import shutil
import threading
import time
import uuid

WORKSPACE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "workspace")
JOBS_DIR = os.path.join(WORKSPACE, "jobs")

JOB_TTL_HOURS = 24.0

_jobs = {}
_lock = threading.Lock()


def _job_dir(job_id: str) -> str:
    return os.path.join(JOBS_DIR, job_id)


def uploads_dir(job_id: str) -> str:
    path = os.path.join(_job_dir(job_id), "uploads")
    os.makedirs(path, exist_ok=True)
    return path


def outputs_dir(job_id: str) -> str:
    path = os.path.join(_job_dir(job_id), "outputs")
    os.makedirs(path, exist_ok=True)
    return path


def create_job(tool: str, params: dict) -> dict:
    """Регистрирует задачу и создаёт её рабочие папки."""
    job_id = uuid.uuid4().hex[:12]
    job = {
        "id": job_id,
        "tool": tool,
        "status": "queued",
        "progress": {"current": 0, "total": 0, "percent": 0},
        "logs": [],
        "files": [],
        "error": None,
        "params": params,
        "created_at": time.time(),
        "cancel_event": threading.Event(),
    }
    with _lock:
        _jobs[job_id] = job
    uploads_dir(job_id)
    outputs_dir(job_id)
    return job


def get_job(job_id: str):
    with _lock:
        return _jobs.get(job_id)


def add_log(job: dict, message: str):
    with _lock:
        job["logs"].append({"t": round(time.time(), 2), "msg": str(message)})


def make_progress(job: dict):
    """Колбэк progress(i, total) для core-функций."""
    def _progress(current: int, total: int):
        with _lock:
            percent = round(100.0 * current / total, 1) if total else 0
            job["progress"] = {"current": current, "total": total,
                               "percent": percent}
    return _progress


def collect_outputs(job: dict):
    """Сканирует папку outputs задачи (и свои папки, если заданы)
    и обновляет список файлов."""
    roots = [outputs_dir(job["id"])]
    for extra in (job.get("out_dirs") or []):
        if extra not in roots:
            roots.append(extra)
    files = []
    for out_dir in roots:
        if not os.path.isdir(out_dir):
            continue
        for root, _dirs, names in os.walk(out_dir):
            for name in sorted(names):
                full = os.path.join(root, name)
                rel = os.path.relpath(full, out_dir)
                files.append({
                    "name": rel.replace(os.sep, "/"),
                    "path": full,
                    "size": os.path.getsize(full),
                })
    with _lock:
        job["files"] = files


def run_job(job: dict, target, *args, **kwargs):
    """Запускает target(job) в отдельном потоке с обработкой статусов."""
    def _runner():
        job["status"] = "running"
        add_log(job, f"Задача запущена ({job['tool']}).")
        try:
            target(job, *args, **kwargs)
            if job["cancel_event"].is_set():
                job["status"] = "canceled"
                add_log(job, "Задача прервана пользователем.")
            else:
                job["status"] = "done"
                add_log(job, "Задача завершена.")
        except Exception as e:
            job["status"] = "error"
            job["error"] = str(e)
            add_log(job, f"КРИТИЧЕСКАЯ ОШИБКА: {e}")
        finally:
            collect_outputs(job)
            with _lock:
                total = job["progress"]["total"]
                if job["status"] in ("done", "error", "canceled") and total:
                    job["progress"]["current"] = total
                    job["progress"]["percent"] = 100

    thread = threading.Thread(target=_runner, daemon=True,
                              name=f"job-{job['id']}")
    thread.start()
    return thread


def cancel_job(job_id: str) -> bool:
    job = get_job(job_id)
    if not job:
        return False
    job["cancel_event"].set()
    add_log(job, "Получен запрос на прерывание…")
    return True


def cleanup_old_jobs():
    """Удаляет с диска результаты задач старше TTL."""
    if not os.path.isdir(JOBS_DIR):
        return
    cutoff = time.time() - JOB_TTL_HOURS * 3600
    for job_id in os.listdir(JOBS_DIR):
        path = os.path.join(JOBS_DIR, job_id)
        try:
            if os.path.isdir(path) and os.path.getmtime(path) < cutoff:
                shutil.rmtree(path, ignore_errors=True)
        except OSError:
            pass
