"""
Вкладка «VAD (Silero)»: нарезка аудио на фрагменты речи или пауз
с ограничением длительности и сохранением таблицы длительностей.
"""

import os
import threading
import tkinter as tk
from tkinter import messagebox, ttk

from core.vad_silero import run_vad, save_durations_table
from gui.widgets import (AudioSourceSelector, DirectorySelector, LogPanel,
                         ResultsPanel, RunBar)


class VadTab(ttk.Frame):
    def __init__(self, parent, root):
        super().__init__(parent, padding=10)
        self.root = root
        self._build_ui()

    def _build_ui(self):
        self.source = AudioSourceSelector(self)
        self.source.pack(fill="x", pady=(0, 8))

        # Что сохраняем
        mode_frame = ttk.LabelFrame(self, text="Что сохранять", padding=8)
        mode_frame.pack(fill="x", pady=(0, 8))
        self.mode = tk.StringVar(value="speech")
        ttk.Radiobutton(mode_frame, text="Фрагменты речи",
                        variable=self.mode, value="speech").grid(
            row=0, column=0, sticky="w", padx=(0, 12))
        ttk.Radiobutton(mode_frame, text="Фрагменты без речи (паузы)",
                        variable=self.mode, value="silence").grid(
            row=0, column=1, sticky="w")

        # Параметры нарезки
        params_frame = ttk.LabelFrame(self, text="Параметры", padding=8)
        params_frame.pack(fill="x", pady=(0, 8))
        ttk.Label(params_frame, text="Мин. длительность, с:").grid(
            row=0, column=0, sticky="w")
        self.min_dur = tk.StringVar(value="1")
        ttk.Entry(params_frame, textvariable=self.min_dur, width=8).grid(
            row=0, column=1, sticky="w", padx=(4, 14))
        ttk.Label(params_frame, text="Макс. длительность, с:").grid(
            row=0, column=2, sticky="w")
        self.max_dur = tk.StringVar(value="4")
        ttk.Entry(params_frame, textvariable=self.max_dur, width=8).grid(
            row=0, column=3, sticky="w", padx=(4, 14))
        ttk.Label(params_frame, text="Порог VAD:").grid(
            row=0, column=4, sticky="w")
        self.threshold = tk.StringVar(value="0.7")
        ttk.Entry(params_frame, textvariable=self.threshold, width=8).grid(
            row=0, column=5, sticky="w", padx=(4, 0))
        ttk.Label(
            params_frame,
            text="Фрагменты длиннее максимума режутся на части, "
                 "короче минимума — отбрасываются.",
            foreground="#666666").grid(row=1, column=0, columnspan=6,
                                       sticky="w", pady=(6, 0))

        # Таблица длительностей
        table_frame = ttk.LabelFrame(self, text="Таблица длительностей",
                                     padding=8)
        table_frame.pack(fill="x", pady=(0, 8))
        ttk.Label(table_frame, text="Формат таблицы:").grid(row=0, column=0,
                                                            sticky="w")
        self.table_format = tk.StringVar(value="xlsx")
        ttk.Combobox(table_frame, values=["xlsx", "csv"],
                     textvariable=self.table_format,
                     state="readonly", width=8).grid(row=0, column=1,
                                                     sticky="w", padx=4)

        self.output_dir = DirectorySelector(self)
        self.output_dir.pack(fill="x", pady=(0, 8))

        self.run_bar = RunBar(self, self.root, "Запустить VAD", self._start)
        self.run_bar.pack(fill="x", pady=(0, 8))

        bottom = ttk.Frame(self)
        bottom.pack(fill="both", expand=True)
        self.log_panel = LogPanel(bottom, self.root)
        self.log_panel.pack(side="left", fill="both", expand=True,
                            padx=(0, 4))
        self.results = ResultsPanel(bottom, self.root, self.log_panel.log)
        self.results.pack(side="right", fill="both", expand=True,
                          padx=(4, 0))

    def _start(self):
        files = self.source.get_files()
        if not files:
            messagebox.showerror("Ошибка", "Выберите источник аудио")
            self.run_bar.finish()
            return
        out_dir = self.output_dir.get()
        if not out_dir:
            messagebox.showerror("Ошибка", "Укажите папку для сохранения")
            self.run_bar.finish()
            return
        try:
            min_dur = float(self.min_dur.get().replace(",", "."))
            max_dur = float(self.max_dur.get().replace(",", "."))
            threshold = float(self.threshold.get().replace(",", "."))
        except ValueError:
            messagebox.showerror("Ошибка",
                                 "Длительности и порог должны быть числами")
            self.run_bar.finish()
            return
        if not (0 < min_dur <= max_dur):
            messagebox.showerror(
                "Ошибка", "Нужно 0 < мин. длительность <= макс. длительность")
            self.run_bar.finish()
            return
        if not (0 < threshold < 1):
            messagebox.showerror("Ошибка", "Порог VAD должен быть между 0 и 1")
            self.run_bar.finish()
            return

        threading.Thread(
            target=self._worker,
            args=(files, out_dir, self.mode.get(), min_dur, max_dur,
                  threshold, self.table_format.get(),
                  self.run_bar.cancel_event),
            daemon=True).start()

    def _worker(self, files, out_dir, mode, min_dur, max_dur, threshold,
                table_format, cancel_event):
        log = self.log_panel.log
        mode_name = "речь" if mode == "speech" else "паузы (без речи)"
        log(f"Старт VAD: сохраняем «{mode_name}», файлов: {len(files)}, "
            f"длительность {min_dur}–{max_dur} с, порог {threshold}")
        try:
            rows = run_vad(files, out_dir, mode=mode, min_dur=min_dur,
                           max_dur=max_dur, threshold=threshold, log=log,
                           progress=self.run_bar.set_progress,
                           cancel_event=cancel_event)
            if rows:
                table_path = save_durations_table(rows, out_dir, table_format)
                log(f"Всего фрагментов: {len(rows)}")
                log(f"Таблица длительностей: {table_path}")
                for row in rows:
                    seg = row.get("segment_file", "")
                    dur = row.get("duration", 0)
                    if seg:
                        self.root.after(
                            0, lambda p=os.path.join(out_dir, seg), d=dur:
                            self.results.add_result(p, f"{d:.2f} с"))
            elif not cancel_event.is_set():
                log("Фрагментов не найдено — таблица не создана.")
        except Exception as e:
            log(f"ОШИБКА: {e}")
        log("VAD завершён.")
        self.root.after(0, self._finish)

    def _finish(self):
        self.run_bar.finish()
        messagebox.showinfo("Готово", "VAD-обработка завершена")

    # ------------------------------------------------------------ настройки
    def get_settings(self) -> dict:
        return {
            "mode": self.mode.get(),
            "min_dur": self.min_dur.get(),
            "max_dur": self.max_dur.get(),
            "threshold": self.threshold.get(),
            "table_format": self.table_format.get(),
            "source_mode": self.source.get_mode(),
            "output_dir": self.output_dir.get(),
        }

    def apply_settings(self, s: dict):
        if not s:
            return
        self.mode.set(s.get("mode", "speech"))
        self.min_dur.set(s.get("min_dur", "1"))
        self.max_dur.set(s.get("max_dur", "4"))
        self.threshold.set(s.get("threshold", "0.7"))
        if s.get("table_format") in ("xlsx", "csv"):
            self.table_format.set(s["table_format"])
        self.source.set_mode(s.get("source_mode", "file"))
        if s.get("output_dir"):
            self.output_dir.set(s["output_dir"])
