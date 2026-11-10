"""
Генератор метаданных реплик (в стиле main.yml: db_va_data_ai_assets_by_groups)
из таблицы (xlsx/csv) с параллельной нарезкой аудио по .seg-разметке.

Логика:
  * каждая строка таблицы -> запись в метаданных;
  * если в имени файла встречается маркер кастомной переменной
    (например «cn»), запись режется по .seg-разметке, лежащей рядом
    с аудио: отрывки, у которых НАЧАЛЬНАЯ метка содержит заданный
    текст (конечная метка — пустая), вырезаются, оставшиеся куски
    сохраняются как {имя}_1.wav, {имя}_2.wav..., а запись оформляется
    как «- parts:» с чередованием аудиофрагментов и переменных;
  * текст реплики делится по обозначениям переменных
    (например {subscriber_name}); куски текста сопоставляются
    сохранённым аудиофрагментам по порядку следования;
  * номер реплики {n} растёт на 1 с каждой строкой ТАБЛИЦЫ
    (а не с каждым фрагментом нарезки).

Подстановка в шаблоны — простая замена токенов {filename}, {text},
{duration_s}, {duration_ms}, {n}, {intent}, {name}. Двойные фигурные
скобки Ansible вида {{ db_va_data_s3_bucket }} не затрагиваются.
"""

import os
import re

from core.audio_io import AUDIO_EXTENSIONS

TABLE_EXTENSIONS = (".xlsx", ".xls", ".csv")

HEADER_LINE = "db_va_data_ai_assets_by_groups:"

DEFAULT_RECORD_TEMPLATE = (
    "- { filename: 's3://{{ db_va_data_s3_bucket }}/{filename}', "
    "transcription: '{text}', duration_s: {duration_s} }")
DEFAULT_INTENT_TEMPLATE = "- {intent}:"
DEFAULT_VOICE_LINE = "- voice_id_2101: # Maya"
DEFAULT_PARTS_TEMPLATE = "- parts:"
DEFAULT_VAR_TEMPLATE = '- { part_type: "{name}" }'

# Синонимы названий столбцов (если заданное имя не найдено)
COLUMN_ALIASES = {
    "text": {"text", "текст", "transcription", "транскрипция", "реплика"},
    "filename": {"filename", "file", "название файла", "имя файла",
                 "файл"},
    "intent": {"intent", "интент", "наименование интента",
               "название интента"},
}


def default_variables() -> list:
    """Две переменные «из коробки»: caller name / caller reason."""
    return [
        {"marker": "cn", "seg_label": "subscriber_name",
         "placeholder": "{subscriber_name}", "name": "subscriber_name",
         "template": DEFAULT_VAR_TEMPLATE, "indent": 16},
        {"marker": "cr", "seg_label": "subscriber_reason",
         "placeholder": "{subscriber_reason}", "name": "subscriber_reason",
         "template": DEFAULT_VAR_TEMPLATE, "indent": 16},
    ]


# ------------------------------------------------------------- таблица

def load_table(path: str):
    """Читает таблицу (xlsx/xls/csv) в DataFrame со строковыми ячейками."""
    import pandas as pd
    ext = os.path.splitext(path)[1].lower()
    if ext == ".csv":
        df = pd.read_csv(path, dtype=str, encoding="utf-8-sig",
                         sep=None, engine="python")
    elif ext in (".xlsx", ".xls"):
        df = pd.read_excel(path, dtype=str, sheet_name=0)
    else:
        raise ValueError(f"Неподдерживаемый формат таблицы: {ext} "
                         f"(нужны xlsx/xls/csv)")
    return df.fillna("")


def resolve_column(df, requested: str, kind: str, required: bool = True):
    """
    Находит столбец: сначала точное совпадение с requested
    (без учёта регистра/пробелов), потом синонимы из COLUMN_ALIASES.
    Возвращает реальное имя столбца или None.
    """
    columns = {str(c).strip().lower(): c for c in df.columns}
    requested = (requested or "").strip().lower()
    if requested and requested in columns:
        return columns[requested]
    for alias in COLUMN_ALIASES.get(kind, set()):
        if alias in columns:
            return columns[alias]
    if required:
        raise ValueError(
            f"В таблице нет столбца «{requested or kind}». "
            f"Доступные столбцы: {', '.join(str(c) for c in df.columns)}")
    return None


# -------------------------------------------------------------- разметка

def read_seg(path: str, with_params: bool = False):
    """
    Читает .seg (UTF-8 с BOM) и возвращает список меток
    [{pos, name}], где pos — позиция в ОТСЧЁТАХ (не байтах).
    При with_params=True возвращает (labels, params) — параметры
    нужны, например, для предпросмотра (SAMPLING_FREQ).
    """
    with open(path, encoding="utf-8-sig") as f:
        lines = [line.strip() for line in f]

    header_start = lines.index("[PARAMETERS]") + 1
    data_start = lines.index("[LABELS]") + 1

    params = {}
    for line in lines[header_start:data_start - 1]:
        if "=" in line:
            key, value = line.split("=", 1)
            params[key.strip()] = int(value.strip())
    bps = params.get("BYTE_PER_SAMPLE", 2)
    nch = params.get("N_CHANNEL", 1)

    labels = []
    for line in lines[data_start:]:
        if line.count(",") < 2:
            break
        pos, _level, name = line.split(",", maxsplit=2)
        labels.append({"pos": int(pos) // bps // nch, "name": name.strip()})
    labels.sort(key=lambda lab: lab["pos"])
    if with_params:
        return labels, params
    return labels


def find_cut_regions(labels: list, label_names: list) -> list:
    """
    Из списка меток выделяет отрывки на вырезку: начальная метка
    (текст из label_names) + следующая за ней метка (конец).
    Возвращает [{start, end, name}] в отсчётах, по порядку.
    """
    wanted = {n.strip().lower() for n in label_names if n and n.strip()}
    regions = []
    i = 0
    while i < len(labels):
        lab = labels[i]
        if lab["name"] and lab["name"].lower() in wanted:
            if i + 1 < len(labels):
                regions.append({"start": lab["pos"],
                                "end": labels[i + 1]["pos"],
                                "name": lab["name"]})
                i += 2
                continue
        i += 1
    regions.sort(key=lambda r: r["start"])
    return regions


# ---------------------------------------------------------------- аудио

def cut_audio_by_regions(audio_path: str, regions: list,
                         out_dir: str, log=None) -> list:
    """
    Вырезает отрывки regions из аудиофайла; оставшиеся куски
    сохраняет в out_dir как {имя}_1.wav, {имя}_2.wav, ...
    Возвращает [{start, end, filename, path, duration}] по порядку.
    """
    import soundfile as sf

    info = sf.info(audio_path)
    data, sr = sf.read(audio_path, always_2d=True)
    total = data.shape[0]

    subtype = info.subtype if info.format == "WAV" and info.subtype \
        else "PCM_16"
    base = os.path.splitext(os.path.basename(audio_path))[0]
    os.makedirs(out_dir, exist_ok=True)

    chunks = []
    for start, end in _chunk_bounds(total, regions):
        if end - start < int(0.05 * sr):  # короче 50 мс — пропускаем
            continue
        fname = f"{base}_{len(chunks) + 1}.wav"
        fpath = os.path.join(out_dir, fname)
        sf.write(fpath, data[start:end], sr, subtype=subtype)
        chunks.append({"start": start, "end": end, "filename": fname,
                       "path": fpath, "duration": (end - start) / sr})
    if log:
        log(f"  Нарезано фрагментов: {len(chunks)} -> {out_dir}")
    return chunks


def audio_duration(path: str) -> float:
    import soundfile as sf
    info = sf.info(path)
    return info.frames / float(info.samplerate)


# ---------------------------------------------------------------- текст

def split_text_by_placeholders(text: str, placeholders: list) -> list:
    """
    Делит текст по обозначениям переменных ({subscriber_name} и т.п.).
    Возвращает куски текста (без переменных) в порядке следования —
    они сопоставляются аудиофрагментам по порядку.
    """
    ph = [p for p in placeholders if p]
    if not ph:
        return [text.strip()] if text.strip() else []
    pattern = "(" + "|".join(re.escape(p) for p in ph) + ")"
    tokens = re.split(pattern, text)
    return [t.strip() for t in tokens
            if t and t.strip() and t not in ph]


def render_template(template: str, values: dict) -> str:
    """Простая замена токенов {token} -> значение (без str.format,
    чтобы не трогать {{ ansible_переменные }})."""
    line = template
    for token, value in values.items():
        line = line.replace("{" + token + "}", str(value))
    return line


def _escape_text(text: str) -> str:
    """Экранирование для подстановки в одинарные кавычки шаблона."""
    return text.replace("\\", "\\\\").replace("'", "\\'")


def _file_line_values(filename: str, text: str, duration: float,
                      n: int) -> dict:
    return {
        "filename": filename,
        "text": _escape_text(text),
        "duration_s": int(round(duration)),
        "duration_ms": int(round(duration * 1000)),
        "n": n,
    }


# ------------------------------------------------------------ рендеринг

def _chunk_bounds(total: int, regions: list) -> list:
    """Границы сохраняемых кусков: дополнение отрывков regions
    к интервалу [0, total]. Возвращает [(start, end), ...] в отсчётах."""
    bounds = [0]
    for region in regions:
        bounds.append(max(0, min(total, region["start"])))
        bounds.append(max(0, min(total, region["end"])))
    bounds.append(total)
    return [(bounds[k], bounds[k + 1]) for k in range(0, len(bounds) - 1, 2)]


def _build_parts(chunks: list, regions: list, pieces: list,
                 involved: list) -> list:
    """
    Собирает список parts в хронологическом порядке: аудиофрагменты
    (chunks: {start, filename, duration}) чередуются с переменными
    (regions сопоставляются конфигам involved по тексту метки).
    Куски текста pieces сопоставляются фрагментам по порядку.
    """
    timeline = [(c["start"], "file", c) for c in chunks]
    timeline += [(r["start"], "var", r) for r in regions]
    timeline.sort(key=lambda item: item[0])

    parts = []
    piece_i = 0
    for _pos, kind, obj in timeline:
        if kind == "file":
            piece = pieces[piece_i] if piece_i < len(pieces) else ""
            piece_i += 1
            parts.append({"kind": "file", "filename": obj["filename"],
                          "text": piece, "duration": obj["duration"]})
        else:
            var = next(
                (v for v in involved
                 if v.get("seg_label", "").strip().lower()
                 == obj["name"].lower()),
                involved[0])
            parts.append({"kind": "var", "var": var})
    return parts


def render_metadata_text(records: list, cfg: dict,
                         intents_enabled: bool) -> str:
    """Собирает текст файла метаданных из готовых записей."""
    record_template = cfg.get("record_template") or DEFAULT_RECORD_TEMPLATE
    record_indent = int(cfg.get("record_indent") or 0)
    parts_template = cfg.get("parts_template") or DEFAULT_PARTS_TEMPLATE
    parts_indent = int(cfg.get("parts_indent") or 0)
    parts_content_indent = int(cfg.get("parts_content_indent") or 0)
    intent_template = cfg.get("intent_template") or DEFAULT_INTENT_TEMPLATE
    intent_indent = int(cfg.get("intent_indent") or 0)
    number_enabled = bool(cfg.get("number_enabled"))

    def render_file_line(rec, item, indent):
        values = _file_line_values(item["filename"], item["text"],
                                   item["duration"],
                                   rec["n"] if number_enabled else "")
        return " " * indent + render_template(record_template, values)

    def render_record(rec, lines):
        """Добавляет в lines строки одной записи (каждая с \\n)."""
        if "parts" in rec:
            lines.append(" " * parts_indent + parts_template + "\n")
            for part in rec["parts"]:
                if part["kind"] == "file":
                    lines.append(render_file_line(rec, part,
                                                  parts_content_indent)
                                 + "\n")
                else:
                    var = part["var"]
                    line = render_template(
                        var.get("template") or DEFAULT_VAR_TEMPLATE,
                        {"name": var.get("name", "")})
                    lines.append(" " * int(var.get("indent") or 0)
                                 + line + "\n")
        else:
            lines.append(render_file_line(rec, rec["file"],
                                          record_indent) + "\n")

    lines = [HEADER_LINE + "\n"]
    if cfg.get("voice_enabled"):
        voice_line = cfg.get("voice_line") or DEFAULT_VOICE_LINE
        lines.append(" " * int(cfg.get("voice_indent") or 0)
                     + voice_line + "\n")

    if intents_enabled:
        groups = {}
        for rec in records:
            groups.setdefault(rec["intent"], []).append(rec)
        for intent, recs in groups.items():
            lines.append(" " * intent_indent
                         + render_template(intent_template,
                                           {"intent": intent}) + "\n")
            for rec in recs:
                render_record(rec, lines)
    else:
        for rec in records:
            render_record(rec, lines)

    return "".join(lines)


# ------------------------------------------------------------ генерация

def _resolve_audio(audio_dir: str, raw_name: str):
    """Ищет аудиофайл из ячейки таблицы в папке с аудио."""
    raw_name = (raw_name or "").strip().strip("'\"")
    if not raw_name:
        return None
    candidates = []
    if os.path.isabs(raw_name):
        candidates.append(raw_name)
    candidates.append(os.path.join(audio_dir, raw_name))
    candidates.append(os.path.join(audio_dir, os.path.basename(raw_name)))
    stem = os.path.splitext(candidates[-1])[0]
    candidates.extend(stem + ext for ext in AUDIO_EXTENSIONS)
    for cand in candidates:
        if os.path.isfile(cand):
            return cand
    return None


def generate_metadata(cfg: dict, log=None, progress=None,
                      cancel_event=None) -> dict:
    """
    Генерирует файл метаданных и (при необходимости) режет аудио.

    cfg — словарь с ключами:
      table_path, audio_dir, output_path, output_audio_dir,
      text_column, filename_column, intent_column,
      voice_enabled, voice_line, voice_indent,
      intents_enabled, intent_indent, intent_template,
      record_template, record_indent,
      parts_template, parts_indent, parts_content_indent,
      number_enabled, number_start,
      variables — список dict: marker, seg_label, placeholder, name,
                  template, indent.

    Возвращает статистику: {records, intents, fragments, warnings,
    canceled, output_path}.
    """

    def _log(msg):
        if log:
            log(msg)

    audio_dir = cfg["audio_dir"]
    variables = [v for v in cfg.get("variables", [])
                 if (v.get("marker") or "").strip()]

    df = load_table(cfg["table_path"])
    text_col = resolve_column(df, cfg.get("text_column"), "text")
    file_col = resolve_column(df, cfg.get("filename_column"), "filename")

    intents_enabled = bool(cfg.get("intents_enabled", True))
    intent_col = None
    if intents_enabled:
        intent_col = resolve_column(df, cfg.get("intent_column"),
                                    "intent", required=False)
        if intent_col is None:
            _log("ПРЕДУПРЕЖДЕНИЕ: столбец интента не найден в таблице — "
                 "метаданные будут сгенерированы без уровня интентов.")
            intents_enabled = False

    out_audio_dir = (cfg.get("output_audio_dir") or "").strip() or audio_dir

    number_start = int(cfg.get("number_start") or 1)

    records = []      # [{intent, n, file|parts}]
    created_files = []  # пути к нарезанным аудиофрагментам
    warnings = 0
    canceled = False
    total = len(df)

    for idx in range(total):
        if cancel_event is not None and cancel_event.is_set():
            _log("Задача прервана пользователем.")
            canceled = True
            break

        row = df.iloc[idx]
        n = number_start + idx  # номер реплики — номер строки таблицы
        text = str(row[text_col] or "").strip()
        raw_name = str(row[file_col] or "").strip()
        intent = str(row[intent_col]).strip() if intent_col else ""

        if intent_col and not intent:
            _log(f"  ПРЕДУПРЕЖДЕНИЕ: строка {idx + 2} без интента — "
                 f"пропущена.")
            warnings += 1
            if progress:
                progress(idx + 1, total)
            continue
        if not raw_name:
            _log(f"  ПРЕДУПРЕЖДЕНИЕ: строка {idx + 2} без имени файла — "
                 f"пропущена.")
            warnings += 1
            if progress:
                progress(idx + 1, total)
            continue

        _log(f"Строка {idx + 1}/{total}: {raw_name}")
        audio_path = _resolve_audio(audio_dir, raw_name)
        if audio_path is None:
            _log(f"  ОШИБКА: аудиофайл не найден в {audio_dir} — "
                 f"строка пропущена.")
            warnings += 1
            if progress:
                progress(idx + 1, total)
            continue

        base = os.path.splitext(os.path.basename(audio_path))[0]
        involved = [v for v in variables
                    if v["marker"].strip().lower() in base.lower()]

        if involved:
            # --- реплика с переменными: режем по .seg ---
            seg_path = os.path.join(os.path.dirname(audio_path),
                                    base + ".seg")
            if not os.path.isfile(seg_path):
                _log(f"  ОШИБКА: нет файла разметки {base}.seg рядом с "
                     f"аудио — строка пропущена.")
                warnings += 1
                if progress:
                    progress(idx + 1, total)
                continue
            try:
                labels = read_seg(seg_path)
            except Exception as e:
                _log(f"  ОШИБКА чтения {base}.seg: {e} — строка "
                     f"пропущена.")
                warnings += 1
                if progress:
                    progress(idx + 1, total)
                continue

            regions = find_cut_regions(
                labels, [v.get("seg_label", "") for v in involved])
            if not regions:
                _log(f"  ОШИБКА: в {base}.seg нет меток с текстом "
                     f"«{'», «'.join(v.get('seg_label', '') for v in involved)}»"
                     f" — строка пропущена.")
                warnings += 1
                if progress:
                    progress(idx + 1, total)
                continue

            chunks = cut_audio_by_regions(audio_path, regions,
                                          out_audio_dir, log=log)
            created_files.extend(c["path"] for c in chunks)
            pieces = split_text_by_placeholders(
                text, [v.get("placeholder", "") for v in involved])
            if len(pieces) != len(chunks):
                _log(f"  ПРЕДУПРЕЖДЕНИЕ: кусков текста ({len(pieces)}) "
                     f"не совпадает с числом аудиофрагментов "
                     f"({len(chunks)}) для {base}.")
                warnings += 1

            parts = _build_parts(chunks, regions, pieces, involved)
            records.append({"intent": intent, "n": n, "parts": parts})
        else:
            # --- обычная реплика без нарезки ---
            if re.search(r"\{[A-Za-z_]+\}", text):
                _log(f"  ПРЕДУПРЕЖДЕНИЕ: текст содержит переменную, но "
                     f"маркера в имени файла нет — запись без нарезки.")
                warnings += 1
            records.append({
                "intent": intent, "n": n,
                "file": {"filename": os.path.basename(audio_path),
                         "text": text,
                         "duration": audio_duration(audio_path)}})

        if progress:
            progress(idx + 1, total)

    # ------------------------------------------------- рендеринг файла
    text_out = render_metadata_text(records, cfg, intents_enabled)
    output_path = cfg["output_path"]
    os.makedirs(os.path.dirname(os.path.abspath(output_path)),
                exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(text_out)

    fragments = sum(len(r["parts"]) for r in records if "parts" in r)
    _log(f"Готово: записей — {len(records)}, строк в parts — "
         f"{fragments}, предупреждений — {warnings}.")
    _log(f"Метаданные сохранены: {output_path}")

    return {"records": len(records), "fragments": fragments,
            "warnings": warnings, "canceled": canceled,
            "intents": intents_enabled, "output_path": output_path,
            "created_files": created_files}


# ---------------------------------------------------------- предпросмотр

def preview_metadata(cfg: dict, max_rows: int = 2, log=None) -> str:
    """
    Текстовый предпросмотр: как первые max_rows строк таблицы будут
    выглядеть в метаданных. Аудио НЕ нарезается и не сохраняется —
    длительности берутся из заголовков файлов, если они доступны
    (иначе из .seg-разметки). Имена будущих фрагментов показываются
    такими, какими они будут созданы ({имя}_1.wav, ...).
    """

    def _log(msg):
        if log:
            log(msg)

    audio_dir = (cfg.get("audio_dir") or "").strip()
    variables = [v for v in cfg.get("variables", [])
                 if (v.get("marker") or "").strip()]

    df = load_table(cfg["table_path"])
    text_col = resolve_column(df, cfg.get("text_column"), "text")
    file_col = resolve_column(df, cfg.get("filename_column"), "filename")

    intents_enabled = bool(cfg.get("intents_enabled", True))
    intent_col = None
    if intents_enabled:
        intent_col = resolve_column(df, cfg.get("intent_column"),
                                    "intent", required=False)
        if intent_col is None:
            _log("ПРЕДУПРЕЖДЕНИЕ: столбец интента не найден — "
                 "предпросмотр без уровня интентов.")
            intents_enabled = False

    number_start = int(cfg.get("number_start") or 1)
    rows = min(max(1, max_rows), len(df))
    _log(f"Предпросмотр первых {rows} строк таблицы "
         f"(без нарезки аудио).")

    records = []
    for idx in range(rows):
        row = df.iloc[idx]
        n = number_start + idx
        text = str(row[text_col] or "").strip()
        raw_name = str(row[file_col] or "").strip()
        intent = str(row[intent_col]).strip() if intent_col else ""

        if intent_col and not intent:
            _log(f"  Строка {idx + 2}: нет интента — пропущена.")
            continue
        if not raw_name:
            _log(f"  Строка {idx + 2}: нет имени файла — пропущена.")
            continue

        base = os.path.splitext(os.path.basename(raw_name))[0]
        audio_path = (_resolve_audio(audio_dir, raw_name)
                      if audio_dir else None)
        involved = [v for v in variables
                    if v["marker"].strip().lower() in base.lower()]

        if involved:
            # --- запись с переменными: читаем .seg, но не режем аудио ---
            seg_dir = (os.path.dirname(audio_path)
                       if audio_path else audio_dir)
            seg_path = os.path.join(seg_dir, base + ".seg")
            regions = []
            sr = 0
            if os.path.isfile(seg_path):
                try:
                    labels, params = read_seg(seg_path, with_params=True)
                    regions = find_cut_regions(
                        labels, [v.get("seg_label", "") for v in involved])
                    sr = params.get("SAMPLING_FREQ", 0)
                except Exception as e:
                    _log(f"  {base}: ошибка чтения разметки: {e} — "
                         f"показано как обычная запись.")
            else:
                _log(f"  {base}: нет файла {base}.seg — показано как "
                     f"обычная запись (при генерации такая строка "
                     f"будет пропущена!).")

            if regions:
                if audio_path:
                    import soundfile as sf
                    info = sf.info(audio_path)
                    sr = info.samplerate
                    total = info.frames
                elif sr:
                    total = max(r["end"] for r in regions)
                    _log(f"  {base}: аудиофайл не найден — длительности "
                         f"посчитаны по разметке; последний фрагмент "
                         f"может не отображаться.")
                else:
                    total = 0
                if total and sr:
                    chunks = []
                    for start, end in _chunk_bounds(total, regions):
                        if end - start < int(0.05 * sr):
                            continue
                        chunks.append({
                            "start": start, "end": end,
                            "filename": f"{base}_{len(chunks) + 1}.wav",
                            "duration": (end - start) / sr})
                    pieces = split_text_by_placeholders(
                        text, [v.get("placeholder", "") for v in involved])
                    if len(pieces) != len(chunks):
                        _log(f"  {base}: кусков текста ({len(pieces)}) "
                             f"!= фрагментов ({len(chunks)}).")
                    parts = _build_parts(chunks, regions, pieces,
                                         involved)
                    records.append({"intent": intent, "n": n,
                                    "parts": parts})
                    continue

        # --- обычная запись (или фолбэк при проблемах с разметкой) ---
        if audio_path:
            duration = audio_duration(audio_path)
        else:
            duration = 0.0
            _log(f"  {base}: аудиофайл не найден — длительность "
                 f"показана как 0.")
        records.append({
            "intent": intent, "n": n,
            "file": {"filename": os.path.basename(raw_name),
                     "text": text, "duration": duration}})

    return render_metadata_text(records, cfg, intents_enabled)
