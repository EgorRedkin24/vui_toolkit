"""
Эндпоинты инструментов VUI ToolKit.

Общий паттерн: POST multipart/form-data, поле `params` — JSON-строка
с параметрами, файлы — в полях files/table/ref_audio. В ответ — {"id"}.
Дальше фронтенд опрашивает GET /api/jobs/{id} до status=done|error|canceled.
"""

import json
import os

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from api import jobs as job_store
from api import services

router = APIRouter(prefix="/api", tags=["tools"])

ALLOWED_TABLE = (".xlsx", ".xls", ".csv")


def _allowed_audio() -> tuple:
    from core.audio_io import AUDIO_EXTENSIONS
    return AUDIO_EXTENSIONS


def _parse_params(raw: str) -> dict:
    try:
        return json.loads(raw) if raw else {}
    except json.JSONDecodeError as e:
        raise HTTPException(400, f"Некорректный JSON в поле params: {e}")


def _check_ext(files: list, allowed: tuple, what: str):
    for f in files:
        ext = os.path.splitext(f.filename or "")[1].lower()
        if ext not in allowed:
            raise HTTPException(
                400, f"{what}: неподдерживаемый формат «{f.filename}» "
                     f"(нужны: {', '.join(allowed)})")


# ------------------------------------------------------------ 1. Обработка

@router.post("/jobs/process")
def start_process(params: str = Form(...),
                  files: list[UploadFile] = File(...)):
    """Обработка аудио: пресет или свой пайплайн эффектов."""
    p = _parse_params(params)
    _check_ext(files, _allowed_audio(), "Обработка")
    try:
        steps = services.resolve_pipeline(p)
    except ValueError as e:
        raise HTTPException(400, str(e))
    job = job_store.create_job("process", p)
    paths = services.save_uploads(job["id"], files)
    job_store.run_job(job, services.with_normalization, paths,
                      services.run_processing, steps,
                      (p.get("format") or "WAV").upper(),
                      p.get("subtype") or "PCM_16",
                      bool(p.get("keep_names", False)))
    return {"id": job["id"]}


@router.post("/preview/process")
def preview_process(params: str = Form(...),
                    file: UploadFile = File(...)):
    """
    Предпрослушивание: обрабатывает ОДИН файл синхронно и сразу
    возвращает готовое аудио (без создания задачи).
    """
    p = _parse_params(params)
    _check_ext([file], _allowed_audio(), "Предпросмотр")
    import tempfile
    with tempfile.NamedTemporaryFile(
            suffix=os.path.splitext(file.filename)[1], delete=False) as tmp:
        tmp.write(file.file.read())
        src = tmp.name
    fmt = (p.get("format") or "WAV").upper()
    ext = services.SAVE_FORMATS.get(fmt, services.SAVE_FORMATS["WAV"])["ext"]
    out = tempfile.NamedTemporaryFile(suffix=ext, delete=False).name
    try:
        services.process_preview(src, p, out)
    except Exception as e:
        raise HTTPException(400, str(e))
    finally:
        os.unlink(src)
    from fastapi.responses import FileResponse
    return FileResponse(out, media_type="application/octet-stream",
                        filename=f"preview{ext}")


# ------------------------------------------------------------------ 2. VAD

@router.post("/jobs/vad")
def start_vad(params: str = Form(...),
              files: list[UploadFile] = File(...)):
    """VAD (Silero): нарезка записей на фрагменты речи или пауз."""
    p = _parse_params(params)
    _check_ext(files, _allowed_audio(), "VAD")
    job = job_store.create_job("vad", p)
    paths = services.save_uploads(job["id"], files)
    job_store.run_job(job, services.with_normalization, paths,
                      services.run_vad, p)
    return {"id": job["id"]}


# ---------------------------------------------------------- 3. Диаризация

@router.post("/jobs/diarize")
def start_diarize(params: str = Form(...),
                  files: list[UploadFile] = File(...)):
    """Диаризация (pyannote): разделение спикеров, нужен HF-токен."""
    p = _parse_params(params)
    _check_ext(files, _allowed_audio(), "Диаризация")
    job = job_store.create_job("diarization", p)
    paths = services.save_uploads(job["id"], files)
    job_store.run_job(job, services.with_normalization, paths,
                      services.run_diarization, p)
    return {"id": job["id"]}


# ------------------------------------------------------------- 4. Склейка

@router.post("/jobs/merge")
def start_merge(params: str = Form(...),
                files: list[UploadFile] = File(...)):
    """Склейка записей в один файл (порядок = порядок загрузки)."""
    p = _parse_params(params)
    _check_ext(files, _allowed_audio(), "Склейка")
    job = job_store.create_job("merge", p)
    paths = services.save_uploads(job["id"], files)
    job_store.run_job(job, services.with_normalization, paths,
                      services.run_merge, p)
    return {"id": job["id"]}


# ------------------------------------------------------------------ 5. TTS

@router.post("/jobs/tts")
def start_tts(params: str = Form(...),
              table: UploadFile = File(None),
              ref_audio: UploadFile = File(None),
              ref_files: list[UploadFile] = File(None)):
    """
    Синтез речи. engine=elevenlabs|omnivoice, mode=single|table.
    table — xlsx/csv со столбцом text; ref_audio — эталон голоса
    (OmniVoice); ref_files — пул эталонов для таблицы OmniVoice.
    """
    p = _parse_params(params)
    job = job_store.create_job("tts", p)
    table_path = services.save_upload(job["id"], table) if table else None
    ref_path = (services.save_upload(job["id"], ref_audio)
                if ref_audio else None)
    ref_pool = {}
    for f in (ref_files or []):
        ref_pool[os.path.basename(f.filename)] = \
            services.save_upload(job["id"], f)
    if p.get("mode") == "table" and not table_path:
        job_store.cancel_job(job["id"])
        raise HTTPException(400, "В режиме «таблица» нужен файл таблицы")
    job_store.run_job(job, services.run_tts, p, table_path, ref_path,
                      ref_pool)
    return {"id": job["id"]}


# ------------------------------------------------------ 6. Поиск и разметка

@router.post("/jobs/search")
def start_search(params: str = Form(...),
                 files: list[UploadFile] = File(...)):
    """Поиск слов/словосочетаний (Whisper) с созданием .seg-разметки."""
    p = _parse_params(params)
    _check_ext(files, _allowed_audio(), "Поиск")
    job = job_store.create_job("search", p)
    paths = services.save_uploads(job["id"], files)
    job_store.run_job(job, services.with_normalization, paths,
                      services.run_search, p)
    return {"id": job["id"]}


# -------------------------------------------------------------- 7. Метаданные

@router.post("/jobs/metadata")
def start_metadata(params: str = Form(...),
                   table: UploadFile = File(...),
                   files: list[UploadFile] = File(...)):
    """Генерация метаданных реплик + нарезка аудио по .seg-разметке.
    files — аудиофайлы И .seg-файлы одним списком."""
    p = _parse_params(params)
    _check_ext([table], ALLOWED_TABLE, "Метаданные (таблица)")
    _check_ext(files, _allowed_audio() + (".seg",), "Метаданные (файлы)")
    job = job_store.create_job("metadata", p)
    table_path = services.save_upload(job["id"], table)
    services.save_uploads(job["id"], files)
    cfg = services.metadata_cfg(p, table_path,
                                job_store.uploads_dir(job["id"]), job)
    job_store.run_job(job, services.run_metadata, cfg)
    return {"id": job["id"]}


@router.post("/metadata/preview")
def metadata_preview(params: str = Form(...),
                     table: UploadFile = File(...),
                     files: list[UploadFile] = File(None)):
    """Синхронный предпросмотр первых N строк метаданных (без нарезки)."""
    from core.metadata_gen import preview_metadata

    p = _parse_params(params)
    _check_ext([table], ALLOWED_TABLE, "Предпросмотр (таблица)")
    job = job_store.create_job("metadata_preview", p)
    table_path = services.save_upload(job["id"], table)
    if files:
        _check_ext(files, _allowed_audio() + (".seg",), "Предпросмотр (файлы)")
        saved = services.save_uploads(job["id"], files)
        services.normalize_audio(job["id"], saved,
                                 log=lambda m: job_store.add_log(job, m))
    cfg = services.metadata_cfg(p, table_path,
                                job_store.uploads_dir(job["id"]), job)
    try:
        text = preview_metadata(cfg, max_rows=int(p.get("preview_rows", 2)),
                                log=lambda m: job_store.add_log(job, m))
    except Exception as e:
        raise HTTPException(400, str(e))
    return {"preview": text, "logs": [l["msg"] for l in job["logs"]]}
