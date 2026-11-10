"""Общие элементы интерфейса Flet-версии (стиль веб-интерфейса)."""

import os

import flet as ft

from core.audio_io import AUDIO_EXTENSIONS, collect_audio_files, is_audio_file
from vui.colors import c


def card(control=None, title=None, padding=16, expand=False):
    """«Панель» как surface-panel на сайте: белая карточка с рамкой,
    скруглением и мягкой тенью (в духе современных voice-сервисов)."""
    col = ft.Column(spacing=10, tight=True)
    if title:
        col.controls.append(
            ft.Text(title, size=13, weight=ft.FontWeight.W_600, color=c("fg")))
    if control is not None:
        col.controls.append(control)
    return ft.Container(
        content=col, bgcolor=c("card"), border=ft.Border.all(1, c("border")),
        border_radius=14, padding=padding, expand=expand,
        shadow=ft.BoxShadow(blur_radius=18, color=c("shadow"),
                            offset=ft.Offset(0, 3)))


def labeled(label, control, hint=None):
    col = ft.Column([
        ft.Text(label, size=12, color=c("hint")),
        control,
    ], spacing=4)
    if hint:
        col.controls.append(ft.Text(hint, size=11, color=c("hint")))
    return col


def notice(text, tone="info"):
    colors = {"info": c("hint"), "warning": c("warning"),
              "error": c("destructive"), "success": c("success")}
    return ft.Container(
        content=ft.Text(text, size=12, color=colors.get(tone, c("hint"))),
        bgcolor=c("secondary"), border_radius=8, padding=10)


def seg(options, value, on_change, allow_multiple=False):
    """Сегментированный переключатель (как Segmented на сайте)."""
    btn = ft.SegmentedButton(
        segments=[ft.Segment(value=k, label=ft.Text(v))
                  for k, v in options],
        selected=[value] if not allow_multiple else list(value),
        allow_multiple_selection=allow_multiple,
        allow_empty_selection=False,
        style=ft.ButtonStyle(
            bgcolor={ft.ControlState.DEFAULT: c("secondary"),
                     ft.ControlState.SELECTED: c("accent")},
            color={ft.ControlState.DEFAULT: c("fg"),
                   ft.ControlState.SELECTED: c("fg")},
            side=ft.BorderSide(1, c("border")),
            shape=ft.RoundedRectangleBorder(radius=8)),
        on_change=lambda e: on_change(
            list(e.control.selected) if allow_multiple
            else e.control.selected[0]))
    return btn


def txt(value="", on_change=None, multiline=False, password=False,
        mono=False, width=None, min_lines=None, placeholder=None,
        read_only=False):
    t = ft.TextField(
        value=value,
        multiline=multiline,
        password=password,
        can_reveal_password=password,
        read_only=read_only,
        width=width,
        min_lines=min_lines,
        hint_text=placeholder,
        text_style=ft.TextStyle(
            font_family="Consolas" if mono else None, size=13),
        color=c("fg"),
        on_change=(lambda e: on_change(e.control.value)) if on_change
        else None,
    )
    return t


def num(value, on_change, width=90):
    return ft.TextField(
        value=str(value), width=width,
        input_filter=ft.NumbersOnlyInputFilter(),
        color=c("fg"),
        on_change=lambda e: on_change(e.control.value))


def drop(options, value, on_change, width=None):
    return ft.Dropdown(
        options=[ft.dropdown.Option(str(k), str(v)) for k, v in options],
        value=str(value), width=width,
        color=c("fg"),
        on_select=lambda e: on_change(e.control.value))


def switch(value, on_change, label=None):
    return ft.Row([
        ft.Switch(value=value,
                  on_change=lambda e: on_change(e.control.value)),
        ft.Text(label, size=13, color=c("fg")) if label else ft.Container(),
    ], vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=6)


def slider_row(value, minimum, maximum, divisions, fmt, on_change):
    label = ft.Text(fmt(value), size=12, color=c("fg"))

    def _ch(v):
        label.value = fmt(v)
        label.update()
        on_change(v)

    return ft.Column([
        label,
        ft.Slider(min=minimum, max=maximum, divisions=divisions,
                  value=value, on_change=lambda e: _ch(e.control.value)),
    ], spacing=0)


AUDIO_EXTS_PICKER = [e.lstrip(".") for e in AUDIO_EXTENSIONS]


class AudioFilesPicker(ft.Column):
    """
    Выбор аудиоисточника: одна запись / несколько / папка.
    Файлы берутся по исходным путям (копирование в задачу — на этапе запуска).
    """

    def __init__(self, page, title="Источник аудио"):
        super().__init__(spacing=8)
        self.page_ref = page
        self.mode = "files"
        self.files = []

        self.mode_seg = seg(
            [("file", "Одна запись"), ("files", "Несколько записей"),
             ("folder", "Папка")],
            "files", self._set_mode)

        self.summary = ft.Text("Файлы не выбраны", size=12, color=c("hint"),
                               expand=True)

        pick_btn = ft.FilledTonalButton("Выбрать…", icon=ft.Icons.UPLOAD_FILE,
                                        on_click=self._pick)
        clear_btn = ft.TextButton("Очистить", on_click=self._clear)

        self.picker = ft.FilePicker(on_result=self._on_result)

        self.controls = [
            ft.Text(title, size=13, weight=ft.FontWeight.W_600, color=c("fg")),
            self.mode_seg,
            ft.Row([pick_btn, clear_btn, self.summary],
                   vertical_alignment=ft.CrossAxisAlignment.CENTER),
        ]

    def _set_mode(self, mode):
        self.mode = mode
        self.files = []
        self._refresh()

    def _clear(self, _e=None):
        self.files = []
        self._refresh()

    def _pick(self, _e):
        # методы FilePicker в flet 1.0 асинхронные — запускаем через run_task
        self.page_ref.run_task(self._pick_async)

    async def _pick_async(self):
        if self.mode == "folder":
            # в flet 1.0 результат возвращается напрямую из await,
            # on_result при программном вызове не срабатывает
            path = await self.picker.get_directory_path(
                dialog_title="Выберите папку")
            self.files = collect_audio_files(path) if path else []
        else:
            picked_files = await self.picker.pick_files(
                dialog_title="Выберите аудиофайлы",
                allow_multiple=self.mode == "files",
                allowed_extensions=AUDIO_EXTS_PICKER)
            picked = [f.path for f in (picked_files or []) if f.path]
            if self.mode == "file":
                picked = picked[:1]
            self.files = [p for p in picked if is_audio_file(p)]
        self._refresh()

    def _on_result(self, e: ft.FilePickerResultEvent):
        # резервный путь (если результат придёт событием)
        if self.mode == "folder":
            if e.files and e.files[0].path:
                self.files = collect_audio_files(e.files[0].path)
        else:
            picked = [f.path for f in (e.files or []) if f.path]
            if self.mode == "file":
                picked = picked[:1]
            self.files = [p for p in picked if is_audio_file(p)]
        self._refresh()

    def _refresh(self):
        if not self.files:
            self.summary.value = "Файлы не выбраны"
        elif len(self.files) == 1:
            self.summary.value = os.path.basename(self.files[0])
        else:
            self.summary.value = f"Выбрано файлов: {len(self.files)}"
        self.summary.update()

    def get_files(self):
        return list(self.files)


class FilePickField(ft.Row):
    """Поле выбора одного файла с кнопкой Обзор.""" ""

    def __init__(self, page, label=None, extensions=None, on_change=None):
        super().__init__(vertical_alignment=ft.CrossAxisAlignment.CENTER,
                         spacing=8)
        self.page_ref = page
        self.on_change_cb = on_change
        self.path = None
        self._label = label or "Выберите файл"
        self.value_label = ft.Text("Не выбран", size=12, color=c("hint"),
                                   expand=True)
        self.picker = ft.FilePicker(on_result=self._on_result)
        exts = [e.lstrip(".") for e in (extensions or [])]
        self._exts = exts
        btn = ft.FilledTonalButton(
            "Обзор…", icon=ft.Icons.FILE_OPEN,
            on_click=lambda _e: page.run_task(self._pick_async))
        clear = ft.TextButton("Очистить", on_click=self._clear)
        self.controls = [btn, clear, self.value_label]

    async def _pick_async(self):
        picked_files = await self.picker.pick_files(
            dialog_title=self._label,
            allow_multiple=False, allowed_extensions=self._exts or None)
        files = [f.path for f in (picked_files or []) if f.path]
        self.path = files[0] if files else None
        self.value_label.value = (os.path.basename(self.path)
                                  if self.path else "Не выбран")
        if is_mounted(self.value_label):
            self.value_label.update()
        if self.on_change_cb:
            self.on_change_cb(self.path)

    def _clear(self, _e=None):
        self.path = None
        self.value_label.value = "Не выбран"
        self.value_label.update()
        if self.on_change_cb:
            self.on_change_cb(None)

    def _on_result(self, e: ft.FilePickerResultEvent):
        # резервный путь (если результат придёт событием)
        files = [f.path for f in (e.files or []) if f.path]
        self.path = files[0] if files else None
        self.value_label.value = (os.path.basename(self.path)
                                  if self.path else "Не выбран")
        if is_mounted(self.value_label):
            self.value_label.update()
        if self.on_change_cb:
            self.on_change_cb(self.path)

    def get(self):
        return self.path


def fmt_size(size: int) -> str:
    if size >= 1024 * 1024:
        return f"{size / 1024 / 1024:.1f} МБ"
    if size >= 1024:
        return f"{size / 1024:.1f} КБ"
    return f"{size} Б"


class OutputDirPicker(ft.Column):
    """
    Выбор папки для результатов: «Папка задачи» (по умолчанию) или
    своя папка на диске. get_dir() возвращает None для папки задачи.
    """

    def __init__(self, page, title="Куда сохранять результаты"):
        super().__init__(spacing=6)
        self.page_ref = page
        self.mode = "job"
        self.dir_path = None

        self.mode_seg = seg(
            [("job", "Папка задачи"), ("custom", "Своя папка")],
            "job", self._set_mode)
        self.pick_btn = ft.FilledTonalButton(
            "Выбрать папку…", icon=ft.Icons.FOLDER_OPEN,
            on_click=lambda _e: page.run_task(self._pick_async),
            visible=False)
        self.path_label = ft.Text(
            "По умолчанию: папка результатов задачи (см. панель справа)",
            size=12, color=c("hint"), expand=True)
        self.picker = ft.FilePicker(on_result=self._on_result)

        self.controls = [
            ft.Text(title, size=13, weight=ft.FontWeight.W_600,
                    color=c("fg")),
            self.mode_seg,
            ft.Row([self.pick_btn, self.path_label],
                   vertical_alignment=ft.CrossAxisAlignment.CENTER),
        ]

    def _set_mode(self, mode):
        self.mode = mode
        self.pick_btn.visible = mode == "custom"
        if mode == "custom" and not self.dir_path:
            self.path_label.value = "Папка не выбрана — будет использована " \
                                    "папка задачи"
        elif mode == "job":
            self.path_label.value = ("По умолчанию: папка результатов "
                                     "задачи (см. панель справа)")
        else:
            self.path_label.value = self.dir_path
        for ctrl in (self.pick_btn, self.path_label):
            if is_mounted(ctrl):
                ctrl.update()

    async def _pick_async(self):
        path = await self.picker.get_directory_path(
            dialog_title="Выберите папку для результатов")
        if path:
            self.dir_path = path
            self.path_label.value = path
            if is_mounted(self.path_label):
                self.path_label.update()

    def _on_result(self, e: ft.FilePickerResultEvent):
        # резервный путь (если результат придёт событием)
        path = getattr(e, "path", None)
        if path:
            self.dir_path = path
            self.path_label.value = path
            if is_mounted(self.path_label):
                self.path_label.update()

    def get_dir(self):
        """None — папка задачи; иначе абсолютный путь к своей папке."""
        if self.mode == "custom" and self.dir_path:
            return self.dir_path
        return None


def is_mounted(control) -> bool:
    """True, если контрол уже добавлен на страницу (control.page бросает
    RuntimeError, пока контрол не примонтирован)."""
    try:
        control.page
        return True
    except RuntimeError:
        return False
