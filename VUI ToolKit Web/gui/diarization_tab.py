"""
Вкладка «Диаризация»: разделение спикеров через pyannote.audio.
Результат (<имя>_dia.txt) по умолчанию сохраняется рядом с исходником,
либо в выбранную папку.
"""

import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from core.diarization import diarize_files, MODEL_NAME
from gui.widgets import (AudioSourceSelector, LogPanel, ResultsPanel, RunBar)


class DiarizationTab(ttk.Frame):
    def __init__(self, parent, root):
        super().__init__(parent, padding=10)
        self.root = root
        self._build_ui()

    def _build_ui(self):
        # Токен Hugging Face
        token_frame = ttk.LabelFrame(self, text="Hugging Face", padding=8)
        token_frame.pack(fill="x", pady=(0, 8))
        ttk.Label(token_frame, text="HF-токен:").grid(row=0, column=0,
                                                      sticky="w")
        self.hf_token = tk.StringVar()
        ttk.Entry(token_frame, textvariable=self.hf_token, width=55).grid(
            row=0, column=1, sticky="w", padx=(4, 0))
        ttk.Label(
            token_frame,
            text=f"Модель: {MODEL_NAME}. Токен нужен с принятой лицензией "
                 f"модели на huggingface.co. Токен сохраняется в настройках "
                 f"в открытом виде.",
            foreground="#666666").grid(row=1, column=0, columnspan=2,
                                       sticky="w", pady=(6, 0))

        self.source = AudioSourceSelector(self)
        self.source.pack(fill="x", pady=(0, 8))

        # Папка для результатов (необязательно)
        out_frame = ttk.LabelFrame(self, text="Папка для результатов",
                                   padding=8)
        out_frame.pack(fill="x", pady=(0, 8))
        self.use_source_dir = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            out_frame,
            text="Сохранять в папку исходных записей",
            variable=self.use_source_dir,
            command=self._on_out_mode_change).grid(row=0, column=0,
                                                   columnspan=3, sticky="w")
        ttk.Label(out_frame, text="Другая папка:").grid(row=1, column=0,
                                                        sticky="w",
                                                        pady=(6, 0))
        self.output_dir = tk.StringVar()
        self.output_entry = ttk.Entry(out_frame, textvariable=self.output_dir,
                                      width=55, state="disabled")
        self.output_entry.grid(row=1, column=1, sticky="w", padx=(4, 4),
                               pady=(6, 0))
        self.output_btn = ttk.Button(out_frame, text="Обзор...",
                                     command=self._browse_output,
                                     state="disabled")
        self.output_btn.grid(row=1, column=2, pady=(6, 0))
        ttk.Label(
            out_frame,
            text="Файл результата: <имя исходника>_dia.txt",
            foreground="#666666").grid(row=2, column=0, columnspan=3,
                                       sticky="w", pady=(6, 0))

        self.run_bar = RunBar(self, self.root, "Запустить диаризацию",
                              self._start)
        self.run_bar.pack(fill="x", pady=(0, 8))

        bottom = ttk.Frame(self)
        bottom.pack(fill="both", expand=True)
        self.log_panel = LogPanel(bottom, self.root)
        self.log_panel.pack(side="left", fill="both", expand=True,
                            padx=(0, 4))
        self.results = ResultsPanel(bottom, self.root, self.log_panel.log)
        self.results.pack(side="right", fill="both", expand=True,
                          padx=(4, 0))

    def _on_out_mode_change(self):
        state = "disabled" if self.use_source_dir.get() else "normal"
        self.output_entry.config(state=state)
        self.output_btn.config(state=state)

    def _browse_output(self):
        path = filedialog.askdirectory()
        if path:
            self.output_dir.set(path)

    def _start(self):
        token = self.hf_token.get().strip()
        if not token:
            messagebox.showerror("Ошибка", "Введите токен Hugging Face")
            self.run_bar.finish()
            return
        files = self.source.get_files()
        if not files:
            messagebox.showerror("Ошибка", "Выберите источник аудио")
            self.run_bar.finish()
            return
        out_dir = None
        if not self.use_source_dir.get():
            out_dir = self.output_dir.get().strip()
            if not out_dir:
                messagebox.showerror(
                    "Ошибка", "Укажите папку для результатов или включите "
                              "сохранение рядом с исходниками")
                self.run_bar.finish()
                return

        threading.Thread(target=self._worker,
                         args=(files, token, out_dir,
                               self.run_bar.cancel_event),
                         daemon=True).start()

    def _worker(self, files, token, out_dir, cancel_event):
        log = self.log_panel.log
        log("Модель pyannote при первом запуске скачивается — "
            "это может занять несколько минут.")
        try:
            results = diarize_files(files, token, out_dir, log=log,
                                    progress=self.run_bar.set_progress,
                                    cancel_event=cancel_event)
            log(f"Создано файлов: {len(results)}")
            for p in results:
                self.root.after(
                    0, lambda path=p: self.results.add_result(path, "txt"))
        except Exception as e:
            log(f"ОШИБКА: {e}")
        log("Диаризация завершена.")
        self.root.after(0, self._finish)

    def _finish(self):
        self.run_bar.finish()
        messagebox.showinfo("Готово", "Диаризация завершена")

    # ------------------------------------------------------------ настройки
    def get_settings(self) -> dict:
        return {
            "hf_token": self.hf_token.get(),
            "use_source_dir": self.use_source_dir.get(),
            "output_dir": self.output_dir.get(),
            "source_mode": self.source.get_mode(),
        }

    def apply_settings(self, s: dict):
        if not s:
            return
        self.hf_token.set(s.get("hf_token", ""))
        self.use_source_dir.set(s.get("use_source_dir", True))
        self.output_dir.set(s.get("output_dir", ""))
        self._on_out_mode_change()
        self.source.set_mode(s.get("source_mode", "file"))
