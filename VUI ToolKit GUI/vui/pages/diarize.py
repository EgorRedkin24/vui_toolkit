"""Страница «Диаризация» — разметка спикеров (pyannote)."""

import flet as ft

from vui.colors import c
from vui.controls import AudioFilesPicker, OutputDirPicker, labeled, txt, \
    notice
from vui.pages.base import ToolPage
from vui import store


class DiarizePage(ToolPage):
    def __init__(self, page):
        super().__init__(
            page, "Диаризация",
            "Размечает, кто и когда говорит, и сохраняет .seg-файлы "
            "рядом с результатами.")
        self.page_ref = page

        self.files_picker = AudioFilesPicker(page, "Аудиофайлы")
        self.out_dir_picker = OutputDirPicker(page)
        self.hf_token = txt(store.load().get("hf_token", ""),
                            self._set_token, password=True)

        self.build_form([
            self.files_picker,
            labeled("Токен Hugging Face", self.hf_token,
                    hint="Нужен доступ к модели pyannote/speaker-diarization-3.1 "
                         "— получить на huggingface.co/settings/tokens"),
            notice("Первая загрузка модели может занять несколько минут.",
                   "warning"),
            self.out_dir_picker,
        ])

    def _set_token(self, v):
        self.hf_token_val = v

    @property
    def token(self):
        return getattr(self, "hf_token_val", self.hf_token.value) or ""

    def collect(self):
        files = self.files_picker.get_files()
        if not files:
            raise ValueError("Добавьте хотя бы один аудиофайл")
        if not self.token.strip():
            raise ValueError("Введите токен Hugging Face")
        return {"tool": "diarize", "files": files,
                "params": {"hf_token": self.token,
                           "output_dir": self.out_dir_picker.get_dir()}}
