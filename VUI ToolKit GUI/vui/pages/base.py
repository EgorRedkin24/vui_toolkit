"""Базовая страница инструмента: форма слева, панель задачи справа."""

import flet as ft

from vui.colors import c
from vui.jobpanel import JobPanel
from vui.controls import card


class ToolPage(ft.Row):
    """
    Общая разметка страницы инструмента (как на сайте):
    слева — скроллируемая карточка с формой, справа — панель задачи.
    Обе колонки скроллируются независимо — страницы с длинными
    формами (TTS, метаданные) листаются колесом мыши.
    """

    def __init__(self, page, title, description):
        # expand=True обязателен: без него Column-хост даёт Row бесконечную
        # высоту, ListView'ы не переполняются и колесо мыши не скроллит
        super().__init__(expand=True,
                         vertical_alignment=ft.CrossAxisAlignment.STRETCH,
                         spacing=16)
        self.page_ref = page
        self.panel = JobPanel(page)

        header = ft.Column([
            ft.Text(title, size=22, weight=ft.FontWeight.W_700, color=c("fg")),
            ft.Text(description, size=13, color=c("hint")),
        ], spacing=4)

        # Страница заполняет form_sections через build_form()
        self.form_sections = ft.Column(spacing=16, tight=True)

        self.run_btn = ft.FilledButton(
            "Запустить задачу", icon=ft.Icons.PLAY_ARROW,
            height=44,
            style=ft.ButtonStyle(
                shape=ft.StadiumBorder(),
                padding=ft.Padding.symmetric(horizontal=22, vertical=0)),
            on_click=self._run)

        left = ft.ListView(
            controls=[header, card(self.form_sections, padding=20)],
            expand=True, spacing=14)

        right = ft.ListView(
            controls=[
                ft.Row([self.run_btn],
                       alignment=ft.MainAxisAlignment.START),
                self.panel,
            ],
            width=420, spacing=10)

        self.controls = [left, right]

    # API для наследников -------------------------------------------------
    def build_form(self, sections):
        """sections — список контролов, которые лягут в карточку формы."""
        self.form_sections.controls.extend(sections)

    def collect(self):
        """Собирает параметры из полей формы. Бросает ValueError."""
        raise NotImplementedError

    # ---------------------------------------------------------------------
    def _run(self, _e):
        try:
            payload = self.collect()
        except ValueError as ex:
            self.page_ref.show_dialog(ft.SnackBar(
                content=ft.Text(str(ex), color=c("primary_fg")),
                bgcolor=c("destructive")))
            return
        # payload: dict с ключами tool/params/files/table/ref_audio/ref_files
        self.panel.submit(
            payload.pop("tool"), payload.pop("params"),
            files=payload.get("files"), table=payload.get("table"),
            ref_audio=payload.get("ref_audio"),
            ref_files=payload.get("ref_files"))
