"""
Вкладка «TTS»: синтез речи двумя движками —
ElevenLabs (облачный API) и OmniVoice (локальная модель клонирования голоса).

Два режима: одна фраза или таблица фраз (столбец 'text'; необязательный
столбец 'voice' — для ElevenLabs это voice_id, для OmniVoice — путь
к эталонной записи голоса).
"""

import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from core import tts_elevenlabs, tts_omnivoice
from core.audio_io import AUDIO_EXTENSIONS
from gui.widgets import (DirectorySelector, LogPanel, ResultsPanel, RunBar)

ENGINES = ("ElevenLabs (API)", "OmniVoice (локально)")


class TtsTab(ttk.Frame):
    def __init__(self, parent, root):
        super().__init__(parent, padding=10)
        self.root = root
        self._table_df = None
        self._build_ui()

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        # Движок
        engine_frame = ttk.LabelFrame(self, text="Движок синтеза", padding=8)
        engine_frame.pack(fill="x", pady=(0, 8))
        ttk.Label(engine_frame, text="Движок:").pack(side="left")
        self.engine_var = tk.StringVar(value=ENGINES[0])
        combo = ttk.Combobox(engine_frame, values=ENGINES,
                             textvariable=self.engine_var,
                             state="readonly", width=24)
        combo.pack(side="left", padx=8)
        combo.bind("<<ComboboxSelected>>", lambda e: self._on_engine_change())

        # Параметры движка (два набора, переключаются)
        self.engine_container = ttk.LabelFrame(
            self, text="Параметры движка", padding=8)
        self.engine_container.pack(fill="x", pady=(0, 8))

        # --- ElevenLabs ---
        self.el_frame = ttk.Frame(self.engine_container)
        ttk.Label(self.el_frame, text="API-ключ:").grid(row=0, column=0,
                                                        sticky="w")
        self.api_key = tk.StringVar()
        ttk.Entry(self.el_frame, textvariable=self.api_key, width=45).grid(
            row=0, column=1, sticky="w", padx=(4, 14))
        ttk.Label(self.el_frame, text="Модель:").grid(row=0, column=2,
                                                      sticky="w")
        self.model_id = tk.StringVar(value=tts_elevenlabs.DEFAULT_MODEL)
        ttk.Combobox(self.el_frame, values=tts_elevenlabs.TTS_MODELS,
                     textvariable=self.model_id, state="readonly",
                     width=24).grid(row=0, column=3, sticky="w", padx=4)
        ttk.Label(self.el_frame, text="Voice ID (голос по умолчанию):").grid(
            row=1, column=0, sticky="w", pady=(6, 0))
        self.voice_id = tk.StringVar()
        ttk.Entry(self.el_frame, textvariable=self.voice_id, width=45).grid(
            row=1, column=1, sticky="w", padx=4, pady=(6, 0))
        ttk.Label(
            self.el_frame,
            text="Ключ сохраняется в настройках в открытом виде.",
            foreground="#666666").grid(row=2, column=0, columnspan=4,
                                       sticky="w", pady=(6, 0))

        # --- OmniVoice ---
        self.ov_frame = ttk.Frame(self.engine_container)
        ttk.Label(self.ov_frame,
                  text="Эталонная запись голоса:").grid(row=0, column=0,
                                                        sticky="w")
        self.ref_audio = tk.StringVar()
        ttk.Entry(self.ov_frame, textvariable=self.ref_audio, width=45).grid(
            row=0, column=1, sticky="w", padx=(4, 4))
        ttk.Button(self.ov_frame, text="Обзор...",
                   command=self._browse_ref_audio).grid(row=0, column=2)
        ttk.Label(
            self.ov_frame,
            text="OmniVoice клонирует голос из эталонной записи. "
                 "Модель скачивается при первом запуске (нужен интернет).",
            foreground="#666666").grid(row=1, column=0, columnspan=3,
                                       sticky="w", pady=(6, 0))

        # Режим: одна фраза / таблица
        src_frame = ttk.LabelFrame(self, text="Что озвучиваем", padding=8)
        src_frame.pack(fill="x", pady=(0, 8))
        self.source_mode = tk.StringVar(value="phrase")
        ttk.Radiobutton(src_frame, text="Одна фраза",
                        variable=self.source_mode, value="phrase",
                        command=self._on_mode_change).grid(
            row=0, column=0, sticky="w", padx=(0, 12))
        ttk.Radiobutton(src_frame, text="Фразы из таблицы",
                        variable=self.source_mode, value="table",
                        command=self._on_mode_change).grid(
            row=0, column=1, sticky="w")

        self.phrase_frame = ttk.Frame(src_frame)
        ttk.Label(self.phrase_frame, text="Текст фразы:").pack(anchor="w")
        self.phrase_text = tk.Text(self.phrase_frame, height=4, width=70)
        self.phrase_text.pack(fill="x", pady=(2, 0))

        self.table_frame = ttk.Frame(src_frame)
        self.table_path = tk.StringVar()
        ttk.Entry(self.table_frame, textvariable=self.table_path,
                  state="readonly", width=55).pack(side="left", padx=(0, 5))
        ttk.Button(self.table_frame, text="Обзор...",
                   command=self._browse_table).pack(side="left")
        self.table_info = ttk.Label(self.table_frame, text="",
                                    foreground="#666666")
        self.table_info.pack(side="left", padx=8)

        self.table_hint = ttk.Label(src_frame, text="", foreground="#666666")
        self.table_hint.grid(row=3, column=0, columnspan=2, sticky="w",
                             pady=(4, 0))

        self.phrase_frame.grid(row=1, column=0, columnspan=2, sticky="ew",
                               pady=(8, 0))
        self.table_frame.grid(row=2, column=0, columnspan=2, sticky="ew",
                              pady=(8, 0))
        self._on_engine_change()
        self._on_mode_change()

        self.output_dir = DirectorySelector(self)
        self.output_dir.pack(fill="x", pady=(0, 8))

        self.run_bar = RunBar(self, self.root, "Озвучить", self._start)
        self.run_bar.pack(fill="x", pady=(0, 8))

        bottom = ttk.Frame(self)
        bottom.pack(fill="both", expand=True)
        self.log_panel = LogPanel(bottom, self.root)
        self.log_panel.pack(side="left", fill="both", expand=True,
                            padx=(0, 4))
        self.results = ResultsPanel(bottom, self.root, self.log_panel.log)
        self.results.pack(side="right", fill="both", expand=True,
                          padx=(4, 0))

    def _on_engine_change(self):
        elevenlabs = self.engine_var.get() == ENGINES[0]
        if elevenlabs:
            self.ov_frame.pack_forget()
            self.el_frame.pack(fill="x")
            self.table_hint.config(
                text="Обязательный столбец: 'text'. Для разных голосов — "
                     "столбец 'voice' с voice_id.")
        else:
            self.el_frame.pack_forget()
            self.ov_frame.pack(fill="x")
            self.table_hint.config(
                text="Обязательный столбец: 'text'. Для разных голосов — "
                     "столбец 'voice' с путём к эталонной записи голоса.")

    def _on_mode_change(self):
        if self.source_mode.get() == "phrase":
            self.table_frame.grid_remove()
            self.phrase_frame.grid()
        else:
            self.phrase_frame.grid_remove()
            self.table_frame.grid()

    def _browse_ref_audio(self):
        path = filedialog.askopenfilename(
            filetypes=[("Аудиофайлы",
                        " ".join(f"*{e}" for e in AUDIO_EXTENSIONS)),
                       ("Все файлы", "*.*")])
        if path:
            self.ref_audio.set(path)

    def _browse_table(self):
        path = filedialog.askopenfilename(
            filetypes=[("Таблицы", "*.xlsx *.xls *.csv"),
                       ("Все файлы", "*.*")])
        if not path:
            return
        try:
            df = tts_elevenlabs.load_table(path)
        except Exception as e:
            messagebox.showerror("Ошибка",
                                 f"Не удалось прочитать таблицу: {e}")
            return
        if "text" not in df.columns:
            messagebox.showerror(
                "Ошибка", "В таблице нет обязательного столбца 'text'")
            return
        self._table_df = df
        self.table_path.set(path)
        has_voice = "voice" in df.columns or "voice_id" in df.columns
        voice_note = (", столбец 'voice' найден" if has_voice else
                      ", столбца 'voice' нет — голос по умолчанию")
        self.table_info.config(text=f"{len(df)} строк{voice_note}")

    # ------------------------------------------------------------ запуск
    def _start(self):
        elevenlabs = self.engine_var.get() == ENGINES[0]
        out_dir = self.output_dir.get()
        if not out_dir:
            messagebox.showerror("Ошибка", "Укажите папку для сохранения")
            self.run_bar.finish()
            return

        if elevenlabs:
            if not self.api_key.get().strip():
                messagebox.showerror("Ошибка",
                                     "Введите API-ключ ElevenLabs")
                self.run_bar.finish()
                return

        mode = self.source_mode.get()
        if mode == "phrase":
            text = self.phrase_text.get("1.0", tk.END).strip()
            if not text:
                messagebox.showerror("Ошибка", "Введите текст фразы")
                self.run_bar.finish()
                return
            if elevenlabs:
                if not self.voice_id.get().strip():
                    messagebox.showerror("Ошибка", "Введите Voice ID")
                    self.run_bar.finish()
                    return
            else:
                ref = self.ref_audio.get().strip()
                if not ref or not os.path.isfile(ref):
                    messagebox.showerror(
                        "Ошибка", "Выберите эталонную запись голоса")
                    self.run_bar.finish()
                    return
        else:
            if self._table_df is None:
                messagebox.showerror("Ошибка", "Загрузите таблицу с фразами")
                self.run_bar.finish()
                return

        threading.Thread(target=self._worker,
                         args=(elevenlabs, mode, out_dir,
                               self.run_bar.cancel_event),
                         daemon=True).start()

    def _worker(self, elevenlabs, mode, out_dir, cancel_event):
        log = self.log_panel.log
        os.makedirs(out_dir, exist_ok=True)
        progress = self.run_bar.set_progress
        try:
            if elevenlabs:
                if mode == "phrase":
                    path = tts_elevenlabs.synthesize_single(
                        self.phrase_text.get("1.0", tk.END).strip(),
                        self.voice_id.get().strip(),
                        self.api_key.get().strip(), out_dir,
                        self.model_id.get(), log)
                    if path:
                        self._add_result(path)
                else:
                    created = tts_elevenlabs.synthesize_table(
                        self._table_df, self.voice_id.get().strip(),
                        self.api_key.get().strip(), out_dir,
                        self.model_id.get(), log, progress=progress,
                        cancel_event=cancel_event)
                    log(f"Создано файлов: {len(created)}")
                    for p in created:
                        self._add_result(p)
            else:
                if mode == "phrase":
                    path = tts_omnivoice.synthesize_single(
                        self.phrase_text.get("1.0", tk.END).strip(),
                        self.ref_audio.get().strip(), out_dir, log)
                    if path:
                        self._add_result(path)
                else:
                    created = tts_omnivoice.synthesize_table(
                        self._table_df, self.ref_audio.get().strip(),
                        out_dir, log, progress=progress,
                        cancel_event=cancel_event)
                    log(f"Создано файлов: {len(created)}")
                    for p in created:
                        self._add_result(p)
        except Exception as e:
            log(f"ОШИБКА: {e}")
        log("Озвучка завершена.")
        self.root.after(0, self._finish)

    def _add_result(self, path):
        self.root.after(0, lambda p=path: self.results.add_result(p, "аудио"))

    def _finish(self):
        self.run_bar.finish()
        messagebox.showinfo("Готово", "Озвучка завершена")

    # ------------------------------------------------------------ настройки
    def get_settings(self) -> dict:
        return {
            "engine": self.engine_var.get(),
            "api_key": self.api_key.get(),
            "model_id": self.model_id.get(),
            "voice_id": self.voice_id.get(),
            "ref_audio": self.ref_audio.get(),
            "source_mode": self.source_mode.get(),
            "output_dir": self.output_dir.get(),
        }

    def apply_settings(self, s: dict):
        if not s:
            return
        if s.get("engine") in ENGINES:
            self.engine_var.set(s["engine"])
            self._on_engine_change()
        self.api_key.set(s.get("api_key", ""))
        if s.get("model_id") in tts_elevenlabs.TTS_MODELS:
            self.model_id.set(s["model_id"])
        self.voice_id.set(s.get("voice_id", ""))
        self.ref_audio.set(s.get("ref_audio", ""))
        self.source_mode.set(s.get("source_mode", "phrase"))
        self._on_mode_change()
        if s.get("output_dir"):
            self.output_dir.set(s["output_dir"])
