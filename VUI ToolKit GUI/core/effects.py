"""
Эффекты и пресеты обработки аудио для VUI ToolKit.

Все эффекты работают с сигналом float32 [-1, 1] (см. core.audio_io).
Каждый эффект — функция f(signal, sr, **params) -> (signal, sr).
Реестр EFFECTS содержит русские названия и спецификации параметров,
по которым GUI строит поля ввода автоматически.
"""

import math
import os
import tempfile

import numpy as np
import scipy.signal
import scipy.io.wavfile

# --- Опциональные зависимости (эффекты с ними помечаются в GUI) ---
try:
    import pyrubberband as pyrb
    HAS_RUBBERBAND = True
except ImportError:
    HAS_RUBBERBAND = False

try:
    import parselmouth
    HAS_PARSELMOUTH = True
except ImportError:
    HAS_PARSELMOUTH = False


# ---------------------------------------------------------------------------
# Эффекты
# ---------------------------------------------------------------------------

def add_silence_start(signal: np.ndarray, sr: int, duration: float = 0.2):
    """Добавляет тишину заданной длительности (секунды) в начало записи."""
    n = int(sr * duration)
    if signal.ndim == 1:
        silence = np.zeros(n, dtype=np.float32)
    else:
        silence = np.zeros((n, signal.shape[1]), dtype=np.float32)
    return np.concatenate([silence, signal]), sr


def add_silence_end(signal: np.ndarray, sr: int, duration: float = 0.2):
    """Добавляет тишину заданной длительности (секунды) в конец записи."""
    n = int(sr * duration)
    if signal.ndim == 1:
        silence = np.zeros(n, dtype=np.float32)
    else:
        silence = np.zeros((n, signal.shape[1]), dtype=np.float32)
    return np.concatenate([signal, silence]), sr


def add_silence(signal: np.ndarray, sr: int, duration: float = 0.2):
    """Добавляет одинаковую тишину в начало и конец (удобно для пресетов)."""
    signal, sr = add_silence_start(signal, sr, duration)
    return add_silence_end(signal, sr, duration)


def add_random_noise(signal: np.ndarray, sr: int, factor: float = 0.01):
    """Добавляет гауссов шум с амплитудой factor от максимума сигнала."""
    max_val = np.max(np.abs(signal)) if signal.size else 0
    if max_val == 0:
        return signal, sr
    noise = np.random.normal(0, max_val * factor, size=signal.shape)
    return (signal + noise).astype(np.float32), sr


def add_reverberation(signal: np.ndarray, sr: int, time: float = 0.2):
    """Простая реверберация: три задержанные копии с затуханием."""
    n = len(signal)
    out = signal.copy().astype(np.float64)
    for delay, amp in [(1, 0.1), (2, 0.05), (3, 0.025)]:
        shift = int(time * sr * delay)
        if 0 < shift < n:
            if signal.ndim == 1:
                out[shift:] += signal[:n - shift] * amp
            else:
                out[shift:, :] += signal[:n - shift, :] * amp
    return out.astype(np.float32), sr


def imitate_packet_loss(signal: np.ndarray, sr: int, window_length: float = 0.2):
    """Имитирует потерю пакетов: заглушает 5 случайных окон."""
    out = signal.copy()
    win = int(sr * window_length)
    if win <= 0:
        return out, sr
    num_windows = len(out) // win
    if num_windows == 0:
        return out, sr
    windows = np.random.randint(num_windows, size=min(5, num_windows))
    for i in windows:
        out[i * win:(i + 1) * win] *= 0.1
    return out, sr


def imitate_clipping(signal: np.ndarray, sr: int, threshold: float = 0.5):
    """Имитирует клиппинг: обрезает амплитуду выше threshold от максимума."""
    out = signal.copy()
    max_val = np.max(np.abs(out)) if out.size else 0
    if max_val == 0:
        return out, sr
    limit = max_val * threshold
    return np.clip(out, -limit, limit), sr


def change_speed(signal: np.ndarray, sr: int, speed_factor: float = 1.0):
    """
    Изменяет скорость воспроизведения.
    С rubberband — без изменения высоты тона; иначе — ресэмплинг
    (меняется и высота, это отражено в логе GUI).
    """
    if speed_factor <= 0:
        raise ValueError("speed_factor должен быть > 0")
    if HAS_RUBBERBAND:
        if signal.ndim == 1:
            stretched = pyrb.time_stretch(signal, sr, speed_factor)
        else:
            channels = [pyrb.time_stretch(signal[:, c], sr, speed_factor)
                        for c in range(signal.shape[1])]
            stretched = np.stack(channels, axis=1)
        return stretched.astype(np.float32), sr
    # Фолбэк: ресэмплинг (меняет и высоту тона)
    new_len = max(1, int(len(signal) / speed_factor))
    return scipy.signal.resample(signal, new_len, axis=0).astype(np.float32), sr


def change_pitch(signal: np.ndarray, sr: int, factor: float = 1.0):
    """Изменяет высоту тона (ЧОТ) через Praat/Parselmouth."""
    if not HAS_PARSELMOUTH:
        raise RuntimeError(
            "Для изменения высоты тона нужен пакет praat-parselmouth "
            "(pip install praat-parselmouth)"
        )
    from core.audio_io import save_audio

    tmp_in = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp_in.close()
    try:
        save_audio(tmp_in.name, signal, sr, "WAV", "PCM_16")
        sound_obj = parselmouth.Sound(tmp_in.name)
        initial_pitch = sound_obj.to_pitch()
        pitch_tier = parselmouth.praat.call(
            "Create PitchTier", "pitch_tier", 0.0, sound_obj.get_end_time())
        time_step = initial_pitch.get_time_step()
        start_time = initial_pitch.get_start_time()
        end_time = start_time + initial_pitch.get_total_duration()
        t = start_time
        while t <= end_time:
            value = initial_pitch.get_value_at_time(t)
            if not np.isnan(value):
                parselmouth.praat.call(pitch_tier, "Add point", t, value * factor)
            t += time_step
        manip = parselmouth.praat.call(sound_obj, "To Manipulation", 0.01, 75, 300)
        parselmouth.praat.call([manip, pitch_tier], "Replace pitch tier")
        result = parselmouth.praat.call(manip, "Get resynthesis (overlap-add)")
        new_signal = result.values.T.astype(np.float32)
        if new_signal.ndim == 2 and new_signal.shape[1] == 1:
            new_signal = new_signal[:, 0]
        return new_signal, int(result.sampling_frequency)
    finally:
        os.unlink(tmp_in.name)


def high_pass_filter(signal: np.ndarray, sr: int, frequency: float = 500, order: int = 4):
    """Фильтр верхних частот (Баттерворт)."""
    sos = scipy.signal.butter(order, frequency, "hp", fs=sr, output="sos")
    return scipy.signal.sosfilt(sos, signal, axis=0).astype(np.float32), sr


def low_pass_filter(signal: np.ndarray, sr: int, frequency: float = 2000, order: int = 4):
    """Фильтр нижних частот (Баттерворт)."""
    sos = scipy.signal.butter(order, frequency, "lp", fs=sr, output="sos")
    return scipy.signal.sosfilt(sos, signal, axis=0).astype(np.float32), sr


def trim_silence(signal: np.ndarray, sr: int, silence_fraction: float = 0.05,
                 chunk_size: int = 10, padding_ms: int = 150):
    """
    Обрезает тишину в начале и конце записи.
    silence_fraction — доля от максимальной амплитуды, ниже которой тишина;
    chunk_size — минимальная длительность тишины, мс;
    padding_ms — отступ от границ речи, мс.
    """
    if signal.size == 0:
        return signal, sr
    mono = np.abs(signal if signal.ndim == 1 else signal.mean(axis=1))
    max_val = mono.max()
    if max_val == 0:
        return signal, sr
    threshold = max_val * silence_fraction

    chunk = max(1, int(sr * chunk_size / 1000))
    n_chunks = len(mono) // chunk
    if n_chunks == 0:
        return signal, sr
    loud = np.array([mono[i * chunk:(i + 1) * chunk].max() > threshold
                     for i in range(n_chunks)])
    if not loud.any():
        return signal[:0], sr
    first = int(np.argmax(loud)) * chunk
    last = (n_chunks - int(np.argmax(loud[::-1]))) * chunk
    pad = int(sr * padding_ms / 1000)
    start = max(0, first - pad)
    end = min(len(signal), last + pad)
    return signal[start:end], sr


def resample(signal: np.ndarray, sr: int, new_sr: int = 16000):
    """Изменяет частоту дискретизации (качественный polyphase-ресэмплинг)."""
    new_sr = int(new_sr)
    if new_sr == sr:
        return signal, sr
    g = math.gcd(sr, new_sr)
    out = scipy.signal.resample_poly(signal, new_sr // g, sr // g, axis=0)
    return out.astype(np.float32), new_sr


def stereo_to_mono(signal: np.ndarray, sr: int):
    """Сводит многоканальный сигнал в моно (усреднение каналов)."""
    if signal.ndim == 2 and signal.shape[1] > 1:
        return signal.mean(axis=1).astype(np.float32), sr
    return signal, sr


# ---------------------------------------------------------------------------
# Реестр эффектов (для конструктора пайплайна в GUI)
# ---------------------------------------------------------------------------

EFFECTS = {
    "add_silence_start": {
        "title": "Тишина в начале",
        "func": add_silence_start,
        "params": {
            "duration": {"type": float, "default": 0.2, "label": "Длительность, с"},
        },
    },
    "add_silence_end": {
        "title": "Тишина в конце",
        "func": add_silence_end,
        "params": {
            "duration": {"type": float, "default": 0.2, "label": "Длительность, с"},
        },
    },
    "add_silence": {
        "title": "Тишина в начале и конце (одинаковая)",
        "func": add_silence,
        "params": {
            "duration": {"type": float, "default": 0.2, "label": "Длительность, с"},
        },
    },
    "add_random_noise": {
        "title": "Случайный шум",
        "func": add_random_noise,
        "params": {
            "factor": {"type": float, "default": 0.01, "label": "Уровень (доля от макс.)"},
        },
    },
    "add_reverberation": {
        "title": "Реверберация",
        "func": add_reverberation,
        "params": {
            "time": {"type": float, "default": 0.2, "label": "Время задержки, с"},
        },
    },
    "imitate_packet_loss": {
        "title": "Имитация потери пакетов",
        "func": imitate_packet_loss,
        "params": {
            "window_length": {"type": float, "default": 0.2, "label": "Длина окна, с"},
        },
    },
    "imitate_clipping": {
        "title": "Имитация клиппинга",
        "func": imitate_clipping,
        "params": {
            "threshold": {"type": float, "default": 0.5, "label": "Порог (доля от макс.)"},
        },
    },
    "change_speed": {
        "title": "Изменение скорости",
        "func": change_speed,
        "params": {
            "speed_factor": {"type": float, "default": 1.0, "label": "Коэффициент"},
        },
        "note": "без rubberband меняется и высота тона",
    },
    "change_pitch": {
        "title": "Изменение высоты тона",
        "func": change_pitch,
        "params": {
            "factor": {"type": float, "default": 1.0, "label": "Коэффициент"},
        },
        "note": "требуется praat-parselmouth",
    },
    "high_pass_filter": {
        "title": "Фильтр верхних частот",
        "func": high_pass_filter,
        "params": {
            "frequency": {"type": float, "default": 500, "label": "Частота среза, Гц"},
            "order": {"type": int, "default": 4, "label": "Порядок фильтра"},
        },
    },
    "low_pass_filter": {
        "title": "Фильтр нижних частот",
        "func": low_pass_filter,
        "params": {
            "frequency": {"type": float, "default": 2000, "label": "Частота среза, Гц"},
            "order": {"type": int, "default": 4, "label": "Порядок фильтра"},
        },
    },
    "trim_silence": {
        "title": "Обрезка тишины по краям",
        "func": trim_silence,
        "params": {
            "silence_fraction": {"type": float, "default": 0.05, "label": "Порог (доля от макс.)"},
            "chunk_size": {"type": int, "default": 10, "label": "Мин. тишина, мс"},
            "padding_ms": {"type": int, "default": 150, "label": "Отступ, мс"},
        },
    },
    "resample": {
        "title": "Изменение частоты дискретизации",
        "func": resample,
        "params": {
            "new_sr": {"type": int, "default": 16000, "label": "Новая частота, Гц"},
        },
    },
    "stereo_to_mono": {
        "title": "Сведение в моно",
        "func": stereo_to_mono,
        "params": {},
    },
}

# Готовые пресеты: название -> список шагов пайплайна
PRESETS = {
    "bad_micro": [
        {"effect": "add_random_noise", "params": {"factor": 0.01}},
        {"effect": "imitate_clipping", "params": {"threshold": 0.7}},
        {"effect": "low_pass_filter", "params": {"frequency": 2500, "order": 4}},
        {"effect": "high_pass_filter", "params": {"frequency": 500, "order": 4}},
    ],
    "ambience": [
        {"effect": "add_reverberation", "params": {"time": 0.2}},
        {"effect": "imitate_packet_loss", "params": {"window_length": 0.2}},
        {"effect": "add_random_noise", "params": {"factor": 0.01}},
    ],
    "bad_connection": [
        {"effect": "imitate_packet_loss", "params": {"window_length": 0.2}},
        {"effect": "imitate_clipping", "params": {"threshold": 0.7}},
        {"effect": "low_pass_filter", "params": {"frequency": 2500, "order": 4}},
        {"effect": "high_pass_filter", "params": {"frequency": 500, "order": 4}},
        {"effect": "add_random_noise", "params": {"factor": 0.01}},
    ],
    "voice_changer_higher": [
        {"effect": "change_speed", "params": {"speed_factor": 1.02}},
        {"effect": "add_random_noise", "params": {"factor": 0.01}},
        {"effect": "high_pass_filter", "params": {"frequency": 500, "order": 4}},
        {"effect": "change_pitch", "params": {"factor": 1.05}},
    ],
    "voice_changer_lower": [
        {"effect": "change_speed", "params": {"speed_factor": 0.95}},
        {"effect": "add_random_noise", "params": {"factor": 0.01}},
        {"effect": "low_pass_filter", "params": {"frequency": 3000, "order": 4}},
        {"effect": "change_pitch", "params": {"factor": 0.95}},
    ],
    "stereo_to_mono": [
        {"effect": "stereo_to_mono", "params": {}},
    ],
}


def apply_pipeline(signal: np.ndarray, sr: int, steps: list, log=None):
    """
    Последовательно применяет шаги пайплайна.
    steps — список словарей {"effect": <id>, "params": {...}}.
    Возвращает (signal, sr).
    """
    for i, step in enumerate(steps, 1):
        effect_id = step["effect"]
        if effect_id not in EFFECTS:
            raise ValueError(f"Неизвестный эффект: {effect_id}")
        spec = EFFECTS[effect_id]
        if log:
            params_str = ", ".join(f"{k}={v}" for k, v in step["params"].items())
            log(f"  Шаг {i}: {spec['title']} ({params_str})")
        signal, sr = spec["func"](signal, sr, **step["params"])
    return signal, sr
