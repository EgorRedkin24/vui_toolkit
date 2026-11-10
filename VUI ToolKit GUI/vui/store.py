"""Настройки приложения (тема, токены) поверх core/settings.py."""

from core import settings as _settings

DEFAULTS = {
    "theme": "dark",
    "hf_token": "",
    "elevenlabs_api_key": "",
    "elevenlabs_voice_id": "",
}


def load() -> dict:
    data = _settings.load_settings()
    # ключи могут лежать вложенно (как сохраняла tkinter-версия)
    flat = dict(DEFAULTS)
    for key in flat:
        if key in data:
            flat[key] = data[key]
    return flat


def save(data: dict):
    merged = _settings.load_settings()
    merged.update(data)
    _settings.save_settings(merged)
