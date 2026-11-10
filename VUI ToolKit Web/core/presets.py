"""
Пользовательские пресеты пайплайнов.

Хранятся в user_presets.json в корне проекта. Пресет —
это имя + список шагов {"effect": <id>, "params": {...}},
тот же формат, что и у встроенных PRESETS в core.effects.
"""

import json
import os

_PRESETS_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "user_presets.json")


def load_user_presets() -> dict:
    """Возвращает {имя: [шаги]}. При отсутствии файла — пустой dict."""
    try:
        with open(_PRESETS_PATH, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_user_preset(name: str, steps: list) -> bool:
    """Сохраняет (или перезаписывает) пользовательский пресет."""
    name = name.strip()
    if not name:
        return False
    presets = load_user_presets()
    presets[name] = steps
    return _write(presets)


def delete_user_preset(name: str) -> bool:
    presets = load_user_presets()
    if name in presets:
        del presets[name]
        return _write(presets)
    return False


def _write(presets: dict) -> bool:
    try:
        with open(_PRESETS_PATH, "w", encoding="utf-8") as f:
            json.dump(presets, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False
