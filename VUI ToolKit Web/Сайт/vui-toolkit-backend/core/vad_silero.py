"""
VAD на основе Silero (torch hub) для VUI ToolKit.

Вырезает из аудиозаписей фрагменты речи ИЛИ пауз (на выбор),
ограничивает длительность фрагментов (min/max), слишком длинные
фрагменты режет на куски, и возвращает таблицу длительностей.
"""

import math
import os

import numpy as np
import scipy.signal
import scipy.io.wavfile

_MODEL = None
_UTILS = None
TARGET_SR = 16000  # Silero VAD работает на 16 кГц


def _load_model():
    """Ленивая загрузка модели Silero VAD (один раз за сессию)."""
    global _MODEL, _UTILS
    if _MODEL is None:
        import torch
        model, utils = torch.hub.load(
            "snakers4/silero-vad", "silero_vad", trust_repo=True)
        _MODEL = model
        _UTILS = utils
    return _MODEL, _UTILS


def _to_mono_16k(signal: np.ndarray, sr: int) -> np.ndarray:
    """Моно + ресэмплинг до 16 кГц для подачи в модель."""
    if signal.ndim == 2:
        signal = signal.mean(axis=1)
    if sr != TARGET_SR:
        g = math.gcd(sr, TARGET_SR)
        signal = scipy.signal.resample_poly(signal, TARGET_SR // g, sr // g)
    return signal.astype(np.float32)


def _invert_timestamps(speech_ts: list, duration: float) -> list:
    """Превращает интервалы речи в интервалы пауз (и наоборот)."""
    pauses = []
    prev_end = 0.0
    for ts in speech_ts:
        if ts["start"] > prev_end:
            pauses.append({"start": prev_end, "end": ts["start"]})
        prev_end = max(prev_end, ts["end"])
    if prev_end < duration:
        pauses.append({"start": prev_end, "end": duration})
    return pauses


def _split_segment(start: float, end: float, min_dur: float, max_dur: float):
    """
    Дробит интервал [start, end) на куски в пределах [min_dur, max_dur].
    Куски короче min_dur отбрасываются (как в исходном скрипте).
    """
    dur = end - start
    if dur <= 0:
        return []
    if dur <= max_dur:
        return [(start, end)] if dur >= min_dur else []
    pieces = []
    n_full = int(dur // max_dur)
    for k in range(n_full):
        pieces.append((start + k * max_dur, start + (k + 1) * max_dur))
    rest_start = start + n_full * max_dur
    if end - rest_start >= min_dur:
        pieces.append((rest_start, end))
    return pieces


def run_vad(files: list, output_dir: str, mode: str = "speech",
            min_dur: float = 1.0, max_dur: float = 4.0,
            threshold: float = 0.7, log=None, progress=None,
            cancel_event=None) -> list:
    """
    Обрабатывает список аудиофайлов VAD'ом.

    mode: "speech" — сохранять фрагменты речи; "silence" — фрагменты пауз.
    Возвращает список словарей:
    {source_file, segment_file, start, end, duration} — для таблицы.
    """
    if mode not in ("speech", "silence"):
        raise ValueError("mode должен быть 'speech' или 'silence'")
    if min_dur <= 0 or max_dur <= 0 or min_dur > max_dur:
        raise ValueError("Некорректные границы длительности: "
                         "нужно 0 < min_dur <= max_dur")

    import torch
    model, utils = _load_model()
    get_speech_timestamps = utils[0]

    os.makedirs(output_dir, exist_ok=True)
    rows = []

    # Локальный импорт, чтобы модуль можно было использовать и без soundfile
    from core.audio_io import load_audio

    for file_idx, audio_file in enumerate(files, 1):
        if cancel_event is not None and cancel_event.is_set():
            if log:
                log("Задача прервана пользователем.")
            break
        name = os.path.basename(audio_file)
        if log:
            log(f"Обработка {file_idx}/{len(files)}: {name}")
        if progress:
            progress(file_idx - 1, len(files))
        try:
            orig_audio, orig_sr = load_audio(audio_file)
            if orig_audio.ndim == 2:
                orig_audio = orig_audio.mean(axis=1)
            duration = len(orig_audio) / orig_sr

            wav_16k = torch.from_numpy(_to_mono_16k(orig_audio, orig_sr))
            speech_ts = get_speech_timestamps(
                wav_16k, model, threshold=threshold, return_seconds=True)

            if mode == "speech":
                intervals = speech_ts
            else:
                intervals = _invert_timestamps(speech_ts, duration)

            if not intervals:
                if log:
                    log(f"  Подходящих фрагментов не найдено в {name}")
                continue

            base_name = os.path.splitext(name)[0]
            counter = 1
            for ts in intervals:
                for seg_start, seg_end in _split_segment(
                        ts["start"], ts["end"], min_dur, max_dur):
                    s = int(seg_start * orig_sr)
                    e = min(int(seg_end * orig_sr), len(orig_audio))
                    if e <= s:
                        continue
                    segment = orig_audio[s:e]
                    seg_dur = len(segment) / orig_sr

                    seg_name = f"{base_name}_{counter:03d}.wav"
                    seg_path = os.path.join(output_dir, seg_name)
                    scipy.io.wavfile.write(
                        seg_path, orig_sr, (segment * 32767).astype(np.int16))
                    rows.append({
                        "source_file": name,
                        "segment_file": seg_name,
                        "start": round(seg_start, 3),
                        "end": round(seg_end, 3),
                        "duration": round(seg_dur, 3),
                    })
                    counter += 1

            if log:
                log(f"  Сохранено фрагментов: {counter - 1}")
        except Exception as e:
            if log:
                log(f"  ОШИБКА при обработке {name}: {e}")
        if progress:
            progress(file_idx, len(files))

    return rows


def save_durations_table(rows: list, output_dir: str,
                         table_format: str = "xlsx") -> str:
    """
    Сохраняет таблицу длительностей фрагментов в output_dir.
    table_format: 'xlsx' или 'csv'. Возвращает путь к файлу таблицы.
    """
    if not rows:
        raise ValueError("Нет данных для сохранения таблицы")
    import pandas as pd
    df = pd.DataFrame(rows)
    if table_format == "csv":
        path = os.path.join(output_dir, "segments_durations.csv")
        df.to_csv(path, index=False, encoding="utf-8-sig")
    else:
        path = os.path.join(output_dir, "segments_durations.xlsx")
        df.to_excel(path, index=False)
    return path
