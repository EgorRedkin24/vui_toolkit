"""Страница «Поиск слов» — Whisper + .seg-фрагменты."""

import flet as ft

from vui.colors import c
from vui.controls import AudioFilesPicker, OutputDirPicker, labeled, seg, \
    txt, drop, slider_row, switch, notice, is_mounted
from vui.pages.base import ToolPage


class SearchPage(ToolPage):
    def __init__(self, page):
        super().__init__(
            page, "Поиск слов в аудио",
            "Распознаёт речь (Whisper) и вырезает фрагменты с нужными "
            "словами в .seg-файлы.")
        self.page_ref = page

        self.files_picker = AudioFilesPicker(page, "Аудиофайлы")
        self.out_dir_picker = OutputDirPicker(page)

        self.words = []
        self.word_field = txt("", width=220,
                              on_change=lambda v: None,
                              placeholder="слово или фраза")
        self.word_field.on_submit = lambda e: self._add_word(None)
        add_btn = ft.FilledTonalButton("Добавить", icon=ft.Icons.ADD,
                                       on_click=self._add_word)
        self.chips_col = ft.Row(wrap=True, spacing=6, run_spacing=2)

        self.max_fragments = "1"
        self.model = "small"
        self.language = "ru"
        self.fuzzy = False
        self.similarity = 80  # проценты

        model_drop = drop(
            [("tiny", "tiny (быстро)"), ("base", "base"),
             ("small", "small"), ("medium", "medium (точно)")],
            "small", lambda v: setattr(self, "model", v), width=180)
        lang_drop = drop(
            [("ru", "Русский"), ("en", "Английский"), ("auto", "Авто")],
            "ru", lambda v: setattr(self, "language",
                                    None if v == "auto" else v), width=140)
        sim = slider_row(
            80, 50, 100, 50, lambda v: f"Схожесть: {v:.0f}%",
            lambda v: setattr(self, "similarity", v))

        self.build_form([
            self.files_picker,
            labeled("Слова для поиска", ft.Column([
                ft.Row([self.word_field, add_btn],
                       vertical_alignment=ft.CrossAxisAlignment.CENTER),
                self.chips_col,
            ], tight=True, spacing=6)),
            ft.Row([
                labeled("Модель Whisper", model_drop),
                labeled("Язык", lang_drop),
                labeled("Макс. фрагментов на слово",
                        txt("1", lambda v: setattr(self, "max_fragments", v),
                            width=70)),
            ], vertical_alignment=ft.CrossAxisAlignment.START),
            switch(False, lambda v: setattr(self, "fuzzy", bool(v)),
                   "Нечёткий поиск (похожие слова)"),
            labeled("Порог схожести", sim),
            notice("Поиск идёт локально — первая загрузка модели Whisper "
                   "займёт время.", "warning"),
            self.out_dir_picker,
        ])

    # ---------------------------------------------------------------------
    def _add_word(self, _e):
        w = (self.word_field.value or "").strip()
        if w and w not in self.words:
            self.words.append(w)
        self.word_field.value = ""
        if is_mounted(self.word_field):
            self.word_field.update()
        self._render_chips()

    def _del_word(self, w):
        self.words.remove(w)
        self._render_chips()

    def _render_chips(self):
        self.chips_col.controls.clear()
        for w in self.words:
            self.chips_col.controls.append(ft.Container(
                content=ft.Row([
                    ft.Text(w, size=12, color=c("fg")),
                    ft.IconButton(ft.Icons.CLOSE, icon_size=12,
                                  icon_color=c("hint"),
                                  on_click=lambda _e, word=w:
                                  self._del_word(word)),
                ], spacing=0, tight=True,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER),
                bgcolor=c("accent"), border_radius=14, padding=ft.padding.
                symmetric(horizontal=8)))
        if is_mounted(self.chips_col):
            self.chips_col.update()

    # ---------------------------------------------------------------------
    def collect(self):
        files = self.files_picker.get_files()
        if not files:
            raise ValueError("Добавьте хотя бы один аудиофайл")
        if not self.words:
            raise ValueError("Добавьте хотя бы одно слово для поиска")
        try:
            max_frag = int(self.max_fragments)
        except (TypeError, ValueError):
            max_frag = 1
        return {"tool": "search", "files": files, "params": {
            "words": list(self.words),
            "max_fragments": max(1, max_frag),
            "model": self.model,
            "language": self.language or None,
            "fuzzy": self.fuzzy,
            "similarity": self.similarity / 100.0,
            "output_dir": self.out_dir_picker.get_dir(),
        }}
