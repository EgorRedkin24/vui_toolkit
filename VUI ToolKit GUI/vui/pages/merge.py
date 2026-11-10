"""Страница «Склейка» — объединение записей в одну."""

import os

import flet as ft

from vui.colors import c
from vui.controls import labeled, seg, txt, drop, is_mounted, OutputDirPicker
from vui.pages.base import ToolPage
from core.audio_io import SAVE_FORMATS, is_audio_file


class MergePage(ToolPage):
    def __init__(self, page):
        super().__init__(
            page, "Склейка аудио",
            "Объединяет несколько записей в одну, с паузами между ними. "
            "Порядок файлов можно менять.")
        self.page_ref = page

        self.files = []
        self.list_col = ft.Column(spacing=4, tight=True)
        self.picker = ft.FilePicker(on_result=self._on_picked)

        pick_btn = ft.FilledTonalButton(
            "Добавить файлы…", icon=ft.Icons.UPLOAD_FILE,
            on_click=lambda _e: page.run_task(self._pick_async))
        clear_btn = ft.TextButton("Очистить", on_click=self._clear)

        self.pause = "0.0"
        self.use_sr = False
        self.target_sr = 16000
        self.output_name = "merged"
        self.format = "WAV"
        self.subtype = "PCM_16"
        self.out_dir_picker = OutputDirPicker(page)

        self.fmt_drop = drop([(k, k) for k in SAVE_FORMATS], "WAV",
                             self._set_format, width=110)
        self.sub_drop = drop(
            [(s, s) for s in SAVE_FORMATS["WAV"]["subtypes"]], "PCM_16",
            lambda v: setattr(self, "subtype", v), width=120)

        self.sr_row = ft.Row([
            seg([(str(s), f"{s} Гц") for s in
                 (8000, 16000, 22050, 44100, 48000)], "16000",
                lambda v: setattr(self, "target_sr", int(v))),
        ], visible=False)

        self.build_form([
            ft.Column([
                ft.Text("Файлы (сверху вниз — порядок склейки)", size=13,
                        weight=ft.FontWeight.W_600, color=c("fg")),
                ft.Row([pick_btn, clear_btn]),
                self.list_col,
            ], tight=True, spacing=8),
            labeled("Пауза между фрагментами, с",
                    txt("0.0", self._set_pause, width=90)),
            labeled("Частота дискретизации результата", ft.Column([
                seg([("keep", "Как у исходников"), ("set", "Задать")],
                    "keep", self._set_sr_mode),
                self.sr_row,
            ], tight=True, spacing=6)),
            labeled("Имя результата", txt("merged", self._set_name,
                                          width=220),
                    hint="Без расширения — добавится автоматически. "
                         "По умолчанию: merged"),
            labeled("Формат",
                    ft.Row([self.fmt_drop, self.sub_drop],
                           vertical_alignment=ft.CrossAxisAlignment.CENTER)),
            self.out_dir_picker,
        ])

    async def _pick_async(self):
        picked_files = await self.picker.pick_files(
            dialog_title="Выберите аудиофайлы", allow_multiple=True)
        for f in (picked_files or []):
            if f.path and is_audio_file(f.path) and f.path not in self.files:
                self.files.append(f.path)
        self._render()

    # ---------------------------------------------------------------------
    def _on_picked(self, e: ft.FilePickerResultEvent):
        for f in (e.files or []):
            if f.path and is_audio_file(f.path) and f.path not in self.files:
                self.files.append(f.path)
        self._render()

    def _clear(self, _e=None):
        self.files = []
        self._render()

    def _move(self, i, d):
        j = i + d
        if 0 <= j < len(self.files):
            self.files[i], self.files[j] = self.files[j], self.files[i]
            self._render()

    def _del(self, i):
        del self.files[i]
        self._render()

    def _render(self):
        self.list_col.controls.clear()
        if not self.files:
            self.list_col.controls.append(
                ft.Text("Файлы не выбраны", size=12, color=c("hint")))
        for i, path in enumerate(self.files):
            row = ft.Row([
                ft.Text(f"{i + 1}.", size=12, color=c("hint"), width=24),
                ft.Text(os.path.basename(path), size=13, color=c("fg"),
                        expand=True, selectable=True),
                ft.IconButton(ft.Icons.ARROW_UPWARD, icon_size=16,
                              on_click=lambda _e, idx=i: self._move(idx, -1)),
                ft.IconButton(ft.Icons.ARROW_DOWNWARD, icon_size=16,
                              on_click=lambda _e, idx=i: self._move(idx, +1)),
                ft.IconButton(ft.Icons.DELETE_OUTLINE, icon_size=16,
                              on_click=lambda _e, idx=i: self._del(idx)),
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=2)
            self.list_col.controls.append(row)
        if is_mounted(self.list_col):
            self.list_col.update()

    # ---------------------------------------------------------------------
    def _set_pause(self, v):
        self.pause = v

    def _set_sr_mode(self, v):
        self.use_sr = v == "set"
        self.sr_row.visible = self.use_sr
        if is_mounted(self.sr_row):
            self.sr_row.update()

    def _set_name(self, v):
        self.output_name = v

    def _set_format(self, fmt):
        self.format = fmt
        subs = SAVE_FORMATS[fmt]["subtypes"]
        self.sub_drop.options = [ft.dropdown.Option(s, s) for s in subs]
        self.sub_drop.value = subs[0] if subs else None
        self.subtype = subs[0] if subs else ""
        if is_mounted(self.sub_drop):
            self.sub_drop.update()

    def collect(self):
        if not self.files:
            raise ValueError("Добавьте хотя бы один аудиофайл")
        try:
            pause = float(str(self.pause).replace(",", "."))
        except ValueError:
            pause = 0.0
        return {"tool": "merge", "files": list(self.files), "params": {
            "pause_sec": pause,
            "target_sr": self.target_sr if self.use_sr else None,
            "output_name": (self.output_name or "merged").strip(),
            "format": self.format,
            "subtype": self.subtype or None,
            "output_dir": self.out_dir_picker.get_dir(),
        }}
