"""
Чтение и запись аудиофайлов для VUI ToolKit.

Внутри приложения сигнал всегда представлен как float32 в диапазоне [-1, 1]
(моно — shape (n,), многоканальный — shape (n, channels)).
Запись поддерживает выбор контейнера (WAV/FLAC/OGG/MP3) и PCM-разрядности.
"""

import os
import numpy as np
import soundfile as sf

AUDIO_EXTENSIONS = (".wav", ".mp3", ".ogg", ".flac", ".m4a")

# Поддерживаемые форматы сохранения: контейнер -> список подтипов (PCM и т.п.)
SAVE_FORMATS = {
    "WAV": {
        "ext": ".wav",
        "subtypes": ["PCM_16", "PCM_24", "PCM_32", "FLOAT"],
    },
    "FLAC": {
        "ext": ".flac",
        "subtypes": ["PCM_16", "PCM_24"],
    },
    "OGG": {
        "ext": ".ogg",
        "subtypes": ["VORBIS"],
    },
    "MP3": {
        "ext": ".mp3",
        "subtypes": [],  # у MP3 разрядность не выбирается
    },
}

DEFAULT_FORMAT = "WAV"
DEFAULT_SUBTYPE = "PCM_16"


def is_audio_file(path: str) -> bool:
    return os.path.splitext(path)[1].lower() in AUDIO_EXTENSIONS


def collect_audio_files(folder: str) -> list:
    """Возвращает отсортированный список аудиофайлов в папке (без вложенных)."""
    files = []
    for name in sorted(os.listdir(folder)):
        full = os.path.join(folder, name)
        if os.path.isfile(full) and is_audio_file(full):
            files.append(full)
    return files


def load_audio(path: str) -> tuple:
    """
    Читает аудиофайл.
    Возвращает (signal, samplerate): signal — float32 в [-1, 1],
    моно: shape (n,), стерео/мультиканал: shape (n, channels).
    """
    signal, sr = sf.read(path, always_2d=False, dtype="float32")
    return signal, sr


def save_audio(path: str, signal: np.ndarray, sr: int,
               fmt: str = DEFAULT_FORMAT, subtype: str = DEFAULT_SUBTYPE) -> str:
    """
    Сохраняет сигнал в заданном формате.
    fmt — ключ из SAVE_FORMATS ('WAV', 'FLAC', 'OGG', 'MP3'),
    subtype — PCM-разрядность ('PCM_16' и т.п.), если применимо.
    """
    fmt = fmt.upper()
    if fmt not in SAVE_FORMATS:
        raise ValueError(f"Неподдерживаемый формат: {fmt}")

    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)

    signal = np.asarray(signal, dtype=np.float32)
    peak = np.max(np.abs(signal)) if signal.size else 0
    if peak > 1.0:  # защита от клиппинга при записи
        signal = signal / peak

    if SAVE_FORMATS[fmt]["subtypes"]:
        if subtype not in SAVE_FORMATS[fmt]["subtypes"]:
            subtype = SAVE_FORMATS[fmt]["subtypes"][0]
        sf.write(path, signal, sr, format=fmt, subtype=subtype)
    else:
        sf.write(path, signal, sr, format=fmt)
    return path


def get_output_path(source_path: str, output_dir: str, suffix: str,
                    fmt: str = DEFAULT_FORMAT) -> str:
    """Формирует путь результата: <output_dir>/<имя_исходника><suffix>.<ext>."""
    base = os.path.splitext(os.path.basename(source_path))[0]
    ext = SAVE_FORMATS[fmt.upper()]["ext"]
    return os.path.join(output_dir, f"{base}{suffix}{ext}")


def unique_path(path: str) -> tuple:
    """
    Защита от перезаписи: если файл уже существует, добавляет
    числовой суффикс _1, _2, ... перед расширением.
    Возвращает (итоговый_путь, был_ли_добавлен_суффикс).
    """
    if not os.path.exists(path):
        return path, False
    base, ext = os.path.splitext(path)
    n = 1
    while os.path.exists(f"{base}_{n}{ext}"):
        n += 1
    return f"{base}_{n}{ext}", True
