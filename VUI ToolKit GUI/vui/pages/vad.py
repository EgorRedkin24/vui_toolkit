"""Страница «VAD» — детекция речи/тишины (Silero)."""

import flet as ft

from vui.colors import c
from vui.controls import AudioFilesPicker, OutputDirPicker, labeled, seg, \
    txt, drop, slider_row
from vui.pages.base import ToolPage


class VadPage(ToolPage):
    def __init__(self, page):
        super().__init__(
            page, "VAD — детекция речи",
            "Находит речевые фрагменты или паузы и сохраняет таблицу "
            "длительностей (xlsx/csv).")
        self.page_ref = page

        self.files_picker = AudioFilesPicker(page, "Аудиофайлы")
        self.out_dir_picker = OutputDirPicker(page)
        self.table_name = "segments_durations"

        self.mode = "speech"
        self.min_dur = "1.0"
        self.max_dur = "4.0"
        self.threshold = 0.7
        self.table_format = "xlsx"

        mode_seg = seg([("speech", "Речь"), ("silence", "Тишина")],
                       "speech", self._set_mode)
        thr = slider_row(
            0.7, 0.1, 0.95, 85, lambda v: f"Порог: {v:.2f}",
            self._set_threshold)

        self.build_form([
            self.files_picker,
            labeled("Что искать", mode_seg),
            ft.Row([
                labeled("Мин. длительность, с", txt("1.0", self._min_dur,
                                                    width=90)),
                labeled("Макс. длительность, с", txt("4.0", self._max_dur,
                                                     width=90)),
            ], vertical_alignment=ft.CrossAxisAlignment.START),
            labeled("Уверенность детектора", thr),
            labeled("Формат таблицы",
                    drop([("xlsx", "XLSX"), ("csv", "CSV")], "xlsx",
                         lambda v: setattr(self, "table_format", v),
                         width=110)),
            labeled("Имя таблицы",
                    txt("segments_durations",
                        lambda v: setattr(self, "table_name", v), width=220),
                    hint="Без расширения — добавится автоматически "
                         "(.xlsx или .csv). По умолчанию: segments_durations"),
            self.out_dir_picker,
        ])

    def _set_mode(self, v):
        self.mode = v

    def _min_dur(self, v):
        self.min_dur = v

    def _max_dur(self, v):
        self.max_dur = v

    def _set_threshold(self, v):
        self.threshold = v

    @staticmethod
    def _f(raw, default):
        try:
            return float(str(raw).replace(",", "."))
        except (TypeError, ValueError):
            return default

    def collect(self):
        files = self.files_picker.get_files()
        if not files:
            raise ValueError("Добавьте хотя бы один аудиофайл")
        return {"tool": "vad", "files": files, "params": {
            "mode": self.mode,
            "min_dur": self._f(self.min_dur, 1.0),
            "max_dur": self._f(self.max_dur, 4.0),
            "threshold": self.threshold,
            "table_format": self.table_format,
            "table_name": (self.table_name or "segments_durations").strip(),
            "output_dir": self.out_dir_picker.get_dir(),
        }}
