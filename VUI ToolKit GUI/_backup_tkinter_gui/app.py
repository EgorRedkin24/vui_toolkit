"""
Главное окно VUI ToolKit: семь вкладок — обработка аудио, VAD,
диаризация, склейка, TTS, поиск с разметкой и генерация метаданных.

Поддерживает тёмную тему, сохранение настроек между запусками
(режимы, токены и ключи) и drag-and-drop файлов (при наличии
пакета tkinterdnd2).
"""

import tkinter as tk
from tkinter import ttk

from core import settings as settings_mod
from gui import theme as theme_mod
from gui.widgets import HAS_DND
from gui.processing_tab import ProcessingTab
from gui.vad_tab import VadTab
from gui.tts_tab import TtsTab
from gui.search_tab import SearchTab
from gui.diarization_tab import DiarizationTab
from gui.merge_tab import MergeTab
from gui.metadata_tab import MetadataTab


class VUIToolKitApp:
    def __init__(self, root):
        self.root = root
        root.title("VUI ToolKit")
        root.geometry("1080x820")
        root.minsize(940, 680)

        self._settings = settings_mod.load_settings()
        # как и веб-версия, по умолчанию тёмная тема
        self._dark = tk.BooleanVar(
            value=self._settings.get("theme", "dark") != "light")
        theme_mod.apply_theme(root, dark=self._dark.get())

        header = ttk.Frame(root, padding=(14, 10, 14, 8))
        header.pack(fill="x")
        brand = ttk.Frame(header)
        brand.pack(side="left")
        ttk.Label(brand, text="VUI ",
                  font=("Segoe UI", 17, "bold")).pack(side="left")
        self._brand_label = ttk.Label(brand, text="ToolKit",
                                      font=("Segoe UI", 17, "bold"),
                                      foreground=theme_mod.current_theme()
                                      ["primary"])
        self._brand_label.pack(side="left")
        self._subtitle = ttk.Label(
            brand,
            text="Обработка аудио · VAD · Диаризация · Склейка · "
                 "TTS · Поиск и разметка · Метаданные",
            foreground=theme_mod.hint_color(),
            font=("Segoe UI", 9))
        self._subtitle.pack(side="left", padx=14, pady=(5, 0))

        self.theme_btn = ttk.Button(header, command=self._toggle_theme,
                                    width=18)
        self.theme_btn.pack(side="right", pady=(2, 0))
        self._update_theme_btn_text()

        # тонкая акцентная полоса под шапкой — как на сайте
        self._accent_line = tk.Frame(root, height=2,
                                     bg=theme_mod.current_theme()["primary"])
        self._accent_line.pack(fill="x")

        notebook = ttk.Notebook(root)
        notebook.pack(fill="both", expand=True, padx=10, pady=(6, 8))

        self.processing_tab = ProcessingTab(notebook, root)
        self.vad_tab = VadTab(notebook, root)
        self.tts_tab = TtsTab(notebook, root)
        self.search_tab = SearchTab(notebook, root)
        self.diarization_tab = DiarizationTab(notebook, root)
        self.merge_tab = MergeTab(notebook, root)
        self.metadata_tab = MetadataTab(notebook, root)

        notebook.add(self.processing_tab, text="  Обработка аудио  ")
        notebook.add(self.vad_tab, text="  VAD (Silero)  ")
        notebook.add(self.diarization_tab, text="  Диаризация  ")
        notebook.add(self.merge_tab, text="  Склейка аудио  ")
        notebook.add(self.tts_tab, text="  TTS  ")
        notebook.add(self.search_tab, text="  Поиск и разметка  ")
        notebook.add(self.metadata_tab, text="  Метаданные  ")

        self._tabs = {
            "processing": self.processing_tab,
            "vad": self.vad_tab,
            "tts": self.tts_tab,
            "search": self.search_tab,
            "diarization": self.diarization_tab,
            "merge": self.merge_tab,
            "metadata": self.metadata_tab,
        }

        # Применяем сохранённые настройки вкладок (тема уже применена выше)
        for key, tab in self._tabs.items():
            tab.apply_settings(self._settings.get(key, {}))

        if not HAS_DND:
            # Подсказка в лог первой вкладки
            self.processing_tab.log_panel.log(
                "Совет: установите пакет tkinterdnd2 "
                "(pip install tkinterdnd2), чтобы перетаскивать "
                "файлы мышью прямо в окно.")

        root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------------------------------------------------------- тема
    def _toggle_theme(self):
        self._dark.set(not self._dark.get())
        theme_mod.apply_theme(self.root, dark=self._dark.get())
        c = theme_mod.current_theme()
        self._brand_label.config(foreground=c["primary"])
        self._subtitle.config(foreground=c["hint"])
        self._accent_line.config(bg=c["primary"])
        self._update_theme_btn_text()

    def _update_theme_btn_text(self):
        self.theme_btn.config(
            text="☀ Светлая тема" if self._dark.get() else "🌙 Тёмная тема")

    # --------------------------------------------------------- настройки
    def _on_close(self):
        data = {"theme": "dark" if self._dark.get() else "light"}
        for key, tab in self._tabs.items():
            data[key] = tab.get_settings()
        settings_mod.save_settings(data)
        self.root.destroy()


def main():
    if HAS_DND:
        try:
            from tkinterdnd2 import TkinterDnD
            root = TkinterDnD.Tk()
        except Exception:
            root = tk.Tk()
    else:
        root = tk.Tk()
    VUIToolKitApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
