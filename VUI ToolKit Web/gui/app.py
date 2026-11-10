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
        root.geometry("1020x800")
        root.minsize(900, 660)

        self._settings = settings_mod.load_settings()
        self._dark = tk.BooleanVar(
            value=self._settings.get("theme", "light") == "dark")

        style = ttk.Style()
        for theme_name in ("clam", "vista", "default"):
            if theme_name in style.theme_names():
                style.theme_use(theme_name)
                break
        style.configure("TNotebook.Tab", padding=(14, 6),
                        font=("Segoe UI", 10))

        header = ttk.Frame(root, padding=(12, 8, 12, 0))
        header.pack(fill="x")
        ttk.Label(header, text="VUI ToolKit",
                  font=("Segoe UI", 16, "bold")).pack(side="left")
        ttk.Label(header,
                  text="Обработка аудио · VAD · Диаризация · Склейка · "
                       "TTS · Поиск и разметка · Метаданные",
                  foreground="#666666").pack(side="left", padx=12, pady=(4, 0))

        self.theme_btn = ttk.Button(header, command=self._toggle_theme,
                                    width=16)
        self.theme_btn.pack(side="right")
        self._update_theme_btn_text()

        notebook = ttk.Notebook(root)
        notebook.pack(fill="both", expand=True, padx=10, pady=8)

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

        # Применяем сохранённые настройки и тему
        for key, tab in self._tabs.items():
            tab.apply_settings(self._settings.get(key, {}))
        if self._dark.get():
            theme_mod.apply_theme(root, dark=True)

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
