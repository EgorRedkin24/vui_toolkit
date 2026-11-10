"""Служебные эндпоинты: состояние сервера, справочники, пресеты, настройки."""

import importlib.util

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from core.audio_io import SAVE_FORMATS
from core.effects import EFFECTS, PRESETS
from core.presets import (load_user_presets, save_user_preset,
                          delete_user_preset)
from core.settings import load_settings, save_settings
from core.word_search import WHISPER_MODELS
from core.tts_elevenlabs import TTS_MODELS

router = APIRouter(prefix="/api", tags=["meta"])


@router.get("/health")
def health():
    return {"status": "ok", "service": "vui-toolkit"}


@router.get("/capabilities")
def capabilities():
    """Какие опциональные функции доступны на этом сервере —
    фронтенд может скрывать/подсвечивать недоступное."""
    def has(module):
        return importlib.util.find_spec(module) is not None

    from core import effects
    from core.audio_io import ffmpeg_available
    return {
        "rubberband": effects.HAS_RUBBERBAND,
        "parselmouth": effects.HAS_PARSELMOUTH,
        "torch": has("torch"),
        "whisper": has("whisper"),
        "pyannote": has("pyannote"),
        "omnivoice": has("omnivoice"),
        "ffmpeg": ffmpeg_available(),
    }


@router.get("/effects")
def list_effects():
    """Реестр эффектов для конструктора пайплайна (без функций)."""
    result = []
    for effect_id, spec in EFFECTS.items():
        params = {}
        for name, p in spec["params"].items():
            params[name] = {"type": p["type"].__name__,
                            "default": p["default"], "label": p["label"]}
        result.append({"id": effect_id, "title": spec["title"],
                       "params": params, "note": spec.get("note")})
    return {"effects": result}


@router.get("/options")
def options():
    """Списки допустимых значений для выпадающих списков фронтенда."""
    return {
        "save_formats": {k: {"ext": v["ext"], "subtypes": v["subtypes"]}
                         for k, v in SAVE_FORMATS.items()},
        "whisper_models": WHISPER_MODELS,
        "tts_models": TTS_MODELS,
        "vad_modes": ["speech", "silence"],
        "table_formats": ["xlsx", "csv"],
    }


@router.get("/presets")
def list_presets():
    """Встроенные и пользовательские (★) пресеты обработки."""
    user = load_user_presets()
    return {
        "builtin": [{"name": k, "steps": v} for k, v in PRESETS.items()],
        "user": [{"name": k, "steps": v} for k, v in user.items()],
    }


class PresetIn(BaseModel):
    name: str
    steps: list


@router.post("/presets")
def create_preset(preset: PresetIn):
    for step in preset.steps:
        if step.get("effect") not in EFFECTS:
            raise HTTPException(
                400, f"Неизвестный эффект: {step.get('effect')}")
    if not save_user_preset(preset.name, preset.steps):
        raise HTTPException(400, "Не удалось сохранить пресет")
    return {"ok": True, "name": preset.name}


@router.delete("/presets/{name}")
def remove_preset(name: str):
    if not delete_user_preset(name):
        raise HTTPException(404, "Пресет не найден")
    return {"ok": True}


@router.get("/settings")
def get_settings():
    """Настройки сервера (режимы по умолчанию, токены и т.п.)."""
    return load_settings()


class SettingsIn(BaseModel):
    data: dict


@router.put("/settings")
def put_settings(body: SettingsIn):
    if not save_settings(body.data):
        raise HTTPException(500, "Не удалось сохранить настройки")
    return {"ok": True}
