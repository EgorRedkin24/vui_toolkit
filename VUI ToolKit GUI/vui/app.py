"""Точка входа Flet-приложения VUI ToolKit: тема, навигация, shell."""

import asyncio
import os
import sys

# чтобы запуск работал из любой cwd
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import flet as ft

from vui import colors, store, runner
from vui.colors import c
from vui.pages.process import ProcessPage
from vui.pages.vad import VadPage
from vui.pages.diarize import DiarizePage
from vui.pages.merge import MergePage
from vui.pages.tts import TtsPage
from vui.pages.search import SearchPage
from vui.pages.metadata import MetadataPage
from vui.pages.settings_page import SettingsPage


_NAV = [
    (ft.Icons.AUDIO_FILE_OUTLINED, ft.Icons.AUDIO_FILE, "Обработка"),
    (ft.Icons.GRAPHIC_EQ_OUTLINED, ft.Icons.GRAPHIC_EQ, "VAD"),
    (ft.Icons.RECORD_VOICE_OVER_OUTLINED, ft.Icons.RECORD_VOICE_OVER,
     "Диаризация"),
    (ft.Icons.CALL_MERGE_OUTLINED, ft.Icons.CALL_MERGE, "Склейка"),
    (ft.Icons.MIC_NONE, ft.Icons.MIC, "TTS"),
    (ft.Icons.SEARCH_OUTLINED, ft.Icons.SEARCH, "Поиск слов"),
    (ft.Icons.DESCRIPTION_OUTLINED, ft.Icons.DESCRIPTION, "Метаданные"),
    (ft.Icons.SETTINGS_OUTLINED, ft.Icons.SETTINGS, "Настройки"),
]


class _Fader(ft.Container):
    """Контейнер с плавным появлением контента (замена AnimatedSwitcher,
    который в Flutter ослабляет ограничения и ломает скролл-листы)."""

    def __init__(self):
        super().__init__(expand=True, animate_opacity=200)

    async def swap(self, control, delay: float = 0.09):
        self.opacity = 0
        self.content = control
        self.update()
        await asyncio.sleep(delay)
        self.opacity = 1
        self.update()


def _build_theme() -> ft.Theme:
    return ft.Theme(
        color_scheme=ft.ColorScheme(
            primary=c("primary"),
            on_primary=c("primary_fg"),
            surface=c("card"),
            on_surface=c("fg"),
            surface_container_highest=c("popover"),
            outline=c("border"),
        ),
        visual_density=ft.VisualDensity.COMFORTABLE,
    )


def _make_pages(page):
    return [ProcessPage(page), VadPage(page), DiarizePage(page),
            MergePage(page), TtsPage(page), SearchPage(page),
            MetadataPage(page), SettingsPage(page)]


def main(page: ft.Page):
    settings = store.load()
    state = {"dark": settings.get("theme", "dark") != "light",
             "index": 0}

    page.title = "VUI ToolKit"
    page.window.width = 1320
    page.window.height = 860
    page.window.min_width = 1100
    page.window.min_height = 700

    runner.cleanup_old_jobs()

    theme_fader = _Fader()   # плавное переключение темы
    page_fader = _Fader()    # плавное появление страницы при навигации

    def _toggle_theme(_e):
        state["dark"] = not state["dark"]
        data = store.load()
        data["theme"] = "dark" if state["dark"] else "light"
        store.save(data)
        shell = _build_shell()
        page.run_task(theme_fader.swap, shell)

    def _build_shell():
        dark = state["dark"]
        colors.set_dark(dark)
        page.theme_mode = ft.ThemeMode.DARK if dark else ft.ThemeMode.LIGHT
        page.theme = _build_theme()
        page.bgcolor = c("bg")

        pages = _make_pages(page)

        def _select(e):
            idx = e.control.selected_index
            state["index"] = idx
            page.run_task(page_fader.swap, pages[idx])

        theme_btn = ft.IconButton(
            ft.Icons.DARK_MODE if dark else ft.Icons.LIGHT_MODE,
            tooltip="Переключить тему", on_click=_toggle_theme)

        rail = ft.NavigationRail(
            extended=True,
            min_extended_width=200,
            bgcolor=c("card"),
            selected_index=state["index"],
            on_change=_select,
            indicator_color=c("accent"),
            label_type=ft.NavigationRailLabelType.ALL,
            destinations=[
                ft.NavigationRailDestination(
                    icon=icon, selected_icon=icon_sel, label=label)
                for icon, icon_sel, label in _NAV
            ],
        )

        topbar = ft.Container(
            content=ft.Row([
                ft.Row([
                    ft.Text("VUI ", size=17, weight=ft.FontWeight.W_700,
                            color=c("fg")),
                    ft.Text("ToolKit", size=17, weight=ft.FontWeight.W_700,
                            color=c("primary")),
                ], tight=True, spacing=0),
                ft.Container(expand=True),
                ft.Text("локальная студия аудио", size=12, color=c("hint")),
                theme_btn,
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
            padding=ft.Padding.symmetric(horizontal=18, vertical=10),
            bgcolor=c("card"),
            border=ft.Border(bottom=ft.BorderSide(1, c("border"))),
        )

        page_fader.content = pages[state["index"]]
        page_fader.opacity = 1

        return ft.Column([
            topbar,
            ft.Row([
                rail,
                ft.VerticalDivider(width=1, color=c("border")),
                ft.Container(page_fader, expand=True, padding=20),
            ], expand=True, spacing=0),
        ], expand=True, spacing=0)

    theme_fader.content = _build_shell()
    page.add(theme_fader)


if __name__ == "__main__":
    ft.run(main)
