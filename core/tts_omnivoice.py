"""
Локальный синтез речи через OmniVoice (k2-fsa/OmniVoice) для VUI ToolKit.

OmniVoice — модель клонирования голоса: вместо voice_id используется
ЭТАЛОННАЯ АУДИОЗАПИСЬ голоса (ref_audio). Два режима:
    - озвучка одной фразы (один эталонный файл);
    - озвучка фраз из таблицы (столбец 'text'; необязательный столбец
      'voice' — путь к эталонной записи для конкретной строки).
"""

import os

import numpy as np
import soundfile as sf

_MODEL = None
SAMPLE_RATE = 24000  # OmniVoice выдаёт 24 кГц


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


def synthesize(text: str, ref_audio: str, output_path: str, log=None) -> bool:
    """
    Озвучивает текст голосом из эталонной записи ref_audio.
    Сохраняет WAV 24 кГц PCM_16 в output_path.
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

        os.makedirs(os.path.dirname(os.path.abspath(output_path)),
                    exist_ok=True)
        sf.write(output_path, audio_data, SAMPLE_RATE, subtype="PCM_16")
        return True
    except Exception as e:
        if log:
            log(f"  ОШИБКА синтеза: {e}")
        return False


def synthesize_single(text: str, ref_audio: str, output_dir: str,
                      log=None) -> str:
    """Озвучка одной фразы. Возвращает путь к файлу или None."""
    out_path = os.path.join(output_dir, "omnivoice_phrase.wav")
    n = 1
    while os.path.exists(out_path):
        out_path = os.path.join(output_dir, f"omnivoice_phrase_{n:02d}.wav")
        n += 1
    if log:
        log(f"Генерация фразы (OmniVoice): "
            f"{text[:60]}{'...' if len(text) > 60 else ''}")
    ok = synthesize(text, ref_audio, out_path, log)
    if log and ok:
        log(f"  -> {os.path.basename(out_path)}")
    return out_path if ok else None


def synthesize_table(df, default_ref_audio: str, output_dir: str,
                     log=None, progress=None, cancel_event=None) -> list:
    """
    Озвучка фраз из таблицы (pandas DataFrame).
    Обязательный столбец: 'text'. Необязательный: 'voice' —
    путь к эталонной записи голоса для строки (иначе default_ref_audio).
    progress(i, total) — колбэк прогресса; cancel_event — threading.Event.
    """
    if "text" not in df.columns:
        raise ValueError("Таблица должна содержать столбец 'text'")

    has_voice_col = "voice" in df.columns or "voice_id" in df.columns
    voice_col = "voice" if "voice" in df.columns else "voice_id"

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

        out_path = os.path.join(output_dir, f"omnivoice_{idx:03d}.wav")
        if log:
            log(f"Генерация {idx}/{total}: {text[:50]}"
                f"{'...' if len(text) > 50 else ''}")
        ok = synthesize(text.strip(), ref_audio, out_path, log)
        if ok:
            created.append(out_path)
            if log:
                log(f"  -> {os.path.basename(out_path)}")
        if progress:
            progress(idx, total)
    return created
