"""Страница «Метаданные» — генератор metadata.txt из таблицы + .seg."""

import flet as ft

from vui.colors import c
from vui.controls import (AudioFilesPicker, FilePickField, OutputDirPicker,
                          labeled, seg, txt, drop, switch, notice,
                          is_mounted)
from vui.pages.base import ToolPage
from vui import runner, services
from core.metadata_gen import (default_variables, DEFAULT_RECORD_TEMPLATE,
                               DEFAULT_INTENT_TEMPLATE, DEFAULT_VOICE_LINE,
                               DEFAULT_PARTS_TEMPLATE, DEFAULT_VAR_TEMPLATE)


class _VarRow:
    """Одна кастомная переменная (маркер нарезки)."""

    def __init__(self, page, data, on_delete):
        self.data = data
        self.on_delete = on_delete
        self.marker = txt(data.get("marker", ""), self._set("marker"),
                          width=70)
        self.seg_label = txt(data.get("seg_label", ""),
                             self._set("seg_label"), width=160)
        self.placeholder = txt(data.get("placeholder", ""),
                               self._set("placeholder"), width=150)
        self.name = txt(data.get("name", ""), self._set("name"), width=150)
        self.template = txt(data.get("template", DEFAULT_VAR_TEMPLATE),
                            self._set("template"), width=260)
        self.indent = txt(str(data.get("indent", 16)),
                          lambda v: self.data.__setitem__(
                              "indent", _to_int(v, 16)), width=60)
        self.control = ft.Column([
            ft.Row([
                ft.IconButton(ft.Icons.DELETE_OUTLINE, icon_size=16,
                              tooltip="Удалить переменную",
                              on_click=lambda _e: on_delete(self)),
            ], alignment=ft.MainAxisAlignment.END),
            ft.Row([
                labeled("Маркер", self.marker),
                labeled("Метка в .seg", self.seg_label),
            ], vertical_alignment=ft.CrossAxisAlignment.END),
            ft.Row([
                labeled("Плейсхолдер в тексте", self.placeholder),
                labeled("Имя переменной", self.name),
            ], vertical_alignment=ft.CrossAxisAlignment.END),
            labeled("Шаблон строки", self.template),
            labeled("Отступ", self.indent),
            ft.Divider(color=c("border"), height=1),
        ], tight=True, spacing=6)

    def _set(self, key):
        return lambda v: self.data.__setitem__(key, v)


def _to_int(raw, default):
    try:
        return int(str(raw).strip())
    except (TypeError, ValueError):
        return default


class MetadataPage(ToolPage):
    def __init__(self, page):
        super().__init__(
            page, "Метаданные",
            "Собирает metadata.txt из таблицы реплик с нарезкой аудио "
            "по .seg-разметке и кастомными переменными.")
        self.page_ref = page

        # --- входные данные
        self.table_field = FilePickField(page, "Таблица реплик",
                                         extensions=["xlsx", "xls", "csv"])
        self.files_picker = AudioFilesPicker(page, "Аудиофайлы (.seg рядом)")
        self.out_dir_picker = OutputDirPicker(page)

        # --- колонки
        self.output_name = "meta.txt"
        self.text_column = "text"
        self.filename_column = "filename"
        self.intent_column = "intent"

        cols_row = ft.Row([
            labeled("Колонка текста", txt("text",
                                          lambda v: setattr(
                                              self, "text_column", v),
                                          width=110)),
            labeled("Колонка имени файла", txt("filename",
                                               lambda v: setattr(
                                                   self, "filename_column",
                                                   v), width=110)),
            labeled("Колонка интента", txt("intent",
                                           lambda v: setattr(
                                               self, "intent_column", v),
                                           width=110)),
        ], vertical_alignment=ft.CrossAxisAlignment.END)

        # --- голос
        self.voice_enabled = True
        self.voice_line = DEFAULT_VOICE_LINE
        self.voice_indent = "2"
        voice_sec = self._section(
            "Голос", [
                switch(True, lambda v: setattr(self, "voice_enabled",
                                               bool(v)), "Добавлять блок голоса"),
                labeled("Строка голоса",
                        txt(DEFAULT_VOICE_LINE, lambda v: setattr(
                            self, "voice_line", v), width=380)),
                labeled("Отступ", txt("2", lambda v: setattr(
                    self, "voice_indent", v), width=60)),
            ])

        # --- интенты
        self.intents_enabled = True
        self.intent_template = DEFAULT_INTENT_TEMPLATE
        self.intent_indent = "6"
        intent_sec = self._section(
            "Интенты", [
                switch(True, lambda v: setattr(self, "intents_enabled",
                                               bool(v)),
                       "Группировать записи по интентам"),
                labeled("Шаблон заголовка интента",
                        txt(DEFAULT_INTENT_TEMPLATE, lambda v: setattr(
                            self, "intent_template", v), width=220)),
                labeled("Отступ", txt("6", lambda v: setattr(
                    self, "intent_indent", v), width=60)),
            ])

        # --- запись
        self.record_template = DEFAULT_RECORD_TEMPLATE
        self.record_indent = "12"
        self.number_enabled = False
        self.number_start = "1"
        record_sec = self._section(
            "Запись", [
                labeled("Шаблон записи", txt(DEFAULT_RECORD_TEMPLATE,
                                             lambda v: setattr(
                                                 self, "record_template", v),
                                             width=520, mono=True)),
                ft.Row([
                    labeled("Отступ", txt("12", lambda v: setattr(
                        self, "record_indent", v), width=60)),
                    switch(False, lambda v: setattr(self, "number_enabled",
                                                    bool(v)),
                           "Нумеровать записи"),
                    labeled("Начать с", txt("1", lambda v: setattr(
                        self, "number_start", v), width=60)),
                ], vertical_alignment=ft.CrossAxisAlignment.END),
            ])

        # --- parts
        self.parts_template = DEFAULT_PARTS_TEMPLATE
        self.parts_indent = "12"
        self.parts_content_indent = "16"
        parts_sec = self._section(
            "Parts (нарезка по переменным)", [
                labeled("Шаблон заголовка", txt(DEFAULT_PARTS_TEMPLATE,
                                                lambda v: setattr(
                                                    self, "parts_template",
                                                    v), width=160)),
                ft.Row([
                    labeled("Отступ", txt("12", lambda v: setattr(
                        self, "parts_indent", v), width=60)),
                    labeled("Отступ содержимого", txt("16", lambda v:
                        setattr(self, "parts_content_indent", v), width=60)),
                ], vertical_alignment=ft.CrossAxisAlignment.END),
            ])

        # --- переменные
        self.var_rows = []
        self.vars_col = ft.Column(spacing=8, tight=True)
        add_var_btn = ft.OutlinedButton(
            "＋ Добавить переменную", icon=ft.Icons.ADD,
            on_click=self._add_var)
        vars_sec = self._section(
            "Кастомные переменные",
            [self.vars_col, add_var_btn,
             ft.Text("Маркер — текст в имени файла (например «cn»). Строки "
                     "таблицы с таким маркером режутся по .seg-меткам "
                     "seg_label, а плейсхолдеры в тексте заменяются "
                     "переменными.", size=11, color=c("hint"))])
        self._add_var()  # две переменные по умолчанию
        self._add_var()

        # --- предпросмотр
        self.preview_rows = "2"
        preview_btn = ft.OutlinedButton(
            "Предпросмотр", icon=ft.Icons.PREVIEW,
            on_click=self._preview)

        self.build_form([
            labeled("Таблица (xlsx/csv)", self.table_field,
                    hint="Обязательно. Столбец текста — по умолчанию «text»"),
            self.files_picker,
            labeled("Имя файла результатов", txt("meta.txt", lambda v:
                setattr(self, "output_name", v), width=160),
                    hint="Здесь расширение указывать нужно (.txt). "
                         "По умолчанию: meta.txt"),
            self.out_dir_picker,
            cols_row,
            voice_sec,
            intent_sec,
            record_sec,
            parts_sec,
            vars_sec,
            ft.Row([
                labeled("Строк в предпросмотре", txt("2", lambda v: setattr(
                    self, "preview_rows", v), width=60)),
                preview_btn,
            ], vertical_alignment=ft.CrossAxisAlignment.END),
        ])

    # ---------------------------------------------------------------------
    @staticmethod
    def _section(title, controls):
        return ft.ExpansionTile(
            title=ft.Text(title, size=13, color=c("fg")),
            subtitle=None,
            controls=[ft.Container(content=ft.Column(controls, tight=True,
                                                     spacing=8),
                                   padding=ft.Padding.only(left=12))],
            collapsed_text_color=c("hint"),
            text_color=c("fg"),
            bgcolor=c("card"),
            shape=ft.RoundedRectangleBorder(radius=8),
        )

    def _add_var(self, _e=None):
        data = dict(default_variables()[len(self.var_rows) %
                                        len(default_variables())])
        row = _VarRow(self.page_ref, data, self._del_var)
        self.var_rows.append(row)
        self.vars_col.controls.append(row.control)
        if is_mounted(self.vars_col):
            self.vars_col.update()

    def _del_var(self, row):
        if row in self.var_rows:
            self.var_rows.remove(row)
            self.vars_col.controls.remove(row.control)
            if is_mounted(self.vars_col):
                self.vars_col.update()

    # ---------------------------------------------------------------------
    def _params(self):
        return {
            "output_name": (self.output_name or "meta.txt").strip(),
            "output_dir": self.out_dir_picker.get_dir(),
            "text_column": self.text_column or "text",
            "filename_column": self.filename_column or "filename",
            "intent_column": self.intent_column or "intent",
            "voice_enabled": self.voice_enabled,
            "voice_line": self.voice_line,
            "voice_indent": _to_int(self.voice_indent, 2),
            "intents_enabled": self.intents_enabled,
            "intent_template": self.intent_template,
            "intent_indent": _to_int(self.intent_indent, 6),
            "record_template": self.record_template,
            "record_indent": _to_int(self.record_indent, 12),
            "parts_template": self.parts_template,
            "parts_indent": _to_int(self.parts_indent, 12),
            "parts_content_indent": _to_int(self.parts_content_indent, 16),
            "number_enabled": self.number_enabled,
            "number_start": _to_int(self.number_start, 1),
            "variables": [dict(r.data) for r in self.var_rows
                          if (r.data.get("marker") or "").strip()],
        }

    def collect(self):
        table = self.table_field.get()
        if not table:
            raise ValueError("Нужна таблица (xlsx/csv)")
        return {"tool": "metadata", "table": table,
                "files": self.files_picker.get_files(),
                "params": self._params()}

    # ---------------------------------------------------------------------
    def _preview(self, _e):
        table = self.table_field.get()
        if not table:
            self.page_ref.show_dialog(ft.SnackBar(ft.Text(
                "Сначала выберите таблицу.")))
            return
        params = self._params()
        job = runner.create_job("metadata-preview", params)
        staged = services.stage_file(job["id"], table)
        files = self.files_picker.get_files()
        if files:
            services.stage_files(job["id"], files)
        cfg = services.metadata_cfg(params, staged,
                                    runner.uploads_dir(job["id"]), job)
        max_rows = _to_int(self.preview_rows, 2)

        text = ft.TextField(value="Формирую предпросмотр…", multiline=True,
                            min_lines=16, max_lines=24, read_only=True,
                            text_style=ft.TextStyle(font_family="Consolas",
                                                    size=12),
                            color=c("fg"))

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("Предпросмотр метаданных", color=c("fg")),
            content=ft.Container(text, width=560),
            actions=[ft.TextButton("Закрыть", on_click=lambda _e: (
                setattr(dlg, "open", False), self.page_ref.update()))])
        self.page_ref.show_dialog(dlg)

        def work():
            try:
                # выход в отдельную папку, чтобы не писать в uploads
                import os
                cfg2 = dict(cfg)
                cfg2["output_path"] = os.path.join(
                    runner.outputs_dir(job["id"]), "preview_meta.txt")
                result = services.preview_metadata(job, cfg2, max_rows)
                text.value = result or "(пусто)"
            except Exception as ex:
                text.value = f"Ошибка предпросмотра: {ex}"
            text.update()

        import threading
        threading.Thread(target=work, daemon=True).start()
