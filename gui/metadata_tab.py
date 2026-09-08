"""
Вкладка «Метаданные»: генерация файла метаданных реплик
(db_va_data_ai_assets_by_groups ...) из таблицы (xlsx/csv)
с параллельной нарезкой аудио по .seg-разметке для записей
с кастомными переменными ({subscriber_name}, {subscriber_reason}, ...).
"""

import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from core import metadata_gen
from gui import theme as theme_mod
from gui.widgets import (DirectorySelector, LogPanel, ResultsPanel, RunBar,
                         ScrollFrame)


class _PreviewDialog(tk.Toplevel):
    """Немодальное окно предпросмотра метаданных (только текст)."""

    def __init__(self, parent, content: str):
        super().__init__(parent)
        self.title("Предпросмотр метаданных")
        self.geometry("880x560")
        self._content = content

        frame = ttk.Frame(self, padding=8)
        frame.pack(fill="both", expand=True)
        self.text = tk.Text(frame, wrap="none", font=("Consolas", 10))
        yscroll = ttk.Scrollbar(frame, orient="vertical",
                                command=self.text.yview)
        xscroll = ttk.Scrollbar(self, orient="horizontal",
                                command=self.text.xview)
        self.text.configure(yscrollcommand=yscroll.set,
                            xscrollcommand=xscroll.set)
        xscroll.pack(side="bottom", fill="x")
        yscroll.pack(side="right", fill="y")
        self.text.pack(side="left", fill="both", expand=True)
        self.text.insert("1.0", content)
        self.text.config(state="disabled")

        btns = ttk.Frame(self, padding=(8, 0, 8, 8))
        btns.pack(fill="x")
        ttk.Button(btns, text="Копировать в буфер",
                   command=self._copy).pack(side="left")
        ttk.Button(btns, text="Закрыть", command=self.destroy).pack(
            side="right")

        # подхватываем текущую тему (диалог создан после apply_theme)
        c = theme_mod.current_theme()
        self.configure(bg=c["bg"])
        theme_mod._restyle_plain_widgets(self, c)

        self.transient(parent.winfo_toplevel())

    def _copy(self):
        self.clipboard_clear()
        self.clipboard_append(self._content)


class _VariableDialog(tk.Toplevel):
    """Диалог добавления/редактирования кастомной переменной."""

    FIELDS = (
        ("marker", "Маркер в имени файла (напр. cn):"),
        ("seg_label", "Текст начальной метки в .seg "
                      "(напр. subscriber_name):"),
        ("placeholder", "Обозначение в тексте "
                        "(напр. {subscriber_name}):"),
        ("name", "Имя переменной для шаблона {name}:"),
        ("template", "Шаблон строки (напр. "
                     '- { part_type: "{name}" }):'),
        ("indent", "Отступ строки, пробелов:"),
    )

    def __init__(self, parent, values=None):
        super().__init__(parent)
        self.title("Переменная")
        self.resizable(False, False)
        self.result = None
        self.vars = {}

        frame = ttk.Frame(self, padding=12)
        frame.pack(fill="both", expand=True)
        for i, (key, label) in enumerate(self.FIELDS):
            ttk.Label(frame, text=label, wraplength=220,
                      justify="left").grid(row=i, column=0, sticky="w",
                                           pady=2)
            var = tk.StringVar(value=(values or {}).get(
                key, "16" if key == "indent" else ""))
            self.vars[key] = var
            width = 12 if key == "indent" else 42
            ttk.Entry(frame, textvariable=var, width=width).grid(
                row=i, column=1, sticky="ew", padx=(8, 0), pady=2)
        btns = ttk.Frame(frame)
        btns.grid(row=len(self.FIELDS), column=0, columnspan=2,
                  pady=(10, 0))
        ttk.Button(btns, text="OK", command=self._ok).pack(
            side="left", padx=4)
        ttk.Button(btns, text="Отмена", command=self.destroy).pack(
            side="left", padx=4)

        self.transient(parent.winfo_toplevel())
        self.grab_set()
        self.wait_window()

    def _ok(self):
        values = {key: var.get().strip() for key, var in self.vars.items()}
        if not values["marker"]:
            messagebox.showerror("Ошибка", "Заполните маркер в имени файла",
                                 parent=self)
            return
        if not values["seg_label"]:
            messagebox.showerror(
                "Ошибка",
                "Заполните текст начальной метки в .seg — по ней "
                "определяется отрывок на вырезку", parent=self)
            return
        try:
            values["indent"] = int(values["indent"] or 0)
        except ValueError:
            messagebox.showerror("Ошибка", "Отступ должен быть числом",
                                 parent=self)
            return
        self.result = values
        self.destroy()


class MetadataTab(ttk.Frame):
    def __init__(self, parent, root):
        super().__init__(parent, padding=10)
        self.root = root
        self._variables = []  # список dict (см. metadata_gen.default_variables)
        self._build_ui()

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        scroll = ScrollFrame(self)
        scroll.pack(fill="both", expand=True)
        body = scroll.content

        # --- таблица реплик ---
        table_frame = ttk.LabelFrame(body, text="Таблица реплик", padding=8)
        table_frame.pack(fill="x", pady=(0, 8))
        self.table_path = tk.StringVar()
        ttk.Entry(table_frame, textvariable=self.table_path).grid(
            row=0, column=0, sticky="ew", padx=(0, 5))
        ttk.Button(table_frame, text="Обзор...",
                   command=self._browse_table).grid(row=0, column=1)
        table_frame.columnconfigure(0, weight=1)

        cols = ttk.Frame(table_frame)
        cols.grid(row=1, column=0, columnspan=2, sticky="w", pady=(6, 0))
        ttk.Label(cols, text="Столбцы — текст:").pack(side="left")
        self.text_col = tk.StringVar(value="text")
        ttk.Entry(cols, textvariable=self.text_col, width=12).pack(
            side="left", padx=(4, 12))
        ttk.Label(cols, text="файл:").pack(side="left")
        self.filename_col = tk.StringVar(value="filename")
        ttk.Entry(cols, textvariable=self.filename_col, width=12).pack(
            side="left", padx=(4, 12))
        ttk.Label(cols, text="интент:").pack(side="left")
        self.intent_col = tk.StringVar(value="intent")
        ttk.Entry(cols, textvariable=self.intent_col, width=12).pack(
            side="left", padx=(4, 0))

        # --- папки и файл метаданных ---
        self.audio_dir = DirectorySelector(body, "Папка с аудиофайлами")
        self.audio_dir.pack(fill="x", pady=(0, 8))
        self.output_audio_dir = DirectorySelector(
            body, "Папка для нарезанных фрагментов (пусто = папка с аудио)")
        self.output_audio_dir.pack(fill="x", pady=(0, 8))

        meta_frame = ttk.LabelFrame(body, text="Файл метаданных (.txt)",
                                    padding=8)
        meta_frame.pack(fill="x", pady=(0, 8))
        self.output_path = tk.StringVar()
        ttk.Entry(meta_frame, textvariable=self.output_path).grid(
            row=0, column=0, sticky="ew", padx=(0, 5))
        ttk.Button(meta_frame, text="Обзор...",
                   command=self._browse_output).grid(row=0, column=1)
        meta_frame.columnconfigure(0, weight=1)

        # --- голос ---
        voice_frame = ttk.LabelFrame(body, text="Голос", padding=8)
        voice_frame.pack(fill="x", pady=(0, 8))
        self.voice_enabled = tk.BooleanVar(value=True)
        ttk.Checkbutton(voice_frame, text="Добавлять строку голоса",
                        variable=self.voice_enabled).grid(
            row=0, column=0, sticky="w")
        ttk.Label(voice_frame, text="Строка:").grid(row=1, column=0,
                                                    sticky="w")
        self.voice_line = tk.StringVar(value=metadata_gen.DEFAULT_VOICE_LINE)
        ttk.Entry(voice_frame, textvariable=self.voice_line, width=42).grid(
            row=1, column=1, sticky="ew", padx=(4, 8))
        ttk.Label(voice_frame, text="Отступ, пробелов:").grid(
            row=1, column=2, sticky="w")
        self.voice_indent = tk.StringVar(value="2")
        tk.Spinbox(voice_frame, from_=0, to=40, width=5,
                   textvariable=self.voice_indent).grid(row=1, column=3,
                                                        sticky="w",
                                                        padx=(4, 0))
        voice_frame.columnconfigure(1, weight=1)

        # --- интенты ---
        intent_frame = ttk.LabelFrame(body, text="Интенты", padding=8)
        intent_frame.pack(fill="x", pady=(0, 8))
        self.intents_enabled = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            intent_frame, text="Группировать записи по интентам "
                               "(столбец проверяется; при проблемах — "
                               "предупреждение в логе)",
            variable=self.intents_enabled).grid(row=0, column=0,
                                                columnspan=4, sticky="w")
        ttk.Label(intent_frame, text="Шаблон:").grid(row=1, column=0,
                                                     sticky="w")
        self.intent_template = tk.StringVar(
            value=metadata_gen.DEFAULT_INTENT_TEMPLATE)
        ttk.Entry(intent_frame, textvariable=self.intent_template,
                  width=24).grid(row=1, column=1, sticky="w", padx=(4, 8))
        ttk.Label(intent_frame, text="Отступ, пробелов:").grid(
            row=1, column=2, sticky="w")
        self.intent_indent = tk.StringVar(value="6")
        tk.Spinbox(intent_frame, from_=0, to=40, width=5,
                   textvariable=self.intent_indent).grid(row=1, column=3,
                                                         sticky="w",
                                                         padx=(4, 0))

        # --- шаблон записи ---
        record_frame = ttk.LabelFrame(body, text="Шаблон строки записи",
                                      padding=8)
        record_frame.pack(fill="x", pady=(0, 8))
        self.record_template = tk.StringVar(
            value=metadata_gen.DEFAULT_RECORD_TEMPLATE)
        ttk.Entry(record_frame, textvariable=self.record_template).grid(
            row=0, column=0, sticky="ew", padx=(0, 8))
        ttk.Label(record_frame, text="Отступ:").grid(row=0, column=1,
                                                     sticky="w")
        self.record_indent = tk.StringVar(value="12")
        tk.Spinbox(record_frame, from_=0, to=40, width=5,
                   textvariable=self.record_indent).grid(row=0, column=2,
                                                         sticky="w",
                                                         padx=(4, 0))
        ttk.Label(
            record_frame,
            text="Токены: {filename} — имя файла, {text} — текст, "
                 "{duration_s} / {duration_ms} — длительность, "
                 "{n} — номер реплики.",
            foreground="#666666", wraplength=720,
            justify="left").grid(row=1, column=0, columnspan=3, sticky="w",
                                 pady=(4, 0))
        record_frame.columnconfigure(0, weight=1)

        # --- номер реплики ---
        number_frame = ttk.LabelFrame(body, text="Номер реплики ({n})",
                                      padding=8)
        number_frame.pack(fill="x", pady=(0, 8))
        self.number_enabled = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            number_frame, text="Подставлять номер реплики ({n})",
            variable=self.number_enabled).grid(row=0, column=0, sticky="w")
        ttk.Label(number_frame, text="Начальное значение:").grid(
            row=0, column=1, sticky="w", padx=(12, 0))
        self.number_start = tk.StringVar(value="1")
        tk.Spinbox(number_frame, from_=0, to=100000, width=7,
                   textvariable=self.number_start).grid(row=0, column=2,
                                                        sticky="w",
                                                        padx=(4, 12))
        ttk.Label(
            number_frame,
            text="Номер растёт на 1 с каждой строкой ТАБЛИЦЫ "
                 "(при нарезке реплики все её части делят один номер).",
            foreground="#666666").grid(row=0, column=3, sticky="w")

        # --- parts ---
        parts_frame = ttk.LabelFrame(
            body, text="Записи с переменными (parts)", padding=8)
        parts_frame.pack(fill="x", pady=(0, 8))
        ttk.Label(parts_frame, text="Строка parts:").grid(row=0, column=0,
                                                          sticky="w")
        self.parts_template = tk.StringVar(
            value=metadata_gen.DEFAULT_PARTS_TEMPLATE)
        ttk.Entry(parts_frame, textvariable=self.parts_template,
                  width=16).grid(row=0, column=1, sticky="w", padx=(4, 12))
        ttk.Label(parts_frame, text="Отступ:").grid(row=0, column=2,
                                                    sticky="w")
        self.parts_indent = tk.StringVar(value="12")
        tk.Spinbox(parts_frame, from_=0, to=40, width=5,
                   textvariable=self.parts_indent).grid(row=0, column=3,
                                                        sticky="w",
                                                        padx=(4, 12))
        ttk.Label(parts_frame, text="Отступ строк внутри parts:").grid(
            row=0, column=4, sticky="w")
        self.parts_content_indent = tk.StringVar(value="16")
        tk.Spinbox(parts_frame, from_=0, to=40, width=5,
                   textvariable=self.parts_content_indent).grid(
            row=0, column=5, sticky="w", padx=(4, 0))

        # --- переменные ---
        var_frame = ttk.LabelFrame(body, text="Переменные (нарезка по "
                                              "разметке)", padding=8)
        var_frame.pack(fill="x", pady=(0, 8))
        columns = ("marker", "seg_label", "placeholder", "name",
                   "template", "indent")
        headings = ("Маркер в имени", "Метка в .seg", "В тексте",
                    "Имя", "Шаблон строки", "Отступ")
        widths = (90, 110, 130, 110, 180, 50)
        tree_holder = ttk.Frame(var_frame)
        tree_holder.pack(fill="x")
        self.var_tree = ttk.Treeview(tree_holder, columns=columns,
                                     show="headings", height=4)
        for col, head, width in zip(columns, headings, widths):
            self.var_tree.heading(col, text=head)
            self.var_tree.column(col, width=width)
        var_scroll = ttk.Scrollbar(tree_holder, orient="vertical",
                                   command=self.var_tree.yview)
        self.var_tree.configure(yscrollcommand=var_scroll.set)
        self.var_tree.pack(side="left", fill="x", expand=True)
        var_scroll.pack(side="right", fill="y")

        var_btns = ttk.Frame(var_frame)
        var_btns.pack(fill="x", pady=(6, 0))
        ttk.Button(var_btns, text="Добавить",
                   command=self._add_variable).pack(side="left")
        ttk.Button(var_btns, text="Изменить",
                   command=self._edit_variable).pack(side="left", padx=6)
        ttk.Button(var_btns, text="Удалить",
                   command=self._delete_variable).pack(side="left")
        ttk.Label(
            var_frame,
            text="Если маркер встречается в имени файла, запись режется "
                 "по .seg-разметке: отрывки с заданной начальной меткой "
                 "вырезаются, куски сохраняются с индексами _1, _2, ..., "
                 "а запись оформляется как parts.",
            foreground="#666666", wraplength=720,
            justify="left").pack(fill="x", pady=(6, 0))

        for var in metadata_gen.default_variables():
            self._insert_variable(var)

        # --- предпросмотр ---
        preview_row = ttk.Frame(body)
        preview_row.pack(fill="x", pady=(0, 8))
        ttk.Button(preview_row, text="Предпросмотр",
                   command=self._preview).pack(side="left")
        ttk.Label(preview_row, text="строк:").pack(side="left",
                                                  padx=(12, 4))
        self.preview_rows = tk.StringVar(value="2")
        tk.Spinbox(preview_row, from_=1, to=100, width=5,
                   textvariable=self.preview_rows).pack(side="left")
        ttk.Label(preview_row,
                  text="как первые реплики таблицы будут выглядеть в "
                       "метаданных (без нарезки аудио)",
                  foreground="#666666").pack(side="left", padx=12)

        # --- запуск ---
        self.run_bar = RunBar(body, self.root, "Сгенерировать метаданные",
                              self._start)
        self.run_bar.pack(fill="x", pady=(0, 8))

        bottom = ttk.Frame(body)
        bottom.pack(fill="both", expand=True)
        self.log_panel = LogPanel(bottom, self.root, height=7)
        self.log_panel.pack(side="left", fill="both", expand=True,
                            padx=(0, 4))
        self.results = ResultsPanel(bottom, self.root, self.log_panel.log)
        self.results.pack(side="right", fill="both", expand=True,
                          padx=(4, 0))

    # ------------------------------------------------------------ диалоги
    def _browse_table(self):
        path = filedialog.askopenfilename(filetypes=[
            ("Таблицы", "*.xlsx *.xls *.csv"), ("Все файлы", "*.*")])
        if path:
            self.table_path.set(path)

    def _browse_output(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Текстовые файлы", "*.txt"),
                       ("Все файлы", "*.*")])
        if path:
            self.output_path.set(path)

    # -------------------------------------------------------- переменные
    def _insert_variable(self, values: dict):
        self._variables.append(dict(values))
        self.var_tree.insert("", "end", values=(
            values.get("marker", ""), values.get("seg_label", ""),
            values.get("placeholder", ""), values.get("name", ""),
            values.get("template", ""), values.get("indent", "")))

    def _selected_index(self):
        sel = self.var_tree.selection()
        if not sel:
            return None
        return self.var_tree.index(sel[0])

    def _add_variable(self):
        dialog = _VariableDialog(self)
        if dialog.result:
            self._insert_variable(dialog.result)

    def _edit_variable(self):
        idx = self._selected_index()
        if idx is None:
            return
        dialog = _VariableDialog(self, values=self._variables[idx])
        if dialog.result:
            self._variables[idx] = dict(dialog.result)
            iid = self.var_tree.get_children()[idx]
            values = dialog.result
            self.var_tree.item(iid, values=(
                values.get("marker", ""), values.get("seg_label", ""),
                values.get("placeholder", ""), values.get("name", ""),
                values.get("template", ""), values.get("indent", "")))

    def _delete_variable(self):
        idx = self._selected_index()
        if idx is None:
            return
        del self._variables[idx]
        self.var_tree.delete(self.var_tree.get_children()[idx])

    # ------------------------------------------------------- предпросмотр
    def _preview(self):
        table_path = self.table_path.get().strip()
        if not table_path or not os.path.isfile(table_path):
            messagebox.showerror("Ошибка",
                                 "Выберите файл таблицы (xlsx/csv)")
            return
        try:
            max_rows = int(self.preview_rows.get())
            if max_rows < 1:
                raise ValueError
        except ValueError:
            messagebox.showerror("Ошибка",
                                 "Число строк предпросмотра должно быть "
                                 "целым и не меньше 1")
            return
        try:
            cfg = self._collect_cfg(table_path, self.audio_dir.get(),
                                    self.output_path.get().strip()
                                    or "(предпросмотр)")
        except ValueError as e:
            messagebox.showerror("Ошибка", str(e))
            return

        self.root.config(cursor="watch")
        try:
            content = metadata_gen.preview_metadata(
                cfg, max_rows=max_rows, log=self.log_panel.log)
        except Exception as e:
            messagebox.showerror("Ошибка",
                                 f"Не удалось построить предпросмотр: {e}")
            return
        finally:
            self.root.config(cursor="")
        _PreviewDialog(self, content)

    # ------------------------------------------------------------ запуск
    def _start(self):
        table_path = self.table_path.get().strip()
        if not table_path or not os.path.isfile(table_path):
            messagebox.showerror("Ошибка", "Выберите файл таблицы "
                                           "(xlsx/csv)")
            self.run_bar.finish()
            return
        audio_dir = self.audio_dir.get()
        if not audio_dir or not os.path.isdir(audio_dir):
            messagebox.showerror("Ошибка", "Укажите папку с аудиофайлами")
            self.run_bar.finish()
            return
        output_path = self.output_path.get().strip()
        if not output_path:
            messagebox.showerror("Ошибка", "Укажите файл для сохранения "
                                           "метаданных (.txt)")
            self.run_bar.finish()
            return
        if self.voice_enabled.get() and not self.voice_line.get().strip():
            messagebox.showerror("Ошибка", "Строка голоса пуста — "
                                           "заполните её или снимите флажок")
            self.run_bar.finish()
            return
        try:
            cfg = self._collect_cfg(table_path, audio_dir, output_path)
        except ValueError as e:
            messagebox.showerror("Ошибка", str(e))
            self.run_bar.finish()
            return

        threading.Thread(target=self._worker, args=(cfg,),
                         daemon=True).start()

    def _collect_cfg(self, table_path, audio_dir, output_path) -> dict:
        def _int(var, name):
            try:
                return int(var.get())
            except ValueError:
                raise ValueError(f"«{name}» должен быть целым числом")

        return {
            "table_path": table_path,
            "audio_dir": audio_dir,
            "output_path": output_path,
            "output_audio_dir": self.output_audio_dir.get(),
            "text_column": self.text_col.get(),
            "filename_column": self.filename_col.get(),
            "intent_column": self.intent_col.get(),
            "voice_enabled": self.voice_enabled.get(),
            "voice_line": self.voice_line.get(),
            "voice_indent": _int(self.voice_indent, "Отступ голоса"),
            "intents_enabled": self.intents_enabled.get(),
            "intent_template": self.intent_template.get(),
            "intent_indent": _int(self.intent_indent, "Отступ интентов"),
            "record_template": self.record_template.get(),
            "record_indent": _int(self.record_indent, "Отступ записей"),
            "parts_template": self.parts_template.get(),
            "parts_indent": _int(self.parts_indent, "Отступ parts"),
            "parts_content_indent": _int(self.parts_content_indent,
                                         "Отступ строк parts"),
            "number_enabled": self.number_enabled.get(),
            "number_start": _int(self.number_start, "Начальный номер"),
            "variables": [dict(v) for v in self._variables],
        }

    def _worker(self, cfg):
        log = self.log_panel.log
        log(f"Старт генерации метаданных: таблица "
            f"{os.path.basename(cfg['table_path'])}, "
            f"переменных: {len(cfg['variables'])}")
        try:
            stats = metadata_gen.generate_metadata(
                cfg, log=log, progress=self.run_bar.set_progress,
                cancel_event=self.run_bar.cancel_event)
            out = stats["output_path"]
            info = (f"записей: {stats['records']}, "
                    f"предупреждений: {stats['warnings']}")
            self.root.after(0, lambda: self.results.add_result(out, info))
            for path in stats.get("created_files", []):
                self.root.after(0, lambda p=path: self.results.add_result(
                    p, "фрагмент"))
        except Exception as e:
            log(f"ОШИБКА: {e}")
        self.root.after(0, self._finish)

    def _finish(self):
        self.run_bar.finish()
        messagebox.showinfo("Готово", "Генерация метаданных завершена")

    # -------------------------------------------------------- настройки
    def get_settings(self) -> dict:
        return {
            "table_path": self.table_path.get(),
            "audio_dir": self.audio_dir.get(),
            "output_audio_dir": self.output_audio_dir.get(),
            "output_path": self.output_path.get(),
            "text_col": self.text_col.get(),
            "filename_col": self.filename_col.get(),
            "intent_col": self.intent_col.get(),
            "voice_enabled": self.voice_enabled.get(),
            "voice_line": self.voice_line.get(),
            "voice_indent": self.voice_indent.get(),
            "intents_enabled": self.intents_enabled.get(),
            "intent_template": self.intent_template.get(),
            "intent_indent": self.intent_indent.get(),
            "record_template": self.record_template.get(),
            "record_indent": self.record_indent.get(),
            "parts_template": self.parts_template.get(),
            "parts_indent": self.parts_indent.get(),
            "parts_content_indent": self.parts_content_indent.get(),
            "number_enabled": self.number_enabled.get(),
            "number_start": self.number_start.get(),
            "preview_rows": self.preview_rows.get(),
            "variables": [dict(v) for v in self._variables],
        }

    def apply_settings(self, s: dict):
        if not s:
            return
        for key, var in (
                ("table_path", self.table_path),
                ("output_path", self.output_path),
                ("text_col", self.text_col),
                ("filename_col", self.filename_col),
                ("intent_col", self.intent_col),
                ("voice_line", self.voice_line),
                ("voice_indent", self.voice_indent),
                ("intent_template", self.intent_template),
                ("intent_indent", self.intent_indent),
                ("record_template", self.record_template),
                ("record_indent", self.record_indent),
                ("parts_template", self.parts_template),
                ("parts_indent", self.parts_indent),
                ("parts_content_indent", self.parts_content_indent),
                ("number_start", self.number_start),
                ("preview_rows", self.preview_rows)):
            if s.get(key) not in (None, ""):
                var.set(s[key])
        for key, var in (("voice_enabled", self.voice_enabled),
                         ("intents_enabled", self.intents_enabled),
                         ("number_enabled", self.number_enabled)):
            if key in s:
                var.set(bool(s[key]))
        if s.get("audio_dir"):
            self.audio_dir.set(s["audio_dir"])
        if s.get("output_audio_dir"):
            self.output_audio_dir.set(s["output_audio_dir"])
        if isinstance(s.get("variables"), list):
            for iid in self.var_tree.get_children():
                self.var_tree.delete(iid)
            self._variables = []
            for var in s["variables"]:
                if isinstance(var, dict):
                    self._insert_variable(var)
