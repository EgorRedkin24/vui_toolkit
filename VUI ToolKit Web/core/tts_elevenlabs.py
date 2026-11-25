"""
Синтез речи через ElevenLabs API для VUI ToolKit.

Два режима:
    - озвучка одной фразы;
    - озвучка фраз из таблицы: столбец 'text_lat' (обязательный), затем —
      'text_rus' (если заполнен; к имени файла добавляется _ru). Имя файла
      берётся из столбца 'name', голос строки — из 'voice' (voice_id).

Ручная пауза и автопауза при ошибках доступа (401/402/403/429/439)
реализованы через PauseControl.
"""

import os
import re
import threading
import time

import requests

TTS_MODELS = ["eleven_multilingual_v2", "eleven_v3", "eleven_v4", "eleven_turbo_v2_5"]
DEFAULT_MODEL = "eleven_multilingual_v2"
OUTPUT_FORMAT = "mp3_44100_128"
VOICE_SETTINGS = {"stability": 0.6, "similarity_boost": 0.8}
MAX_RETRIES = 5
# Ошибки доступа/лимитов: после них нет смысла сыпать запросами дальше.
ACCESS_ERROR_CODES = {401, 402, 403, 429, 439}
# Эти коды не лечатся повтором — сразу останавливаемся.
NO_RETRY_CODES = {401, 402, 403, 439}


class ElevenLabsAccessError(Exception):
    """Ошибка доступа/лимита ElevenLabs (401, 402, 403, 429, 439)."""

    def __init__(self, status: int, message: str):
        super().__init__(f"{status}: {message}")
        self.status = status
        self.message = message


class PauseControl:
    """
    Пауза с возможностью возобновления. Используется и вручную (кнопка),
    и автоматически (ошибки доступа). on_change(paused: bool, reason: str)
    вызывается из любого потока при смене состояния.
    """

    def __init__(self, on_change=None):
        self._paused = threading.Event()
        self.on_change = on_change

    @property
    def paused(self) -> bool:
        return self._paused.is_set()

    def pause(self, reason: str = ""):
        if not self._paused.is_set():
            self._paused.set()
            if self.on_change:
                self.on_change(True, reason)

    def resume(self):
        if self._paused.is_set():
            self._paused.clear()
            if self.on_change:
                self.on_change(False, "")

    def toggle(self):
        if self.paused:
            self.resume()
        else:
            self.pause("вручную")

    def wait_if_paused(self, cancel_event=None) -> bool:
        """Блокируется, пока идёт пауза. False — если задачу прервали."""
        while self._paused.is_set():
            if cancel_event is not None and cancel_event.is_set():
                return False
            time.sleep(0.2)
        return not (cancel_event is not None and cancel_event.is_set())


def resolve_dictionary_locators(dictionary_ids, api_key: str, log=None) -> list:
    """
    По ID словарей произношений подтягивает актуальную версию и возвращает
    pronunciation_dictionary_locators для запроса. dictionary_ids — строка
    (через запятую/пробел/перенос) или список; ElevenLabs принимает до 3.
    """
    if isinstance(dictionary_ids, str):
        dictionary_ids = [x for x in re.split(r"[\s,;]+", dictionary_ids) if x]
    locators = []
    for dict_id in dictionary_ids[:3]:
        response = requests.get(
            f"https://api.elevenlabs.io/v1/pronunciation-dictionaries/{dict_id}",
            headers={"xi-api-key": api_key}, timeout=30)
        if response.status_code != 200:
            try:
                msg = response.json().get("detail", response.text)
            except Exception:
                msg = response.text
            if response.status_code in ACCESS_ERROR_CODES:
                raise ElevenLabsAccessError(response.status_code, str(msg))
            raise ValueError(f"Словарь {dict_id}: статус "
                             f"{response.status_code}, {msg}")
        info = response.json()
        version_id = info.get("latest_version_id") or info.get("version_id")
        if not version_id:
            raise ValueError(f"Словарь {dict_id}: в ответе нет версии")
        if log:
            log(f"Словарь {info.get('name', dict_id)}: версия {version_id}")
        locators.append({"pronunciation_dictionary_id": dict_id,
                         "version_id": version_id})
    return locators


# Столбцы таблицы, из которых берётся имя конкретного файла строки
# (в порядке приоритета; распознаются и русские названия).
FILENAME_COLUMNS = ("name", "filename", "file_name", "имя файла", "название файла")

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


def _safe_name(value) -> str:
    """Имя файла из ячейки 'name': без недопустимых символов и расширения."""
    if value is None or (isinstance(value, float) and value != value):
        return ""
    name = str(value).strip()
    if name.lower().endswith(".mp3"):
        name = name[:-4]
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name).strip(" .")
    return name


def synthesize(text: str, voice_id: str, api_key: str, output_path: str,
               model_id: str = DEFAULT_MODEL, log=None,
               dictionary_locators=None) -> bool:
    """
    Озвучивает текст голосом voice_id и сохраняет MP3 в output_path.
    Делает до MAX_RETRIES попыток с экспоненциальной паузой.
    При ошибках доступа/лимитов (ACCESS_ERROR_CODES) бросает
    ElevenLabsAccessError: сразу для NO_RETRY_CODES, для 429 — после
    исчерпания попыток.
    """
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    headers = {
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
        "xi-api-key": api_key,
    }
    data = {
        "text": text,
        "model_id": model_id,
        "voice_settings": VOICE_SETTINGS,
        "output_format": OUTPUT_FORMAT,
    }
    if dictionary_locators:
        data["pronunciation_dictionary_locators"] = dictionary_locators

    access_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.post(url, json=data, headers=headers, timeout=60)
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
            if response.status_code in ACCESS_ERROR_CODES:
                access_error = ElevenLabsAccessError(response.status_code,
                                                     str(error_msg))
                if response.status_code in NO_RETRY_CODES:
                    raise access_error
            if attempt < MAX_RETRIES:
                time.sleep(2 ** attempt)
        except ElevenLabsAccessError:
            raise
        except Exception as e:
            if log:
                log(f"  Попытка {attempt}: {e}")
            if attempt < MAX_RETRIES:
                time.sleep(2 ** attempt)
    if access_error is not None:
        raise access_error
    return False


def synthesize_single(text: str, voice_id: str, api_key: str,
                      output_dir: str, model_id: str = DEFAULT_MODEL,
                      log=None, dictionary_locators=None) -> str:
    """Озвучка одной фразы. Возвращает путь к файлу или None."""
    out_path = os.path.join(output_dir, "tts_phrase.mp3")
    # не затираем существующие файлы
    n = 1
    while os.path.exists(out_path):
        out_path = os.path.join(output_dir, f"tts_phrase_{n:02d}.mp3")
        n += 1
    if log:
        log(f"Генерация фразы: {text[:60]}{'...' if len(text) > 60 else ''}")
    try:
        ok = synthesize(text, voice_id, api_key, out_path, model_id, log,
                        dictionary_locators)
    except ElevenLabsAccessError as e:
        if log:
            log(f"  ОШИБКА ДОСТУПА ElevenLabs {e}")
        ok = False
    if log:
        log(f"  -> {os.path.basename(out_path)}" if ok else "  ОШИБКА генерации")
    return out_path if ok else None


AUTO_COLUMN = "auto"


def resolve_columns(df, column: str = AUTO_COLUMN) -> list:
    """
    Список (столбец, суффикс имени файла) в порядке озвучки.
    'auto' — text_lat, затем text_rus (_ru), если он есть в таблице.
    Один столбец: text_rus — суффикс _ru, остальные — без суффикса.
    """
    if column in (None, "", AUTO_COLUMN):
        if "text_lat" not in df.columns:
            raise ValueError("Таблица должна содержать столбец 'text_lat'")
        cols = [("text_lat", "")]
        if "text_rus" in df.columns:
            cols.append(("text_rus", "_ru"))
        return cols
    if column not in df.columns:
        raise ValueError(f"В таблице нет столбца '{column}'")
    suffix = "_ru" if column == "text_rus" else ""
    return [(column, suffix)]


def _build_tasks(df, default_voice_id: str, log=None,
                 column: str = AUTO_COLUMN,
                 filename_template: str = None) -> list:
    """
    Собирает задачи по столбцам из resolve_columns: сначала все строки
    первого столбца, затем (если есть данные) следующего.
    Задача: (номер строки, столбец, текст, voice_id, имя файла).
    """
    voice_col = ("voice" if "voice" in df.columns else
                 "voice_id" if "voice_id" in df.columns else None)
    name_col = next((c for c in FILENAME_COLUMNS if c in df.columns), None)
    names = df[name_col].tolist() if name_col else None
    used = set()

    def make_task(idx, lang, suffix, text):
        voice_id = default_voice_id
        if voice_col:
            row_voice = df[voice_col].iloc[idx - 1]
            if isinstance(row_voice, str) and row_voice.strip():
                voice_id = row_voice.strip()
        base = _safe_name(names[idx - 1]) if names else ""
        if not base and filename_template:
            try:
                base = _safe_name(filename_template.format(n=idx))
            except Exception as e:
                if log:
                    log(f"  Шаблон имени некорректен ({e}) — "
                        f"используется имя по умолчанию")
        if not base:
            base = f"tts_{idx:03d}"
        base += suffix
        unique, n = base, 2
        while unique.lower() in used:       # одинаковые name в разных строках
            unique = f"{base}_{n:02d}"
            n += 1
        used.add(unique.lower())
        return (idx, lang, text.strip(), voice_id, unique + ".mp3")

    tasks = []
    for pos, (col, suffix) in enumerate(resolve_columns(df, column)):
        for idx, text in enumerate(df[col].tolist(), 1):
            if not isinstance(text, str) or not text.strip():
                if pos == 0 and log:
                    log(f"Строка {idx}: пустой {col}, пропуск")
                continue
            tasks.append(make_task(idx, col, suffix, text))
    return tasks


def synthesize_table(df, default_voice_id: str, api_key: str,
                     output_dir: str, model_id: str = DEFAULT_MODEL,
                     log=None, progress=None, cancel_event=None,
                     pause=None, dictionary_locators=None,
                     column: str = AUTO_COLUMN, range_start: int = 1,
                     range_end=None, on_range_end=None,
                     filename_template: str = None) -> list:
    """
    Озвучка фраз из таблицы (pandas DataFrame).
    column — из какого столбца озвучиваем: 'auto' (text_lat, затем text_rus
    с суффиксом _ru) либо имя конкретного столбца. Необязательные столбцы:
    'name' / 'filename' (имя файла), 'voice' (voice_id для строки);
    если имя в строке не задано — filename_template (токен {n}).
    range_start/range_end — диапазон реплик (нумерация как в логе
    «Генерация n/всего», с 1, включительно; range_end=None — до конца).
    По достижении конца диапазона включается пауза и вызывается
    on_range_end(range_end, осталось); «Продолжить» озвучивает остаток.
    progress(i, total) — колбэк прогресса; cancel_event — threading.Event;
    pause — PauseControl (ручная пауза и автопауза при ошибках доступа).
    Возвращает список путей к созданным файлам.
    """
    tasks = _build_tasks(df, default_voice_id, log, column,
                         filename_template)
    total = len(tasks)
    range_start = max(1, range_start or 1)
    if range_end is not None and range_end < range_start:
        raise ValueError("Конец диапазона меньше начала")
    if range_start > total:
        if log:
            log(f"Начало диапазона ({range_start}) больше числа реплик "
                f"({total}) — озвучивать нечего.")
        return []
    if log:
        log(f"Реплик к озвучке: {total}; диапазон {range_start}–"
            f"{range_end if range_end is not None else total}")
    created = []
    prev_col = tasks[range_start - 1][1]
    todo = total - range_start + 1
    for n in range(range_start, total + 1):
        idx, lang, text, voice_id, filename = tasks[n - 1]
        if range_end is not None and n == range_end + 1 and pause is not None:
            remaining = total - range_end
            pause.pause(f"конец диапазона {range_start}–{range_end}")
            if log:
                log(f"ПАУЗА: диапазон {range_start}–{range_end} озвучен. "
                    f"Осталось реплик: {remaining}. Нажмите «Продолжить», "
                    f"чтобы озвучить остальные.")
            if on_range_end:
                on_range_end(range_end, remaining)
        if pause is not None:
            pause.wait_if_paused(cancel_event)
        if cancel_event is not None and cancel_event.is_set():
            if log:
                log("Задача прервана пользователем.")
            break
        if lang != prev_col:
            if log:
                log(f"--- {prev_col} завершён, озвучиваем {lang} ---")
            prev_col = lang
        if progress:
            progress(n - range_start, todo)
        if not voice_id:
            if log:
                log(f"Строка {idx} ({lang}): voice id не задан, пропуск")
            continue

        out_path = os.path.join(output_dir, filename)
        if log:
            log(f"Генерация {n}/{total} [{lang}]: {text[:50]}"
                f"{'...' if len(text) > 50 else ''} (voice: {voice_id[:8]}...)")
        ok = False
        while True:
            try:
                ok = synthesize(text, voice_id, api_key, out_path,
                                model_id, log, dictionary_locators)
                break
            except ElevenLabsAccessError as e:
                if pause is None:
                    if log:
                        log(f"ОШИБКА ДОСТУПА ElevenLabs {e}. Остановка.")
                    return created
                pause.pause(f"ошибка {e.status}")
                if log:
                    log(f"ПАУЗА: ошибка ElevenLabs {e}. Исправьте проблему "
                        f"(ключ, баланс, лимиты) и нажмите «Продолжить» — "
                        f"эта фраза будет повторена.")
                if not pause.wait_if_paused(cancel_event):
                    if log:
                        log("Задача прервана пользователем.")
                    return created
        if ok:
            created.append(out_path)
            if log:
                log(f"  -> {filename}")
        elif log:
            log(f"  ОШИБКА генерации строки {idx} ({lang})")
        if progress:
            progress(n - range_start + 1, todo)
    return created


def load_table(path: str):
    """Читает таблицу фраз (Excel или CSV) в pandas DataFrame."""
    import pandas as pd
    if path.lower().endswith(".csv"):
        return pd.read_csv(path)
    return pd.read_excel(path)
