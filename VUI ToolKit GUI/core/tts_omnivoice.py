"""
Локальный синтез речи через OmniVoice (k2-fsa/OmniVoice) для VUI ToolKit.

OmniVoice — модель клонирования голоса: вместо voice_id используется
ЭТАЛОННАЯ АУДИОЗАПИСЬ голоса (ref_audio). Два режима:
    - озвучка одной фразы (один эталонный файл);
    - озвучка фраз из таблицы (столбец 'text'; необязательный столбец
      'voice' — путь к эталонной записи для конкретной строки; точное имя
      файла строки — столбец 'filename'; либо filename_template с {n}).
"""

import os

import numpy as np
import soundfile as sf

from core.tts_elevenlabs import (FILENAME_COLUMNS, resolve_out_path,
                                 sanitize_filename)

_MODEL = None
SAMPLE_RATE = 24000  # OmniVoice выдаёт 24 кГц

# расширение -> формат для core.audio_io.save_audio
_EXT_TO_FMT = {".wav": "WAV", ".flac": "FLAC", ".ogg": "OGG", ".mp3": "MP3"}
_FMT_TO_EXT = {"wav": ".wav", "flac": ".flac", "ogg": ".ogg", "mp3": ".mp3"}


def resolve_audio_format(audio_format) -> tuple:
    """
    Параметры формата синтеза -> (расширение, частота дискретизации).

    audio_format: dict {container: 'wav'|'mp3'|'ogg'|'flac', sample_rate}.
    None -> WAV 24 кГц (как раньше).
    """
    if not audio_format:
        return ".wav", SAMPLE_RATE
    container = str(audio_format.get("container") or "wav").lower()
    ext = _FMT_TO_EXT.get(container, ".wav")
    sr = int(audio_format.get("sample_rate") or SAMPLE_RATE)
    return ext, sr


def _get_model():
    """Ленивая загрузка OmniVoice (один раз за сессию)."""
    global _MODEL
    if _MODEL is None:
        import torch
        from omnivoice import OmniVoice
        device = "cuda:0" if torch.cuda.is_available() else "cpu"
        dtype = torch.float16 if device.startswith("cuda") else torch.float32
        _MODEL = OmniVoice.from_pretrained(
            "k2-fsa/OmniVoice", device_map=device, dtype=dtype)
    return _MODEL


def synthesize(text: str, ref_audio: str, output_path: str, log=None,
               sample_rate: int = None) -> bool:
    """
    Озвучивает текст голосом из эталонной записи ref_audio.
    Сохраняет результат в output_path: формат берётся из расширения пути
    (через core.audio_io.save_audio — WAV/FLAC/OGG/MP3), частота
    дискретизации — sample_rate (по умолчанию 24 кГц, модель выдаёт 24 кГц,
    при необходимости делается ресемплинг).
    """
    import torch
    model = _get_model()
    try:
        audio = model.generate(text=text, ref_audio=ref_audio)
        audio_data = audio[0]
        if torch.is_tensor(audio_data):
            audio_data = audio_data.detach().cpu().numpy()
        if audio_data.ndim > 1 and audio_data.shape[0] == 1:
            audio_data = audio_data.squeeze(0)
        if audio_data.dtype != np.float32:
            audio_data = audio_data.astype(np.float32)

        target_sr = int(sample_rate or SAMPLE_RATE)
        if target_sr != SAMPLE_RATE:
            from scipy.signal import resample_poly
            audio_data = resample_poly(audio_data, target_sr,
                                       SAMPLE_RATE).astype(np.float32)

        os.makedirs(os.path.dirname(os.path.abspath(output_path)),
                    exist_ok=True)
        ext = os.path.splitext(output_path)[1].lower()
        fmt = _EXT_TO_FMT.get(ext, "WAV")
        from core.audio_io import save_audio
        save_audio(output_path, audio_data, target_sr, fmt, "PCM_16")
        return True
    except Exception as e:
        if log:
            log(f"  ОШИБКА синтеза: {e}")
        return False


def synthesize_single(text: str, ref_audio: str, output_dir: str,
                      log=None, audio_format: dict = None,
                      output_name: str = None) -> str:
    """Озвучка одной фразы. Возвращает путь к файлу или None."""
    ext, sr = resolve_audio_format(audio_format)
    stem = sanitize_filename(output_name) if output_name \
        else "omnivoice_phrase"
    out_path = os.path.join(output_dir, f"{stem}{ext}")
    n = 1
    while os.path.exists(out_path):
        out_path = os.path.join(output_dir,
                                f"{stem}_{n:02d}{ext}")
        n += 1
    if log:
        log(f"Генерация фразы (OmniVoice): "
            f"{text[:60]}{'...' if len(text) > 60 else ''}")
    ok = synthesize(text, ref_audio, out_path, log, sample_rate=sr)
    if log and ok:
        log(f"  -> {os.path.basename(out_path)}")
    return out_path if ok else None


def synthesize_table(df, default_ref_audio: str, output_dir: str,
                     log=None, progress=None, cancel_event=None,
                     filename_template: str = None,
                     audio_format: dict = None) -> list:
    """
    Озвучка фраз из таблицы (pandas DataFrame).
    Обязательный столбец: 'text'. Необязательные: 'voice' —
    путь к эталонной записи голоса для строки (иначе default_ref_audio)
    и 'filename' (точное имя файла строки). Если filename в строке не задан,
    имя берётся из filename_template (токен {n} — номер строки), иначе —
    omnivoice_NNN.<расширение по audio_format>.
    progress(i, total) — колбэк прогресса; cancel_event — threading.Event.
    """
    if "text" not in df.columns:
        raise ValueError("Таблица должна содержать столбец 'text'")

    ext, sr = resolve_audio_format(audio_format)

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
        ref_audio = default_ref_audio
        if has_voice_col:
            row_voice = df[voice_col].iloc[idx - 1]
            if isinstance(row_voice, str) and row_voice.strip():
                ref_audio = row_voice.strip()
        if not ref_audio or not os.path.isfile(ref_audio):
            if log:
                log(f"Строка {idx}: эталонная запись не найдена "
                    f"({ref_audio or 'не задана'}), пропуск")
            continue

        row_filename = (df[filename_col].iloc[idx - 1]
                        if filename_col else None)
        out_path = resolve_out_path(output_dir, idx, row_filename,
                                    filename_template, ext, "omnivoice",
                                    log=log)
        if log:
            log(f"Генерация {idx}/{total}: {text[:50]}"
                f"{'...' if len(text) > 50 else ''}")
        ok = synthesize(text.strip(), ref_audio, out_path, log,
                        sample_rate=sr)
        if ok:
            created.append(out_path)
            if log:
                log(f"  -> {os.path.basename(out_path)}")
        if progress:
            progress(idx, total)
    return created
