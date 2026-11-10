"""
Синтез речи через ElevenLabs API для VUI ToolKit.

Два режима:
    - озвучка одной фразы;
    - озвучка фраз из таблицы (столбец 'text'; если нужен разный голос
      для строк — столбец 'voice' с voice_id; точное имя файла строки —
      столбец 'filename'; либо filename_template с токеном {n}).
"""

import os
import re
import time

import requests

TTS_MODELS = ["eleven_multilingual_v2", "eleven_v3", "eleven_turbo_v2_5"]
DEFAULT_MODEL = "eleven_multilingual_v2"
OUTPUT_FORMAT = "mp3_44100_128"
VOICE_SETTINGS = {"stability": 0.6, "similarity_boost": 0.8}
MAX_RETRIES = 5

# Доступные ЧОТ для PCM (WAV) у ElevenLabs
PCM_SAMPLE_RATES = (16000, 22050, 24000, 44100, 48000)
# Доступные битрейты для MP3/OGG Vorbis
BITRATES = (32, 64, 96, 128, 192)

# Столбцы таблицы, из которых берётся имя конкретного файла строки
# (в порядке приоритета; распознаются и русские названия).
FILENAME_COLUMNS = ("filename", "file_name", "имя файла", "название файла")

_ILLEGAL_NAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def sanitize_filename(name: str) -> str:
    """Убирает из имени файла недопустимые символы и опасные края."""
    name = _ILLEGAL_NAME_CHARS.sub("_", str(name)).strip(" .")
    return name[:120]


def resolve_out_path(output_dir: str, idx: int, row_filename,
                     filename_template: str, ext: str, default_stem: str,
                     log=None) -> str:
    """
    Определяет путь выходного файла для строки таблицы idx:
      1) точное имя из столбца filename (если задано в строке);
      2) filename_template с подстановкой {n} (n — номер строки,
         поддерживаются спецификаторы вида {n:03d});
      3) имя по умолчанию default_stem + zero-padded номер.
    Существующие файлы не затираются — добавляется суффикс _1, _2...
    """
    base = None
    if isinstance(row_filename, str) and row_filename.strip():
        base = sanitize_filename(row_filename)
    elif filename_template:
        try:
            base = sanitize_filename(filename_template.format(n=idx))
        except Exception as e:
            if log:
                log(f"  Шаблон имени некорректен ({e}) — "
                    f"используется имя по умолчанию")
    if not base:
        base = f"{default_stem}_{idx:03d}"
    if not base.lower().endswith(ext):
        base += ext
    out_path = os.path.join(output_dir, base)
    stem, suffix = os.path.splitext(out_path)
    n = 1
    while os.path.exists(out_path):
        out_path = f"{stem}_{n}{suffix}"
        n += 1
    return out_path


def resolve_audio_format(audio_format) -> tuple:
    """
    Параметры формата синтеза -> (output_format для API, расширение, MIME).

    audio_format: dict {container: 'mp3'|'wav'|'ogg', sample_rate, bitrate}.
    None -> формат по умолчанию (mp3_44100_128).
    """
    if not audio_format:
        return OUTPUT_FORMAT, ".mp3", "audio/mpeg"
    container = str(audio_format.get("container") or "mp3").lower()
    bitrate = int(audio_format.get("bitrate") or 128)
    sr = int(audio_format.get("sample_rate") or 24000)

    if container == "wav":
        if sr not in PCM_SAMPLE_RATES:
            sr = 24000
        return f"pcm_{sr}", ".wav", "audio/pcm"
    if container == "ogg":
        if bitrate not in BITRATES:
            bitrate = 128
        return f"ogg_vorbis_{bitrate}", ".ogg", "audio/ogg"
    # mp3
    if bitrate <= 32:
        return "mp3_22050_32", ".mp3", "audio/mpeg"
    if bitrate <= 64:
        return "mp3_22050_64", ".mp3", "audio/mpeg"
    if bitrate >= 192:
        return "mp3_44100_192", ".mp3", "audio/mpeg"
    return "mp3_44100_128", ".mp3", "audio/mpeg"


def synthesize(text: str, voice_id: str, api_key: str, output_path: str,
               model_id: str = DEFAULT_MODEL, log=None,
               output_format: str = None) -> bool:
    """
    Озвучивает текст голосом voice_id и сохраняет в output_path.
    output_format — формат API ElevenLabs (mp3_44100_128, pcm_24000,
    ogg_vorbis_128 и т.п.); None — MP3 44,1 кГц 128 кбит/с.
    Делает до MAX_RETRIES попыток с экспоненциальной паузой.
    """
    output_format = output_format or OUTPUT_FORMAT
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    headers = {
        "Accept": "audio/pcm" if output_format.startswith("pcm")
        else "audio/ogg" if output_format.startswith("ogg")
        else "audio/mpeg",
        "Content-Type": "application/json",
        "xi-api-key": api_key,
    }
    data = {
        "text": text,
        "model_id": model_id,
        "voice_settings": VOICE_SETTINGS,
    }
    # output_format передаётся Query-параметром (в body API его игнорирует)
    params = {"output_format": output_format}

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.post(url, json=data, headers=headers,
                                     params=params, timeout=60)
            content_type = response.headers.get("Content-Type", "")
            if response.status_code == 200 and "audio" in content_type:
                audio_data = response.content
                if len(audio_data) < 500:
                    if log:
                        log(f"  Подозрительно маленький ответ "
                            f"({len(audio_data)} байт)")
                    return False
                os.makedirs(os.path.dirname(os.path.abspath(output_path)),
                            exist_ok=True)
                if output_format.startswith("pcm"):
                    # сырой PCM s16le без заголовка -> оборачиваем в WAV
                    import numpy as np
                    import soundfile as sf
                    sr = int(output_format.split("_")[1])
                    pcm = np.frombuffer(audio_data, dtype="<i2")
                    sf.write(output_path, pcm, sr, subtype="PCM_16")
                else:
                    with open(output_path, "wb") as f:
                        f.write(audio_data)
                return True
            # ошибка API
            try:
                error_msg = response.json().get("detail", response.text)
            except Exception:
                error_msg = response.text
            if log:
                log(f"  Попытка {attempt}: статус {response.status_code}, "
                    f"{error_msg}")
            if attempt < MAX_RETRIES:
                time.sleep(2 ** attempt)
        except Exception as e:
            if log:
                log(f"  Попытка {attempt}: {e}")
            if attempt < MAX_RETRIES:
                time.sleep(2 ** attempt)
    return False


def synthesize_single(text: str, voice_id: str, api_key: str,
                      output_dir: str, model_id: str = DEFAULT_MODEL,
                      log=None, audio_format: dict = None,
                      output_name: str = None) -> str:
    """Озвучка одной фразы. Возвращает путь к файлу или None."""
    _, ext, _ = resolve_audio_format(audio_format)
    stem = sanitize_filename(output_name) if output_name else "tts_phrase"
    out_path = os.path.join(output_dir, f"{stem}{ext}")
    # не затираем существующие файлы
    n = 1
    while os.path.exists(out_path):
        out_path = os.path.join(output_dir, f"{stem}_{n:02d}{ext}")
        n += 1
    if log:
        log(f"Генерация фразы: {text[:60]}{'...' if len(text) > 60 else ''}")
    api_format, _, _ = resolve_audio_format(audio_format)
    ok = synthesize(text, voice_id, api_key, out_path, model_id, log,
                    output_format=api_format)
    if log:
        log(f"  -> {os.path.basename(out_path)}" if ok else "  ОШИБКА генерации")
    return out_path if ok else None


def synthesize_table(df, default_voice_id: str, api_key: str,
                     output_dir: str, model_id: str = DEFAULT_MODEL,
                     log=None, progress=None, cancel_event=None,
                     filename_template: str = None,
                     audio_format: dict = None) -> list:
    """
    Озвучка фраз из таблицы (pandas DataFrame).
    Обязательный столбец: 'text'. Необязательные: 'voice' (voice_id для строки)
    и 'filename' (точное имя файла строки). Если filename в строке не задан,
    имя берётся из filename_template (токен {n} — номер строки), иначе —
    tts_NNN.<расширение по audio_format>.
    progress(i, total) — колбэк прогресса; cancel_event — threading.Event.
    Возвращает список путей к созданным файлам.
    """
    if "text" not in df.columns:
        raise ValueError("Таблица должна содержать столбец 'text'")

    api_format, ext, _ = resolve_audio_format(audio_format)

    has_voice_col = "voice" in df.columns or "voice_id" in df.columns
    voice_col = "voice" if "voice" in df.columns else "voice_id"
    filename_col = next((c for c in FILENAME_COLUMNS if c in df.columns),
                        None)

    created = []
    texts = df["text"].tolist()
    total = len(texts)
    for idx, text in enumerate(texts, 1):
        if cancel_event is not None and cancel_event.is_set():
            if log:
                log("Задача прервана пользователем.")
            break
        if progress:
            progress(idx - 1, total)
        if not isinstance(text, str) or not text.strip():
            if log:
                log(f"Строка {idx}: пустой текст, пропуск")
            continue
        voice_id = default_voice_id
        if has_voice_col:
            row_voice = df[voice_col].iloc[idx - 1]
            if isinstance(row_voice, str) and row_voice.strip():
                voice_id = row_voice.strip()
        if not voice_id:
            if log:
                log(f"Строка {idx}: voice id не задан, пропуск")
            continue

        row_filename = (df[filename_col].iloc[idx - 1]
                        if filename_col else None)
        out_path = resolve_out_path(output_dir, idx, row_filename,
                                    filename_template, ext, "tts", log=log)
        if log:
            log(f"Генерация {idx}/{total}: {text[:50]}"
                f"{'...' if len(text) > 50 else ''} (voice: {voice_id[:8]}...)")
        ok = synthesize(text.strip(), voice_id, api_key, out_path,
                        model_id, log, output_format=api_format)
        if ok:
            created.append(out_path)
            if log:
                log(f"  -> {os.path.basename(out_path)}")
        elif log:
            log(f"  ОШИБКА генерации строки {idx}")
        if progress:
            progress(idx, total)
    return created


def load_table(path: str):
    """Читает таблицу фраз (Excel или CSV) в pandas DataFrame."""
    import pandas as pd
    if path.lower().endswith(".csv"):
        return pd.read_csv(path)
    return pd.read_excel(path)
