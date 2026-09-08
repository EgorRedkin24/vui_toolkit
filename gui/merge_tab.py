"""
Вкладка «Склейка аудио»: объединение нескольких записей в одну
с настраиваемой паузой между ними (0 — прямая склейка).
Порядок записей можно менять кнопками «Вверх»/«Вниз»,
файлы можно перетаскивать в список (drag-and-drop).
"""

import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from core.audio_io import (AUDIO_EXTENSIONS, SAVE_FORMATS,
                           collect_audio_files, is_audio_file)
from core.merge_audio import merge_audio_files
from gui.widgets import (DirectorySelector, LogPanel, ResultsPanel, RunBar,
                         HAS_DND, _parse_dropped_paths)

SR_CHOICES = ["как у первого файла", "8000", "16000", "24000", "44100",
              "48000"]


class MergeTab(ttk.Frame):
    def __init__(self, parent, root):
        super().__init__(parent, padding=10)
        self.root = root
        self._files = []
        self._build_ui()

    def _build_ui(self):
        # Список записей для склейки
        files_frame = ttk.LabelFrame(
            self, text="Записи для склейки (в порядке списка)", padding=8)
        files_frame.pack(fill="x", pady=(0, 8))

        list_frame = ttk.Frame(files_frame)
        list_frame.pack(side="left", fill="both", expand=True)
        self.files_listbox = tk.Listbox(list_frame, height=6,
                                        activestyle="none")
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical",
                                  command=self.files_listbox.yview)
        self.files_listbox.config(yscrollcommand=scrollbar.set)
        self.files_listbox.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        if HAS_DND:
            try:
                from tkinterdnd2 import DND_FILES
                self.files_listbox.drop_target_register(DND_FILES)
                self.files_listbox.dnd_bind("<<Drop>>", self._on_drop)
                files_frame.config(text="Записи для склейки (в порядке "
                                        "списка, можно перетащить файлы)")
            except (Exception,):
                pass

        btns = ttk.Frame(files_frame)
        btns.pack(side="right", fill="y", padx=(8, 0))
        ttk.Button(btns, text="Добавить файлы",
                   command=self._add_files).pack(fill="x", pady=2)
        ttk.Button(btns, text="Добавить папку",
                   command=self._add_folder).pack(fill="x", pady=2)
        ttk.Button(btns, text="Удалить",
                   command=self._remove_file).pack(fill="x", pady=2)
        ttk.Button(btns, text="Вверх",
                   command=lambda: self._move(-1)).pack(fill="x", pady=2)
        ttk.Button(btns, text="Вниз",
                   command=lambda: self._move(1)).pack(fill="x", pady=2)
        ttk.Button(btns, text="Очистить",
                   command=self._clear).pack(fill="x", pady=2)

        # Параметры склейки
        params_frame = ttk.LabelFrame(self, text="Параметры склейки",
                                      padding=8)
        params_frame.pack(fill="x", pady=(0, 8))
        ttk.Label(params_frame, text="Пауза между записями, с:").grid(
            row=0, column=0, sticky="w")
        self.pause_var = tk.StringVar(value="0")
        ttk.Entry(params_frame, textvariable=self.pause_var, width=8).grid(
            row=0, column=1, sticky="w", padx=(4, 14))
        ttk.Label(params_frame, text="Частота дискретизации:").grid(
            row=0, column=2, sticky="w")
        self.sr_var = tk.StringVar(value=SR_CHOICES[0])
        ttk.Combobox(params_frame, values=SR_CHOICES,
                     textvariable=self.sr_var, state="readonly",
                     width=20).grid(row=0, column=3, sticky="w", padx=(4, 0))
        ttk.Label(params_frame,
                  text="Пауза 0 — прямая склейка без тишины.",
                  foreground="#666666").grid(row=1, column=0, columnspan=4,
                                             sticky="w", pady=(6, 0))

        # Параметры сохранения
        save_frame = ttk.LabelFrame(self, text="Параметры сохранения аудио",
                                    padding=8)
        save_frame.pack(fill="x", pady=(0, 8))
        ttk.Label(save_frame, text="Имя файла:").grid(row=0, column=0,
                                                      sticky="w")
        self.filename_var = tk.StringVar(value="merged")
        ttk.Entry(save_frame, textvariable=self.filename_var, width=24).grid(
            row=0, column=1, sticky="w", padx=(4, 14))
        ttk.Label(save_frame, text="Формат:").grid(row=0, column=2,
                                                   sticky="w")
        self.format_var = tk.StringVar(value="WAV")
        self.format_combo = ttk.Combobox(
            save_frame, values=list(SAVE_FORMATS.keys()),
            textvariable=self.format_var, state="readonly", width=8)
        self.format_combo.grid(row=0, column=3, sticky="w", padx=(4, 14))
        self.format_combo.bind("<<ComboboxSelected>>", self._on_format_change)
        ttk.Label(save_frame, text="Разрядность:").grid(row=0, column=4,
                                                        sticky="w")
        self.subtype_var = tk.StringVar(value="PCM_16")
        self.subtype_combo = ttk.Combobox(
            save_frame, values=SAVE_FORMATS["WAV"]["subtypes"],
            textvariable=self.subtype_var, state="readonly", width=10)
        self.subtype_combo.grid(row=0, column=5, sticky="w", padx=(4, 0))

        self.output_dir = DirectorySelector(self)
        self.output_dir.pack(fill="x", pady=(0, 8))

        self.run_bar = RunBar(self, self.root, "Склеить", self._start)
        self.run_bar.pack(fill="x", pady=(0, 8))

        bottom = ttk.Frame(self)
        bottom.pack(fill="both", expand=True)
        self.log_panel = LogPanel(bottom, self.root)
        self.log_panel.pack(side="left", fill="both", expand=True,
                            padx=(0, 4))
        self.results = ResultsPanel(bottom, self.root, self.log_panel.log)
        self.results.pack(side="right", fill="both", expand=True,
                          padx=(4, 0))

    # --------------------------------------------------------- список
    def _add_files(self):
        paths = filedialog.askopenfilenames(
            filetypes=[("Аудиофайлы",
                        " ".join(f"*{e}" for e in AUDIO_EXTENSIONS)),
                       ("Все файлы", "*.*")])
        for p in paths:
            self._files.append(p)
        self._refresh()

    def _add_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self._files.extend(collect_audio_files(folder))
            self._refresh()

    def _on_drop(self, event):
        for p in _parse_dropped_paths(self.files_listbox, event.data):
            if os.path.isdir(p):
                self._files.extend(collect_audio_files(p))
            elif is_audio_file(p):
                self._files.append(p)
        self._refresh()

    def _remove_file(self):
        sel = self.files_listbox.curselection()
        if sel:
            del self._files[sel[0]]
            self._refresh()

    def _move(self, delta):
        sel = self.files_listbox.curselection()
        if not sel:
            return
        i, j = sel[0], sel[0] + delta
        if 0 <= j < len(self._files):
            self._files[i], self._files[j] = self._files[j], self._files[i]
            self._refresh()
            self.files_listbox.selection_set(j)

    def _clear(self):
        self._files.clear()
        self._refresh()

    def _refresh(self):
        self.files_listbox.delete(0, tk.END)
        for p in self._files:
            self.files_listbox.insert(tk.END, os.path.basename(p))

    def _on_format_change(self, event=None):
        fmt = self.format_var.get()
        subtypes = SAVE_FORMATS[fmt]["subtypes"]
        self.subtype_combo.config(values=subtypes)
        if subtypes:
            self.subtype_combo.config(state="readonly")
            if self.subtype_var.get() not in subtypes:
                self.subtype_var.set(subtypes[0])
        else:
            self.subtype_var.set("")
            self.subtype_combo.config(state="disabled")

    # --------------------------------------------------------- запуск
    def _start(self):
        if len(self._files) < 2:
            messagebox.showerror(
                "Ошибка", "Добавьте хотя бы две записи для склейки")
            self.run_bar.finish()
            return
        try:
            pause = float(self.pause_var.get().replace(",", "."))
            if pause < 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Ошибка", "Пауза — число >= 0 "
                                           "(0 — прямая склейка)")
            self.run_bar.finish()
            return
        out_dir = self.output_dir.get()
        if not out_dir:
            messagebox.showerror("Ошибка", "Укажите папку для сохранения")
            self.run_bar.finish()
            return
        filename = self.filename_var.get().strip()
        if not filename:
            messagebox.showerror("Ошибка", "Укажите имя итогового файла")
            self.run_bar.finish()
            return

        sr_choice = self.sr_var.get()
        target_sr = None if sr_choice == SR_CHOICES[0] else int(sr_choice)
        fmt = self.format_var.get()
        subtype = self.subtype_var.get()
        out_path = os.path.join(
            out_dir, filename + SAVE_FORMATS[fmt]["ext"])

        threading.Thread(target=self._worker,
                         args=(list(self._files), out_path, pause,
                               target_sr, fmt, subtype,
                               self.run_bar.cancel_event),
                         daemon=True).start()

    def _worker(self, files, out_path, pause, target_sr, fmt, subtype,
                cancel_event):
        log = self.log_panel.log
        log(f"Склейка {len(files)} записей, пауза: {pause} с"
            + (" (прямая склейка)" if pause == 0 else ""))
        try:
            result = merge_audio_files(files, out_path, pause_sec=pause,
                                       target_sr=target_sr, fmt=fmt,
                                       subtype=subtype or "PCM_16", log=log,
                                       cancel_event=cancel_event)
            if result:
                self.root.after(0, lambda p=result:
                                self.results.add_result(p, "итог"))
        except Exception as e:
            log(f"ОШИБКА: {e}")
        log("Склейка завершена.")
        self.root.after(0, self._finish)

    def _finish(self):
        self.run_bar.finish()
        messagebox.showinfo("Готово", "Склейка завершена")

    # ------------------------------------------------------------ настройки
    def get_settings(self) -> dict:
        return {
            "pause": self.pause_var.get(),
            "sr": self.sr_var.get(),
            "filename": self.filename_var.get(),
            "format": self.format_var.get(),
            "subtype": self.subtype_var.get(),
            "output_dir": self.output_dir.get(),
        }

    def apply_settings(self, s: dict):
        if not s:
            return
        self.pause_var.set(s.get("pause", "0"))
        if s.get("sr") in SR_CHOICES:
            self.sr_var.set(s["sr"])
        if s.get("filename"):
            self.filename_var.set(s["filename"])
        if s.get("format") in SAVE_FORMATS:
            self.format_var.set(s["format"])
            self._on_format_change()
        if s.get("subtype"):
            values = self.subtype_combo["values"]
            if s["subtype"] in values:
                self.subtype_var.set(s["subtype"])
        if s.get("output_dir"):
            self.output_dir.set(s["output_dir"])
