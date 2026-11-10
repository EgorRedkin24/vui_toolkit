"""
Сервисный слой: адаптеры между HTTP-запросами и функциями core/.

Все тяжёлые функции принимают job и пользуются колбэками
add_log / make_progress / cancel_event — точно так же, как
десктопный GUI пользовался log/progress/cancel_event.
"""

import os
import shutil

from fastapi import UploadFile

from api import jobs as job_store
from core.audio_io import (load_audio, save_audio, get_output_path,
                           unique_path, SAVE_FORMATS)
from core.effects import EFFECTS, PRESETS, apply_pipeline


def save_upload(job_id: str, upload: UploadFile, filename: str = None) -> str:
    """Сохраняет загруженный файл в папку uploads задачи."""
    name = os.path.basename(filename or upload.filename or "file")
    dest = os.path.join(job_store.uploads_dir(job_id), name)
    dest, _ = unique_path(dest)
    with open(dest, "wb") as f:
        shutil.copyfileobj(upload.file, f)
    return dest


def save_uploads(job_id: str, uploads: list) -> list:
    return [save_upload(job_id, u) for u in uploads]


def normalize_audio(job_id: str, paths: list, log=None) -> list:
    """
    Приводит загруженные аудиофайлы к виду, который гарантированно
    читается всеми движками (soundfile/pyannote/Whisper/OmniVoice):
    если soundfile не может открыть файл (m4a, aac, wma, opus, webm,
    amr, старый mp3-кодек...), файл конвертируется ffmpeg'ом в WAV
    с тем же именем (расширение меняется на .wav), оригинал удаляется.
    Не-аудио файлы (например, .seg) пропускаются как есть.
    """
    import soundfile as sf
    from core.audio_io import AUDIO_EXTENSIONS, _ffmpeg_to_wav, is_audio_file

    normalized = []
    for path in paths:
        if not is_audio_file(path):
            normalized.append(path)
            continue
        try:
            sf.info(path)  # читается напрямую — оставляем
            normalized.append(path)
            continue
        except Exception:
            pass
        stem = os.path.splitext(path)[0]
        try:
            tmp_wav = _ffmpeg_to_wav(path)
            shutil.move(tmp_wav, stem + ".wav")
            os.unlink(path)
            if log:
                log(f"  {os.path.basename(path)}: формат сконвертирован "
                    f"в WAV для совместимости")
            normalized.append(stem + ".wav")
        except Exception as e:
            # не удалось — оставляем исходник, ошибка всплывёт в логе задачи
            if log:
                log(f"  ПРЕДУПРЕЖДЕНИЕ: не удалось сконвертировать "
                    f"{os.path.basename(path)}: {e}")
            normalized.append(path)
    return normalized


# ------------------------------------------------------------- обработка

def with_normalization(job: dict, files: list, target, *args, **kwargs):
    """Обертка для инструментов: сначала конвертирует загруженные
    файлы нечитаемых форматов в WAV, потом запускает инструмент."""
    files = normalize_audio(job["id"], files,
                            log=lambda m: job_store.add_log(job, m))
    return target(job, files, *args, **kwargs)

def run_processing(job: dict, files: list, steps: list, fmt: str,
                   subtype: str, keep_names: bool):
    """Пакетная обработка аудио пайплайном эффектов."""
    log = lambda m: job_store.add_log(job, m)
    progress = job_store.make_progress(job)
    cancel = job["cancel_event"]
    out_dir = job_store.outputs_dir(job["id"])

    total = len(files)
    done = 0
    for i, path in enumerate(files, 1):
        if cancel.is_set():
            break
        name = os.path.basename(path)
        log(f"Обработка {i}/{total}: {name}")
        progress(i - 1, total)
        try:
            signal, sr = load_audio(path)
            signal, sr = apply_pipeline(signal, sr, steps, log=log)
            suffix = "" if keep_names else "_processed"
            out_path = get_output_path(path, out_dir, suffix, fmt)
            out_path, renamed = unique_path(out_path)
            if renamed:
                log(f"  Файл с таким именем уже есть — сохранено как "
                    f"{os.path.basename(out_path)}")
            save_audio(out_path, signal, sr, fmt, subtype)
            log(f"  -> {os.path.basename(out_path)}")
            done += 1
        except Exception as e:
            log(f"  ОШИБКА при обработке {name}: {e}")
        progress(i, total)
    log(f"Готово: обработано {done} из {total}.")


def resolve_pipeline(params: dict) -> list:
    """
    Собирает шаги пайплайна из параметров запроса:
    mode=preset (preset_name) или mode=pipeline (steps + флаги тишины).
    """
    from core.presets import load_user_presets

    mode = params.get("mode", "preset")
    if mode == "preset":
        name = (params.get("preset_name") or "").lstrip("★ ").strip()
        steps = PRESETS.get(name) or load_user_presets().get(name)
        if steps is None:
            raise ValueError(f"Пресет не найден: {name}")
        # отдельные флажки тишины действуют и поверх пресета
        steps = list(steps)
    else:
        steps = list(params.get("steps") or [])
        if not steps:
            raise ValueError("Пайплайн пуст: добавьте хотя бы один эффект")

    if params.get("silence_start", {}).get("enabled"):
        steps.insert(0, {"effect": "add_silence_start", "params": {
            "duration": float(params["silence_start"].get("duration", 0.2))}})
    if params.get("silence_end", {}).get("enabled"):
        steps.append({"effect": "add_silence_end", "params": {
            "duration": float(params["silence_end"].get("duration", 0.2))}})

    for step in steps:
        if step.get("effect") not in EFFECTS:
            raise ValueError(f"Неизвестный эффект: {step.get('effect')}")
    return steps


def process_preview(upload_path: str, params: dict, out_path: str) -> str:
    """Синхронный предпросмотр: обрабатывает один файл, пишет в out_path."""
    steps = resolve_pipeline(params)
    fmt = (params.get("format") or "WAV").upper()
    subtype = params.get("subtype") or "PCM_16"
    signal, sr = load_audio(upload_path)
    signal, sr = apply_pipeline(signal, sr, steps)
    save_audio(out_path, signal, sr, fmt, subtype)
    return out_path


# ------------------------------------------------------------------- VAD

def run_vad(job: dict, files: list, params: dict):
    from core.vad_silero import run_vad as core_run_vad, save_durations_table

    log = lambda m: job_store.add_log(job, m)
    out_dir = job_store.outputs_dir(job["id"])
    rows = core_run_vad(
        files, out_dir,
        mode=params.get("mode", "speech"),
        min_dur=float(params.get("min_dur", 1.0)),
        max_dur=float(params.get("max_dur", 4.0)),
        threshold=float(params.get("threshold", 0.7)),
        log=log, progress=job_store.make_progress(job),
        cancel_event=job["cancel_event"])
    if rows:
        table = save_durations_table(
            rows, out_dir, params.get("table_format", "xlsx"))
        log(f"Таблица длительностей: {os.path.basename(table)}")
    elif not job["cancel_event"].is_set():
        log("Фрагменты не найдены — таблица не создана.")


# ------------------------------------------------------------ диаризация

def run_diarization(job: dict, files: list, params: dict):
    from core.diarization import diarize_files

    hf_token = (params.get("hf_token") or "").strip()
    if not hf_token:
        raise ValueError("Не задан токен Hugging Face")
    diarize_files(files, hf_token,
                  output_dir=job_store.outputs_dir(job["id"]),
                  log=lambda m: job_store.add_log(job, m),
                  progress=job_store.make_progress(job),
                  cancel_event=job["cancel_event"])


# --------------------------------------------------------------- склейка

def run_merge(job: dict, files: list, params: dict):
    from core.merge_audio import merge_audio_files

    fmt = (params.get("format") or "WAV").upper()
    ext = SAVE_FORMATS[fmt]["ext"]
    out_name = (params.get("output_name") or "merged").strip() or "merged"
    out_path = os.path.join(job_store.outputs_dir(job["id"]),
                            out_name + ext)
    out_path, _ = unique_path(out_path)
    sr_raw = params.get("target_sr")
    target_sr = int(sr_raw) if sr_raw else None
    merge_audio_files(files, out_path,
                      pause_sec=float(params.get("pause_sec", 0.0)),
                      target_sr=target_sr, fmt=fmt,
                      subtype=params.get("subtype") or "PCM_16",
                      log=lambda m: job_store.add_log(job, m),
                      cancel_event=job["cancel_event"])


# ------------------------------------------------------------------- TTS

def run_tts(job: dict, params: dict, table_path: str = None,
            ref_audio_path: str = None, ref_pool: dict = None):
    """
    engine: 'elevenlabs' | 'omnivoice'; mode: 'single' | 'table'.
    ref_pool: {basename: путь} — загруженные эталонные записи голоса
    для таблиц OmniVoice (столбец voice сопоставляется по имени файла).
    """
    log = lambda m: job_store.add_log(job, m)
    out_dir = job_store.outputs_dir(job["id"])
    engine = params.get("engine", "elevenlabs")
    mode = params.get("mode", "single")

    # эталонные записи приводим к читаемому формату (для OmniVoice)
    log0 = lambda m: job_store.add_log(job, m)
    if ref_audio_path:
        ref_audio_path = normalize_audio(job["id"], [ref_audio_path],
                                         log=log0)[0]
    if ref_pool:
        ref_pool = {name: normalize_audio(job["id"], [p], log=log0)[0]
                    for name, p in ref_pool.items()}

    if engine == "elevenlabs":
        from core import tts_elevenlabs as tts
        api_key = (params.get("api_key") or "").strip()
        voice_id = (params.get("voice_id") or "").strip()
        if not api_key or not voice_id:
            raise ValueError("Для ElevenLabs нужны api_key и voice_id")
        model_id = params.get("model_id") or tts.DEFAULT_MODEL
        if mode == "single":
            tts.synthesize_single(params.get("text", ""), voice_id, api_key,
                                  out_dir, model_id, log=log)
        else:
            df = tts.load_table(table_path)
            tts.synthesize_table(df, voice_id, api_key, out_dir, model_id,
                                 log=log,
                                 progress=job_store.make_progress(job),
                                 cancel_event=job["cancel_event"],
                                 filename_template=params.get("filename_template") or None)
    else:
        from core import tts_omnivoice as tts
        if mode == "single":
            if not ref_audio_path:
                raise ValueError("Для OmniVoice нужна эталонная запись голоса")
            tts.synthesize_single(params.get("text", ""), ref_audio_path,
                                  out_dir, log=log)
        else:
            import pandas as pd
            df = pd.read_csv(table_path) if table_path.lower().endswith(".csv") \
                else pd.read_excel(table_path)
            # пути в столбце voice подменяем на загруженные файлы
            if ref_pool:
                for col in ("voice", "voice_id"):
                    if col in df.columns:
                        df[col] = df[col].map(
                            lambda v: ref_pool.get(os.path.basename(str(v)), v))
            tts.synthesize_table(df, ref_audio_path, out_dir, log=log,
                                 progress=job_store.make_progress(job),
                                 cancel_event=job["cancel_event"],
                                 filename_template=params.get("filename_template") or None)


# --------------------------------------------------------- поиск и .seg

def run_search(job: dict, files: list, params: dict):
    from core.word_search import search_words_in_files

    words = params.get("words") or []
    if isinstance(words, str):
        words = [w.strip() for w in words.splitlines() if w.strip()]
    search_words_in_files(
        files, words,
        max_fragments=int(params.get("max_fragments", 1)),
        model_name=params.get("model", "small"),
        language=params.get("language", "ru"),
        fuzzy=bool(params.get("fuzzy", False)),
        similarity=float(params.get("similarity", 0.8)),
        log=lambda m: job_store.add_log(job, m),
        progress=job_store.make_progress(job),
        cancel_event=job["cancel_event"])
    # .seg создаются рядом с исходниками (uploads) — копируем в outputs
    out_dir = job_store.outputs_dir(job["id"])
    for path in files:
        seg = os.path.splitext(path)[0] + ".seg"
        if os.path.isfile(seg):
            shutil.copy2(seg, os.path.join(out_dir, os.path.basename(seg)))


# -------------------------------------------------------------- метаданные

def metadata_cfg(params: dict, table_path: str, audio_dir: str,
                 job: dict) -> dict:
    """Собирает cfg для core.metadata_gen из параметров запроса."""
    out_dir = job_store.outputs_dir(job["id"])
    return {
        "table_path": table_path,
        "audio_dir": audio_dir,
        "output_path": os.path.join(out_dir, params.get("output_name")
                                    or "metadata.txt"),
        "output_audio_dir": out_dir,
        "text_column": params.get("text_column") or "text",
        "filename_column": params.get("filename_column") or "filename",
        "intent_column": params.get("intent_column") or "intent",
        "voice_enabled": bool(params.get("voice_enabled", True)),
        "voice_line": params.get("voice_line") or "",
        "voice_indent": int(params.get("voice_indent") or 0),
        "intents_enabled": bool(params.get("intents_enabled", True)),
        "intent_template": params.get("intent_template") or "",
        "intent_indent": int(params.get("intent_indent") or 0),
        "record_template": params.get("record_template") or "",
        "record_indent": int(params.get("record_indent") or 0),
        "parts_template": params.get("parts_template") or "",
        "parts_indent": int(params.get("parts_indent") or 0),
        "parts_content_indent": int(params.get("parts_content_indent") or 0),
        "number_enabled": bool(params.get("number_enabled", False)),
        "number_start": int(params.get("number_start") or 1),
        "variables": params.get("variables") or [],
    }


def run_metadata(job: dict, cfg: dict):
    from core.metadata_gen import generate_metadata

    # приводим загруженные аудио к читаемому формату (нарезка идёт
    # через soundfile напрямую, поэтому конверсия важна именно здесь)
    upload_dir = job_store.uploads_dir(job["id"])
    paths = [os.path.join(upload_dir, n) for n in sorted(os.listdir(upload_dir))]
    normalize_audio(job["id"], paths,
                    log=lambda m: job_store.add_log(job, m))

    stats = generate_metadata(cfg, log=lambda m: job_store.add_log(job, m),
                              progress=job_store.make_progress(job),
                              cancel_event=job["cancel_event"])
    job_store.add_log(
        job, f"Итог: записей — {stats['records']}, фрагментов в parts — "
             f"{stats['fragments']}, предупреждений — {stats['warnings']}.")
