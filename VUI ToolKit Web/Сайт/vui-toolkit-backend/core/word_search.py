"""
Поиск заданных слов и словосочетаний в аудиозаписях и создание файлов
разметки (.seg) для VUI ToolKit / Wave Assistant.

Пайплайн:
    1) чтение аудиофайла и его параметров;
    2) распознавание речи через Whisper (с метками времени на слова);
    3) поиск фрагментов: точное совпадение или неточное (по проценту
       сходства); словосочетания ищутся как склейка соседних токенов;
       количество фрагментов задаётся параметром max_fragments;
    4) запись .seg-файла РЯДОМ С ИСХОДНЫМ АУДИО (UTF-8 с BOM),
       на каждый фрагмент — две метки: начало (со словом) и конец
       (пустая). ПЕРВОЕ ЧИСЛО метки — НОМЕР БАЙТА в аудиопотоке
       (не отсчёта): byte = time * SAMPLING_FREQ * BYTE_PER_SAMPLE * N_CHANNEL.
"""

import difflib
import os
from string import punctuation

WHISPER_MODELS = ["tiny", "base", "small", "medium"]
DEFAULT_MODEL = "small"
DEFAULT_LANGUAGE = "ru"

_MODEL = None
_MODEL_NAME = None


def _get_model(model_name: str):
    """Ленивая загрузка модели Whisper (один раз на выбранный размер)."""
    global _MODEL, _MODEL_NAME
    if _MODEL is None or _MODEL_NAME != model_name:
        import whisper
        _MODEL = whisper.load_model(model_name)
        _MODEL_NAME = model_name
    return _MODEL


_PUNCTUATION_SET = set(punctuation + " " + "«»—–…")


def normalize_word(word: str) -> str:
    """Убирает пунктуацию и пробелы, приводит к нижнему регистру.
    Словосочетание «добрый день» превращается в «добрыйдень» —
    так же склеиваются и токены Whisper при сравнении."""
    return "".join(ch for ch in word if ch not in _PUNCTUATION_SET).lower()


def _get_audio_params(filepath: str) -> dict:
    """Параметры аудио для пересчёта времени в байты."""
    import soundfile as sf
    info = sf.info(filepath)
    subtype = info.subtype or ""
    if "FLOAT" in subtype:
        bps = 8 if "64" in subtype else 4
    elif "PCM_16" in subtype:
        bps = 2
    elif "PCM_24" in subtype:
        bps = 3
    elif "PCM_32" in subtype:
        bps = 4
    else:
        bps = 2
    return {
        "SAMPLING_FREQ": info.samplerate,
        "BYTE_PER_SAMPLE": bps,
        "CODE": 0,
        "N_CHANNEL": info.channels,
    }


def _time_to_byte(time_sec: float, params: dict) -> int:
    """Время (с) -> номер БАЙТА аудиопотока (учитывает разрядность и каналы)."""
    return int(time_sec * params["SAMPLING_FREQ"]
               * params["BYTE_PER_SAMPLE"] * params["N_CHANNEL"])


def _similarity(a: str, b: str) -> float:
    """Сходство строк от 0 до 1 (SequenceMatcher)."""
    return difflib.SequenceMatcher(None, a, b).ratio()


def _find_fragments(tokens: list, targets: list, fuzzy: bool,
                    similarity: float, params: dict) -> list:
    """
    Ищет целевые слова/словосочетания в списке токенов
    (cleaned, start, end). Возвращает список фрагментов.
    """
    fragments = []
    for target in targets:
        tlen = len(target)
        # верхняя граница окна склейки: для fuzzy чуть шире
        max_tok = tlen if not fuzzy else max(tlen, int(tlen * 1.3))
        for i in range(len(tokens)):
            acc = ""
            for j in range(i, min(i + max_tok, len(tokens))):
                acc += tokens[j][0]
                if fuzzy:
                    if len(acc) > tlen * 1.3 + 1:
                        break
                    if abs(len(acc) - tlen) <= max(2, tlen // 3) and \
                            _similarity(acc, target) >= similarity:
                        fragments.append({
                            "word": target,
                            "matched": acc,
                            "start": tokens[i][1],
                            "end": tokens[j][2],
                            "byte_start": _time_to_byte(tokens[i][1], params),
                            "byte_end": _time_to_byte(tokens[j][2], params),
                        })
                        break
                else:
                    if len(acc) > tlen or not target.startswith(acc):
                        break
                    if acc == target:
                        fragments.append({
                            "word": target,
                            "matched": acc,
                            "start": tokens[i][1],
                            "end": tokens[j][2],
                            "byte_start": _time_to_byte(tokens[i][1], params),
                            "byte_end": _time_to_byte(tokens[j][2], params),
                        })
                        break
    fragments.sort(key=lambda f: f["start"])
    return fragments


def find_words_in_audio(audio_path: str, target_words: list,
                        max_fragments: int = 1,
                        model_name: str = DEFAULT_MODEL,
                        language: str = DEFAULT_LANGUAGE,
                        fuzzy: bool = False,
                        similarity: float = 0.8) -> tuple:
    """
    Ищет заданные слова/словосочетания в одной аудиозаписи и создаёт
    .seg рядом с ней.

    fuzzy       — разрешить неточное совпадение;
    similarity  — порог сходства 0..1 (используется при fuzzy=True).

    Возвращает (путь_к_seg, список_фрагментов).
    Фрагмент: {word, matched, start, end, byte_start, byte_end}.
    """
    if not target_words:
        raise ValueError("Список искомых слов пуст")
    if max_fragments < 1:
        raise ValueError("max_fragments должен быть >= 1")

    # 1) чтение параметров аудио
    params = _get_audio_params(audio_path)

    # 2) распознавание речи с метками времени
    model = _get_model(model_name)
    result = model.transcribe(audio_path, word_timestamps=True,
                              language=language or None)
    words = []
    for segment in result["segments"]:
        if "words" in segment:
            words.extend(segment["words"])
        else:
            words.append({"word": segment["text"].strip(),
                          "start": segment["start"], "end": segment["end"]})

    # 3) поиск фрагментов (словосочетания находятся склейкой соседних
    #    токенов; при fuzzy допускается неточное совпадение)
    targets = sorted({normalize_word(w) for w in target_words} - {""},
                     key=len, reverse=True)
    if not targets:
        raise ValueError("После нормализации список искомых слов пуст")

    tokens = []
    for w in words:
        cleaned = normalize_word(w["word"])
        if cleaned:
            tokens.append((cleaned, float(w["start"]), float(w["end"])))

    fragments = _find_fragments(tokens, targets, fuzzy, similarity, params)
    fragments = fragments[:max_fragments]

    # 4) запись .seg рядом с исходным аудиофайлом (UTF-8 с BOM —
    #    чтобы кириллица корректно читалась в Wave Assistant)
    base_name = os.path.splitext(os.path.basename(audio_path))[0]
    seg_path = os.path.join(os.path.dirname(os.path.abspath(audio_path)),
                            f"{base_name}.seg")

    params_out = dict(params)
    params_out["N_LABEL"] = len(fragments) * 2  # на каждый фрагмент — 2 метки

    lines = ["[PARAMETERS]\n"]
    for key, value in params_out.items():
        lines.append(f"{key}={value}\n")
    lines.append("[LABELS]\n")
    for frag in fragments:
        # На каждый фрагмент — ДВЕ метки: начало (со словом)
        # и конец (пустая). Первое число — номер БАЙТА (не отсчёта).
        lines.append(f"{frag['byte_start']},8,{frag['word']}\n")
        lines.append(f"{frag['byte_end']},8,\n")

    with open(seg_path, "w", encoding="utf-8-sig") as f:
        f.writelines(lines)

    return seg_path, fragments


def search_words_in_files(files: list, target_words: list,
                          max_fragments: int = 1,
                          model_name: str = DEFAULT_MODEL,
                          language: str = DEFAULT_LANGUAGE,
                          fuzzy: bool = False,
                          similarity: float = 0.8,
                          log=None, progress=None,
                          cancel_event=None) -> list:
    """
    Пакетная обработка: ищет слова в нескольких файлах.
    .seg сохраняется рядом с каждым исходным аудио.
    progress(i, total) — колбэк прогресса; cancel_event — threading.Event
    для прерывания между файлами.
    Возвращает список путей к созданным .seg.
    """
    results = []
    total = len(files)
    for i, path in enumerate(files, 1):
        if cancel_event is not None and cancel_event.is_set():
            if log:
                log("Задача прервана пользователем.")
            break
        name = os.path.basename(path)
        if log:
            log(f"Обработка {i}/{total}: {name}")
        if progress:
            progress(i - 1, total)
        try:
            seg_path, fragments = find_words_in_audio(
                path, target_words, max_fragments, model_name, language,
                fuzzy=fuzzy, similarity=similarity)
            if log:
                log(f"  Найдено фрагментов: {len(fragments)} -> "
                    f"{os.path.basename(seg_path)}")
                for frag in fragments:
                    matched = (f" (распознано: '{frag['matched']}')"
                               if frag["matched"] != frag["word"] else "")
                    log(f"    '{frag['word']}'{matched}: "
                        f"{frag['start']:.2f}–{frag['end']:.2f} с "
                        f"(байты {frag['byte_start']}–{frag['byte_end']})")
            results.append(seg_path)
        except Exception as e:
            if log:
                log(f"  ОШИБКА: {e}")
        if progress:
            progress(i, total)
    return results
