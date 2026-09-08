"""
Склейка аудиозаписей для VUI ToolKit.

Объединяет несколько записей в один файл в заданном порядке,
между записями вставляется пауза заданной длительности
(0 — прямая склейка без паузы). Все записи приводятся
к единой частоте дискретизации и числу каналов.
"""

import math
import os

import numpy as np
import scipy.signal

from core.audio_io import load_audio, save_audio


def _resample_to(signal: np.ndarray, sr: int, target_sr: int) -> np.ndarray:
    if sr == target_sr:
        return signal
    g = math.gcd(sr, target_sr)
    return scipy.signal.resample_poly(
        signal, target_sr // g, sr // g, axis=0).astype(np.float32)


def merge_audio_files(files: list, output_path: str,
                      pause_sec: float = 0.0,
                      target_sr: int = None,
                      fmt: str = "WAV", subtype: str = "PCM_16",
                      log=None, cancel_event=None) -> str:
    """
    Склеивает файлы в один.

    files      — список путей в нужном порядке;
    pause_sec  — пауза (тишина) между записями, секунды (0 — без паузы);
    target_sr  — частота дискретизации результата
                 (None — взять у первого файла);
    fmt/subtype — формат и PCM-разрядность результата.
    """
    if not files:
        raise ValueError("Список файлов для склейки пуст")
    if pause_sec < 0:
        raise ValueError("Пауза не может быть отрицательной")

    # Частота результата: у первого файла, если не задана явно
    if target_sr is None:
        _, target_sr = load_audio(files[0])

    pause_samples = int(target_sr * pause_sec)
    parts = []
    for i, path in enumerate(files, 1):
        if cancel_event is not None and cancel_event.is_set():
            if log:
                log("Задача прервана пользователем.")
            return None
        signal, sr = load_audio(path)
        if signal.ndim == 2:  # приводим всё к моно для однозначности
            signal = signal.mean(axis=1)
        if sr != target_sr:
            signal = _resample_to(signal, sr, target_sr)
            if log:
                log(f"  {os.path.basename(path)}: ресэмплинг {sr} -> "
                    f"{target_sr} Гц")
        if parts and pause_samples > 0:
            parts.append(np.zeros(pause_samples, dtype=np.float32))
        parts.append(signal)
        if log:
            log(f"  [{i}/{len(files)}] {os.path.basename(path)} "
                f"({len(signal) / target_sr:.2f} с)")

    merged = np.concatenate(parts) if parts else np.zeros(0, dtype=np.float32)
    save_audio(output_path, merged, target_sr, fmt, subtype)
    if log:
        log(f"Итог: {len(merged) / target_sr:.2f} с, {target_sr} Гц -> "
            f"{os.path.basename(output_path)}")
    return output_path
