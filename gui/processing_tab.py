"""
Вкладка «Обработка аудио»: пресеты (встроенные и пользовательские),
конструктор пайплайна, предпрослушивание «до/после», раздельная тишина,
защита от перезаписи, прогресс и прерывание, панель результатов.
"""

import os
import tempfile
import threading
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

from core.audio_io import (SAVE_FORMATS, DEFAULT_FORMAT, DEFAULT_SUBTYPE,
                           load_audio, save_audio, get_output_path,
                           unique_path)
from core.effects import EFFECTS, PRESETS, apply_pipeline
from core.presets import (load_user_presets, save_user_preset,
                          delete_user_preset)
from core import playback
from gui.widgets import (AudioSourceSelector, DirectorySelector, LogPanel,
                         ResultsPanel, RunBar)

_USER_PREFIX = "★ "  # пометка пользовательских пресетов в списке


class ProcessingTab(ttk.Frame):
    def __init__(self, parent, root):
        super().__init__(parent, padding=10)
        self.root = root
        self.pipeline_steps = []
        self._preview_original = None
        self._preview_processed = None
        self._build_ui()

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        self.source = AudioSourceSelector(self)
        self.source.pack(fill="x", pady=(0, 8))

        # Режим: пресет или свой пайплайн
        mode_frame = ttk.LabelFrame(self, text="Режим обработки", padding=8)
        mode_frame.pack(fill="x", pady=(0, 8))
        self.mode = tk.StringVar(value="preset")
        ttk.Radiobutton(mode_frame, text="Готовый пресет",
                        variable=self.mode, value="preset",
                        command=self._on_mode_change).grid(
            row=0, column=0, sticky="w", padx=(0, 12))
        ttk.Radiobutton(mode_frame, text="Свой пайплайн",
                        variable=self.mode, value="pipeline",
                        command=self._on_mode_change).grid(
            row=0, column=1, sticky="w")

        self.mode_container = ttk.Frame(mode_frame)
        self.mode_container.grid(row=1, column=0, columnspan=2,
                                 sticky="nsew", pady=(8, 0))
        mode_frame.columnconfigure(1, weight=1)

        self._build_preset_ui()
        self._build_pipeline_ui()
        self._on_mode_change()

        # Предпрослушивание
        preview_frame = ttk.LabelFrame(
            self, text="Предпрослушивание (первый выбранный файл)",
            padding=8)
        preview_frame.pack(fill="x", pady=(0, 8))
        self.preview_btn = ttk.Button(preview_frame, text="Подготовить",
                                      command=self._start_preview)
        self.preview_btn.pack(side="left")
        self.play_orig_btn = ttk.Button(preview_frame, text="▶ Оригинал",
                                        command=self._play_original,
                                        state="disabled")
        self.play_orig_btn.pack(side="left", padx=(10, 4))
        self.play_proc_btn = ttk.Button(preview_frame,
                                        text="▶ После обработки",
                                        command=self._play_processed,
                                        state="disabled")
        self.play_proc_btn.pack(side="left", padx=(0, 4))
        ttk.Button(preview_frame, text="■ Стоп",
                   command=playback.stop).pack(side="left")
        ttk.Label(preview_frame,
                  text="Сравните версию до и после применения пайплайна.",
                  foreground="#666666").pack(side="left", padx=12)

        # Параметры сохранения
        save_frame = ttk.LabelFrame(self, text="Параметры сохранения аудио",
                                    padding=8)
        save_frame.pack(fill="x", pady=(0, 8))
        ttk.Label(save_frame, text="Формат:").grid(row=0, column=0, sticky="w")
        self.format_var = tk.StringVar(value=DEFAULT_FORMAT)
        self.format_combo = ttk.Combobox(
            save_frame, values=list(SAVE_FORMATS.keys()),
            textvariable=self.format_var, state="readonly", width=8)
        self.format_combo.grid(row=0, column=1, sticky="w", padx=(4, 14))
        self.format_combo.bind("<<ComboboxSelected>>", self._on_format_change)

        ttk.Label(save_frame, text="Разрядность:").grid(row=0, column=2,
                                                        sticky="w")
        self.subtype_var = tk.StringVar(value=DEFAULT_SUBTYPE)
        self.subtype_combo = ttk.Combobox(
            save_frame, values=SAVE_FORMATS[DEFAULT_FORMAT]["subtypes"],
            textvariable=self.subtype_var, state="readonly", width=10)
        self.subtype_combo.grid(row=0, column=3, sticky="w", padx=(4, 0))
        self._on_format_change()

        self.keep_names_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            save_frame,
            text="Сохранить исходные названия (иначе добавляется "
                 "постфикс «_processed»)",
            variable=self.keep_names_var).grid(row=1, column=0, columnspan=4,
                                               sticky="w", pady=(6, 0))

        self.output_dir = DirectorySelector(self)
        self.output_dir.pack(fill="x", pady=(0, 8))

        # Запуск / прерывание / прогресс
        self.run_bar = RunBar(self, self.root, "Запустить обработку",
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

    # ------------------------------------------------------- пресеты
    def _build_preset_ui(self):
        self.preset_frame = ttk.Frame(self.mode_container)

        row1 = ttk.Frame(self.preset_frame)
        row1.pack(fill="x")
        ttk.Label(row1, text="Пресет:").pack(side="left")
        self.preset_var = tk.StringVar()
        self.preset_combo = ttk.Combobox(row1, textvariable=self.preset_var,
                                         state="readonly", width=30)
        self.preset_combo.pack(side="left", padx=8)
        self._refresh_preset_list()

        row2 = ttk.Frame(self.preset_frame)
        row2.pack(fill="x", pady=(6, 0))
        ttk.Button(row2, text="Редактировать",
                   command=self._edit_preset).pack(side="left")
        ttk.Button(row2, text="Удалить",
                   command=self._delete_preset).pack(side="left", padx=6)
        ttk.Label(row2, text="★ — пользовательские пресеты",
                  foreground="#666666").pack(side="left", padx=10)

    def _all_presets(self) -> dict:
        """Все пресеты: встроенные + пользовательские (с пометкой ★)."""
        result = {name: steps for name, steps in PRESETS.items()}
        for name, steps in load_user_presets().items():
            result[_USER_PREFIX + name] = steps
        return result

    def _refresh_preset_list(self, keep_selection: bool = True):
        current = self.preset_var.get() if keep_selection else ""
        values = list(self._all_presets().keys())
        self.preset_combo.config(values=values)
        if current in values:
            self.preset_var.set(current)
        elif values:
            self.preset_var.set(values[0])

    def _edit_preset(self):
        """Загружает выбранный пресет в конструктор пайплайна."""
        name = self.preset_var.get()
        steps = self._all_presets().get(name)
        if not steps:
            return
        import copy
        self.pipeline_steps = copy.deepcopy(steps)
        self._refresh_pipeline()
        self.mode.set("pipeline")
        self._on_mode_change()
        self.log_panel.log(
            f"Пресет «{name}» загружен в конструктор. Отредактируйте шаги "
            f"и нажмите «Сохранить как пресет».")

    def _delete_preset(self):
        name = self.preset_var.get()
        if not name.startswith(_USER_PREFIX):
            messagebox.showinfo("Нельзя удалить",
                                "Встроенные пресеты удалять нельзя. "
                                "Удалять можно только свои (с ★).")
            return
        if messagebox.askyesno("Удаление",
                               f"Удалить пресет «{name[len(_USER_PREFIX):]}»?"):
            delete_user_preset(name[len(_USER_PREFIX):])
            self._refresh_preset_list(keep_selection=False)
            self.log_panel.log(f"Пресет «{name}» удалён.")

    def _save_pipeline_as_preset(self):
        if not self.pipeline_steps:
            messagebox.showerror("Ошибка",
                                 "Пайплайн пуст — нечего сохранять.")
            return
        name = simpledialog.askstring(
            "Сохранение пресета", "Название пресета:", parent=self.root)
        if not name or not name.strip():
            return
        name = name.strip().lstrip(_USER_PREFIX)
        if name in PRESETS:
            messagebox.showerror(
                "Ошибка", f"«{name}» — имя встроенного пресета. "
                          f"Выберите другое имя.")
            return
        exists = name in load_user_presets()
        if exists and not messagebox.askyesno(
                "Перезапись", f"Пресет «{name}» уже существует. Заменить?"):
            return
        import copy
        if save_user_preset(name, copy.deepcopy(self.pipeline_steps)):
            self._refresh_preset_list()
            self.preset_var.set(_USER_PREFIX + name)
            self.log_panel.log(f"Пресет «{name}» сохранён.")
        else:
            messagebox.showerror("Ошибка", "Не удалось сохранить пресет.")

    # ------------------------------------------------------- пайплайн
    def _build_pipeline_ui(self):
        self.pipeline_frame = ttk.Frame(self.mode_container)

        # Тишина в начале и в конце: два независимых флажка
        silence_frame = ttk.Frame(self.pipeline_frame)
        silence_frame.pack(fill="x", pady=(0, 6))

        self.silence_start_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(silence_frame, text="Тишина в начале, с:",
                        variable=self.silence_start_var,
                        command=self._on_silence_toggle).grid(
            row=0, column=0, sticky="w")
        self.silence_start_dur = tk.StringVar(value="0.2")
        self.silence_start_entry = ttk.Entry(
            silence_frame, textvariable=self.silence_start_dur,
            width=6, state="disabled")
        self.silence_start_entry.grid(row=0, column=1, sticky="w",
                                      padx=(4, 16))

        self.silence_end_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(silence_frame, text="Тишина в конце, с:",
                        variable=self.silence_end_var,
                        command=self._on_silence_toggle).grid(
            row=0, column=2, sticky="w")
        self.silence_end_dur = tk.StringVar(value="0.2")
        self.silence_end_entry = ttk.Entry(
            silence_frame, textvariable=self.silence_end_dur,
            width=6, state="disabled")
        self.silence_end_entry.grid(row=0, column=3, sticky="w", padx=(4, 0))

        ttk.Label(silence_frame,
                  text="Тишина добавляется первым/последним шагом пайплайна.",
                  foreground="#666666").grid(row=1, column=0, columnspan=4,
                                             sticky="w", pady=(4, 0))

        list_frame = ttk.Frame(self.pipeline_frame)
        list_frame.pack(fill="both", expand=True)
        self.pipeline_listbox = tk.Listbox(list_frame, height=6,
                                           activestyle="none")
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical",
                                  command=self.pipeline_listbox.yview)
        self.pipeline_listbox.config(yscrollcommand=scrollbar.set)
        self.pipeline_listbox.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        btns = ttk.Frame(self.pipeline_frame)
        btns.pack(side="right", fill="y", padx=(8, 0))
        ttk.Button(btns, text="Добавить эффект",
                   command=self._add_step).pack(fill="x", pady=2)
        ttk.Button(btns, text="Удалить",
                   command=self._remove_step).pack(fill="x", pady=2)
        ttk.Button(btns, text="Вверх",
                   command=lambda: self._move_step(-1)).pack(fill="x", pady=2)
        ttk.Button(btns, text="Вниз",
                   command=lambda: self._move_step(1)).pack(fill="x", pady=2)
        ttk.Button(btns, text="Очистить",
                   command=self._clear_steps).pack(fill="x", pady=2)
        ttk.Button(btns, text="Сохранить как пресет",
                   command=self._save_pipeline_as_preset).pack(fill="x",
                                                               pady=(10, 2))

    def _on_mode_change(self):
        if self.mode.get() == "preset":
            self.pipeline_frame.pack_forget()
            self.preset_frame.pack(fill="x")
        else:
            self.preset_frame.pack_forget()
            self.pipeline_frame.pack(fill="both", expand=True)

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

    def _on_silence_toggle(self):
        self.silence_start_entry.config(
            state="normal" if self.silence_start_var.get() else "disabled")
        self.silence_end_entry.config(
            state="normal" if self.silence_end_var.get() else "disabled")

    # -------------------------------------------------------- конструктор
    def _add_step(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("Добавить эффект")
        dialog.geometry("460x360")
        dialog.transient(self.root)
        dialog.grab_set()

        ttk.Label(dialog, text="Эффект:").pack(anchor="w", padx=10,
                                               pady=(10, 0))
        effect_ids = list(EFFECTS.keys())
        titles = [EFFECTS[e]["title"] for e in effect_ids]
        effect_var = tk.StringVar(value=titles[0])
        combo = ttk.Combobox(dialog, values=titles, textvariable=effect_var,
                             state="readonly", width=45)
        combo.pack(fill="x", padx=10, pady=(2, 6))

        note_label = ttk.Label(dialog, text="", foreground="#886600")
        note_label.pack(anchor="w", padx=10)

        params_frame = ttk.Frame(dialog)
        params_frame.pack(fill="both", expand=True, padx=10, pady=6)
        param_vars = {}

        def update_params(event=None):
            for w in params_frame.winfo_children():
                w.destroy()
            param_vars.clear()
            effect_id = effect_ids[titles.index(effect_var.get())]
            spec = EFFECTS[effect_id]
            note_label.config(text=spec.get("note", ""))
            for row, (pname, pspec) in enumerate(spec["params"].items()):
                ttk.Label(params_frame,
                          text=f"{pspec['label']}:").grid(
                    row=row, column=0, sticky="w", pady=2)
                var = tk.StringVar(value=str(pspec["default"]))
                ttk.Entry(params_frame, textvariable=var, width=12).grid(
                    row=row, column=1, sticky="w", padx=6, pady=2)
                param_vars[pname] = (var, pspec["type"])

        combo.bind("<<ComboboxSelected>>", update_params)
        update_params()

        def on_ok():
            effect_id = effect_ids[titles.index(effect_var.get())]
            params = {}
            for pname, (var, ptype) in param_vars.items():
                try:
                    params[pname] = ptype(var.get())
                except ValueError:
                    messagebox.showerror(
                        "Ошибка",
                        f"Некорректное значение параметра «{pname}»",
                        parent=dialog)
                    return
            self.pipeline_steps.append({"effect": effect_id,
                                        "params": params})
            self._refresh_pipeline()
            dialog.destroy()

        btns = ttk.Frame(dialog)
        btns.pack(pady=10)
        ttk.Button(btns, text="Добавить", command=on_ok).pack(
            side="left", padx=5)
        ttk.Button(btns, text="Отмена", command=dialog.destroy).pack(
            side="left", padx=5)

    def _remove_step(self):
        sel = self.pipeline_listbox.curselection()
        if sel:
            del self.pipeline_steps[sel[0]]
            self._refresh_pipeline()

    def _move_step(self, delta: int):
        sel = self.pipeline_listbox.curselection()
        if not sel:
            return
        i = sel[0]
        j = i + delta
        if 0 <= j < len(self.pipeline_steps):
            self.pipeline_steps[i], self.pipeline_steps[j] = \
                self.pipeline_steps[j], self.pipeline_steps[i]
            self._refresh_pipeline()
            self.pipeline_listbox.selection_set(j)

    def _clear_steps(self):
        self.pipeline_steps.clear()
        self._refresh_pipeline()

    def _refresh_pipeline(self):
        self.pipeline_listbox.delete(0, tk.END)
        for step in self.pipeline_steps:
            title = EFFECTS[step["effect"]]["title"]
            params = ", ".join(f"{k}={v}" for k, v in step["params"].items())
            text = f"{title} ({params})" if params else title
            self.pipeline_listbox.insert(tk.END, text)

    # -------------------------------------------------- сборка шагов
    def _collect_steps(self):
        """Собирает итоговый список шагов (пресет/пайплайн + тишина)."""
        if self.mode.get() == "preset":
            steps = list(self._all_presets().get(self.preset_var.get(), []))
            description = f"пресет «{self.preset_var.get()}»"
        else:
            steps = list(self.pipeline_steps)
            description = "свой пайплайн"

        def _parse_duration(var, name):
            try:
                value = float(var.get().replace(",", "."))
                if value < 0:
                    raise ValueError
                return value
            except ValueError:
                messagebox.showerror("Ошибка",
                                     f"Длительность ({name}) — число >= 0")
                return None

        if self.silence_start_var.get():
            dur = _parse_duration(self.silence_start_dur, "тишина в начале")
            if dur is None:
                return None, None
            steps.insert(0, {"effect": "add_silence_start",
                             "params": {"duration": dur}})
        if self.silence_end_var.get():
            dur = _parse_duration(self.silence_end_dur, "тишина в конце")
            if dur is None:
                return None, None
            steps.append({"effect": "add_silence_end",
                          "params": {"duration": dur}})

        if not steps:
            messagebox.showerror(
                "Ошибка",
                "Пайплайн пуст. Добавьте эффекты или включите "
                "добавление тишины.")
            return None, None
        return steps, f"{description}, шагов: {len(steps)}"

    # -------------------------------------------------- предпрослушка
    def _start_preview(self):
        files = self.source.get_files()
        if not files:
            messagebox.showerror("Ошибка", "Выберите источник аудио")
            return
        steps, description = self._collect_steps()
        if steps is None:
            return
        self.preview_btn.config(state="disabled")
        self.log_panel.log(f"Готовлю предпрослушку: {description}...")
        threading.Thread(target=self._preview_worker,
                         args=(files[0], steps), daemon=True).start()

    def _preview_worker(self, path, steps):
        log = self.log_panel.log
        try:
            signal, sr = load_audio(path)
            signal, sr = apply_pipeline(signal, sr, steps, log=None)
            tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False,
                                              prefix="vui_preview_")
            tmp.close()
            save_audio(tmp.name, signal, sr, "WAV", "PCM_16")
            self._preview_original = path
            self._preview_processed = tmp.name

            def _enable():
                self.play_orig_btn.config(state="normal")
                self.play_proc_btn.config(state="normal")
                self.preview_btn.config(state="normal")
            self.root.after(0, _enable)
            log("Предпрослушка готова: ▶ Оригинал / ▶ После обработки")
        except Exception as e:
            log(f"ОШИБКА предпрослушки: {e}")
            self.root.after(0, lambda: self.preview_btn.config(
                state="normal"))

    def _play_original(self):
        if self._preview_original:
            playback.play_file(self._preview_original, log=self.log_panel.log)

    def _play_processed(self):
        if self._preview_processed:
            playback.play_file(self._preview_processed, log=self.log_panel.log)

    # ------------------------------------------------------------ обработка
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

        steps, description = self._collect_steps()
        if steps is None:
            self.run_bar.finish()
            return

        keep_names = self.keep_names_var.get()
        # Предупреждение о риске перезаписи исходников
        if keep_names:
            src_dirs = {os.path.dirname(os.path.abspath(f)) for f in files}
            if os.path.abspath(out_dir) in src_dirs:
                messagebox.showwarning(
                    "Защита от перезаписи",
                    "Папка сохранения совпадает с папкой исходников, "
                    "а сохранение исходных названий включено.\n\n"
                    "Существующие файлы НЕ будут перезаписаны: "
                    "при совпадении имён автоматически добавляется "
                    "числовой суффикс (_1, _2, ...).")

        fmt = self.format_var.get()
        subtype = self.subtype_var.get()

        threading.Thread(
            target=self._worker,
            args=(files, steps, description, out_dir, fmt, subtype,
                  keep_names, self.run_bar.cancel_event),
            daemon=True).start()

    def _worker(self, files, steps, description, out_dir, fmt, subtype,
                keep_names, cancel_event):
        log = self.log_panel.log
        log(f"Старт: {description}, файлов: {len(files)}, "
            f"формат: {fmt} {subtype or ''}".strip())
        total = len(files)
        for i, path in enumerate(files, 1):
            if cancel_event.is_set():
                log("Задача прервана пользователем.")
                break
            self.run_bar.set_progress(i - 1, total)
            log(f"[{i}/{total}] {os.path.basename(path)}")
            try:
                signal, sr = load_audio(path)
                signal, sr = apply_pipeline(signal, sr, steps, log=log)
                suffix = "" if keep_names else "_processed"
                out_path = get_output_path(path, out_dir, suffix, fmt)
                out_path, renamed = unique_path(out_path)
                if renamed:
                    log(f"  ⚠ Файл с таким именем уже существует — "
                        f"добавлен суффикс: {os.path.basename(out_path)}")
                save_audio(out_path, signal, sr, fmt,
                           subtype or DEFAULT_SUBTYPE)
                dur = len(signal) / sr
                log(f"  Сохранено: {os.path.basename(out_path)} "
                    f"({dur:.2f} с, {sr} Гц)")
                self.root.after(0, lambda p=out_path, d=dur:
                                self.results.add_result(p, f"{d:.2f} с"))
            except Exception as e:
                log(f"  ОШИБКА: {e}")
            self.run_bar.set_progress(i, total)
        log("Обработка завершена.")
        self.root.after(0, self._finish)

    def _finish(self):
        self.run_bar.finish()
        messagebox.showinfo("Готово", "Обработка аудио завершена")

    # ------------------------------------------------------------ настройки
    def get_settings(self) -> dict:
        return {
            "mode": self.mode.get(),
            "preset": self.preset_var.get(),
            "silence_start": self.silence_start_var.get(),
            "silence_start_dur": self.silence_start_dur.get(),
            "silence_end": self.silence_end_var.get(),
            "silence_end_dur": self.silence_end_dur.get(),
            "keep_names": self.keep_names_var.get(),
            "format": self.format_var.get(),
            "subtype": self.subtype_var.get(),
            "source_mode": self.source.get_mode(),
            "output_dir": self.output_dir.get(),
        }

    def apply_settings(self, s: dict):
        if not s:
            return
        self.mode.set(s.get("mode", "preset"))
        self._on_mode_change()
        if s.get("preset"):
            self._refresh_preset_list()
            values = self.preset_combo["values"]
            if s["preset"] in values:
                self.preset_var.set(s["preset"])
        self.silence_start_var.set(s.get("silence_start", False))
        self.silence_end_var.set(s.get("silence_end", False))
        self.silence_start_dur.set(s.get("silence_start_dur", "0.2"))
        self.silence_end_dur.set(s.get("silence_end_dur", "0.2"))
        self._on_silence_toggle()
        self.keep_names_var.set(s.get("keep_names", False))
        if s.get("format") in SAVE_FORMATS:
            self.format_var.set(s["format"])
            self._on_format_change()
        if s.get("subtype"):
            values = self.subtype_combo["values"]
            if s["subtype"] in values:
                self.subtype_var.set(s["subtype"])
        self.source.set_mode(s.get("source_mode", "file"))
        if s.get("output_dir"):
            self.output_dir.set(s["output_dir"])
