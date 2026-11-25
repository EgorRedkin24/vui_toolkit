"""
Библиотека ambience-дорожек (фоновых звуков) для VUI ToolKit.

Дорожки лежат в папке ambience/ в корне проекта. Список для выбора
строится по её содержимому; новые дорожки копируются туда с компьютера.
"""

import os
import shutil

from core.audio_io import AUDIO_EXTENSIONS, unique_path

AMBIENCE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ambience")


def list_tracks() -> list:
    """Имена файлов дорожек в библиотеке (отсортированы)."""
    if not os.path.isdir(AMBIENCE_DIR):
        return []
    return sorted(
        name for name in os.listdir(AMBIENCE_DIR)
        if os.path.isfile(os.path.join(AMBIENCE_DIR, name))
        and os.path.splitext(name)[1].lower() in AUDIO_EXTENSIONS)


def track_path(name: str) -> str:
    """Полный путь к дорожке библиотеки по имени файла."""
    return os.path.join(AMBIENCE_DIR, name)


def import_track(source_path: str) -> str:
    """
    Копирует аудиофайл с компьютера в библиотеку. При совпадении имени
    добавляется числовой суффикс (существующие дорожки не перезаписываются).
    Возвращает имя файла в библиотеке.
    """
    if os.path.splitext(source_path)[1].lower() not in AUDIO_EXTENSIONS:
        raise ValueError("Неподдерживаемый формат аудио")
    os.makedirs(AMBIENCE_DIR, exist_ok=True)
    dest, _ = unique_path(os.path.join(AMBIENCE_DIR,
                                       os.path.basename(source_path)))
    shutil.copy2(source_path, dest)
    return os.path.basename(dest)
