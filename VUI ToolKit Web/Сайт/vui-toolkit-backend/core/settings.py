"""
Сохранение настроек приложения между запусками.

Хранится JSON-файл user_settings.json в корне проекта
(переносится вместе с приложением). Токены и ключи хранятся
в открытом виде — не делитесь этим файлом.
"""

import json
import os

_SETTINGS_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "user_settings.json")


def load_settings() -> dict:
    """Читает настройки. Если файла нет или он битый — пустой dict."""
    try:
        with open(_SETTINGS_PATH, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_settings(data: dict) -> bool:
    """Записывает настройки. Возвращает True при успехе."""
    try:
        with open(_SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False
