"""
Воспроизведение аудио для предпрослушки в VUI ToolKit.

Приоритет: simpleaudio (проигрывает WAV прямо в приложении).
Если simpleaudio не установлен или формат не WAV — файл открывается
внешним проигрывателем системы.
"""

import os
import subprocess
import sys

try:
    import simpleaudio as sa
    HAS_SIMPLEAUDIO = True
except ImportError:
    HAS_SIMPLEAUDIO = False

_PLAY_OBJ = None


def play_file(path: str, log=None) -> bool:
    """
    Воспроизводит аудиофайл. Возвращает True, если воспроизведение
    запущено внутри приложения, False — если открыт внешний плеер.
    """
    global _PLAY_OBJ
    stop()  # останавливаем предыдущее воспроизведение

    if HAS_SIMPLEAUDIO and path.lower().endswith(".wav"):
        try:
            _PLAY_OBJ = sa.WaveObject.from_wave_file(path).play()
            return True
        except Exception as e:
            if log:
                log(f"simpleaudio не смог воспроизвести файл: {e}")

    # Фолбэк: внешний проигрыватель ОС
    try:
        if sys.platform.startswith("win"):
            os.startfile(path)  # noqa: S606
        elif sys.platform == "darwin":
            subprocess.Popen(["afplay", path])
        else:
            subprocess.Popen(["xdg-open", path],
                             stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)
        if log:
            log("Файл открыт во внешнем проигрывателе "
                "(для воспроизведения внутри приложения "
                "установите simpleaudio)")
    except Exception as e:
        if log:
            log(f"Не удалось открыть файл: {e}")
    return False


def stop():
    """Останавливает текущее воспроизведение (если есть)."""
    global _PLAY_OBJ
    if HAS_SIMPLEAUDIO and _PLAY_OBJ is not None:
        try:
            _PLAY_OBJ.stop()
        except Exception:
            pass
    _PLAY_OBJ = None


def open_in_folder(path: str):
    """Открывает папку, содержащую файл (или саму папку)."""
    folder = path if os.path.isdir(path) else os.path.dirname(
        os.path.abspath(path))
    if sys.platform.startswith("win"):
        os.startfile(folder)  # noqa: S606
    elif sys.platform == "darwin":
        subprocess.Popen(["open", folder])
    else:
        subprocess.Popen(["xdg-open", folder],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
