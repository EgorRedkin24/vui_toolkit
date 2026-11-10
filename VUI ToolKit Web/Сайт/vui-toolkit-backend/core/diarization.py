"""
Диаризация (разделение спикеров) через pyannote.audio для VUI ToolKit.

Результат — текстовый файл с интервалами и спикерами. По умолчанию
сохраняется РЯДОМ С ИСХОДНЫМ аудио, имя — <имя_исходника>_dia.txt.
Требуется токен Hugging Face с доступом к pyannote/speaker-diarization.
"""

import os
import re
import time
import warnings

_PIPELINE = None

MODEL_NAME = "pyannote/speaker-diarization-community-1"


def _get_pipeline(hf_token: str):
    """Ленивая загрузка пайплайна pyannote (один раз за сессию)."""
    global _PIPELINE
    if _PIPELINE is None:
        from pyannote.audio import Pipeline
        _PIPELINE = Pipeline.from_pretrained(MODEL_NAME, token=hf_token)
    return _PIPELINE


def diarize_file(audio_path: str, hf_token: str,
                 output_dir: str = None, log=None) -> str:
    """
    Диаризует один аудиофайл.
    output_dir=None — сохранить рядом с исходным файлом.
    Возвращает путь к созданному <имя>_dia.txt.
    """
    pipeline = _get_pipeline(hf_token)

    start_time = time.time()
    output = pipeline(audio_path)
    elapsed = time.time() - start_time

    lines = ["=== ДИАРИЗАЦИЯ ===\n",
             "Формат: [Время начала - Время конца] Спикер\n\n"]
    n_segments = 0
    for segment, _, speaker_raw in output.speaker_diarization.itertracks(
            yield_label=True):
        match = re.search(r"(\d+)$", speaker_raw)
        speaker = (f"speaker_{int(match.group(1))}" if match
                   else speaker_raw.lower())
        lines.append(f"[{segment.start:.2f} - {segment.end:.2f}] "
                     f"Спикер {speaker}\n")
        n_segments += 1

    out_dir = output_dir or os.path.dirname(os.path.abspath(audio_path))
    os.makedirs(out_dir, exist_ok=True)
    stem = os.path.splitext(os.path.basename(audio_path))[0]
    out_path = os.path.join(out_dir, f"{stem}_dia.txt")
    with open(out_path, "w", encoding="utf-8-sig") as f:
        f.writelines(lines)

    if log:
        log(f"  {n_segments} сегментов за {elapsed:.1f} с -> "
            f"{os.path.basename(out_path)}")
    return out_path


def diarize_files(files: list, hf_token: str, output_dir: str = None,
                  log=None, progress=None, cancel_event=None) -> list:
    """
    Пакетная диаризация. output_dir=None — рядом с каждым исходником.
    progress(i, total) — колбэк прогресса; cancel_event — threading.Event.
    Возвращает список путей к созданным файлам.
    """
    warnings.filterwarnings("ignore", message="std\\(\\): degrees of freedom")
    results = []
    total = len(files)
    for i, path in enumerate(files, 1):
        if cancel_event is not None and cancel_event.is_set():
            if log:
                log("Задача прервана пользователем.")
            break
        name = os.path.basename(path)
        if log:
            log(f"Диаризация {i}/{total}: {name}")
        if progress:
            progress(i - 1, total)
        try:
            results.append(diarize_file(path, hf_token, output_dir, log))
        except Exception as e:
            if log:
                log(f"  ОШИБКА: {e}")
        if progress:
            progress(i, total)
    return results
