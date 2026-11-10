"""
Вкладка «Поиск и разметка»: поиск слов и словосочетаний в аудиозаписях
через Whisper и создание .seg-разметки рядом с исходными файлами.
Поддерживается неточное (fuzzy) совпадение с настраиваемым порогом сходства.
"""

import threading
import tkinter as tk
from tkinter import messagebox, ttk

from core.word_search import (WHISPER_MODELS, DEFAULT_MODEL, DEFAULT_LANGUAGE,
                              search_words_in_files)
from gui.widgets import (AudioSourceSelector, LogPanel, ResultsPanel, RunBar)


class SearchTab(ttk.Frame):
    def __init__(self, parent, root):
        super().__init__(parent, padding=10)
        self.root = root
        self._build_ui()

    def _build_ui(self):
        self.source = AudioSourceSelector(self)
        self.source.pack(fill="x", pady=(0, 8))

        # Слова для поиска
        words_frame = ttk.LabelFrame(self, text="Слова и словосочетания "
                                                "для поиска", padding=8)
        words_frame.pack(fill="x", pady=(0, 8))

        left = ttk.Frame(words_frame)
        left.pack(side="left", fill="both", expand=True)
        self.words_listbox = tk.Listbox(left, height=5, activestyle="none")
        scrollbar = ttk.Scrollbar(left, orient="vertical",
                                  command=self.words_listbox.yview)
        self.words_listbox.config(yscrollcommand=scrollbar.set)
        self.words_listbox.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        right = ttk.Frame(words_frame)
        right.pack(side="left", fill="y", padx=(10, 0))
        ttk.Label(right, text="Слово или словосочетание:").pack(anchor="w")
        self.word_var = tk.StringVar()
        entry = ttk.Entry(right, textvariable=self.word_var, width=26)
        entry.pack(anchor="w", pady=(2, 4))
        entry.bind("<Return>", lambda e: self._add_word())
        ttk.Button(right, text="Добавить слово/словосочетание",
                   command=self._add_word).pack(fill="x", pady=2)
        ttk.Button(right, text="Удалить выбранное",
                   command=self._remove_word).pack(fill="x", pady=2)
        ttk.Button(right, text="Очистить список",
                   command=self._clear_words).pack(fill="x", pady=2)

        # Параметры поиска
        params_frame = ttk.LabelFrame(self, text="Параметры распознавания",
                                      padding=8)
        params_frame.pack(fill="x", pady=(0, 8))
        ttk.Label(params_frame, text="Макс. число фрагментов:").grid(
            row=0, column=0, sticky="w")
        self.max_fragments = tk.StringVar(value="1")
        ttk.Entry(params_frame, textvariable=self.max_fragments,
                  width=8).grid(row=0, column=1, sticky="w", padx=(4, 14))
        ttk.Label(params_frame, text="Модель Whisper:").grid(
            row=0, column=2, sticky="w")
        self.model_var = tk.StringVar(value=DEFAULT_MODEL)
        ttk.Combobox(params_frame, values=WHISPER_MODELS,
                     textvariable=self.model_var, state="readonly",
                     width=10).grid(row=0, column=3, sticky="w", padx=(4, 14))
        ttk.Label(params_frame, text="Язык аудио:").grid(row=0, column=4,
                                                         sticky="w")
        self.language = tk.StringVar(value=DEFAULT_LANGUAGE)
        ttk.Entry(params_frame, textvariable=self.language, width=6).grid(
            row=0, column=5, sticky="w", padx=(4, 0))

        # Неточное совпадение
        self.fuzzy_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(params_frame, text="Разрешить неточное совпадение",
                        variable=self.fuzzy_var,
                        command=self._on_fuzzy_toggle).grid(
            row=1, column=0, columnspan=3, sticky="w", pady=(8, 0))
        ttk.Label(params_frame, text="Сходство, %:").grid(row=1, column=3,
                                                          sticky="e",
                                                          pady=(8, 0))
        self.similarity_var = tk.StringVar(value="80")
        self.similarity_entry = ttk.Entry(
            params_frame, textvariable=self.similarity_var, width=6,
            state="disabled")
        self.similarity_entry.grid(row=1, column=4, sticky="w", padx=(4, 0),
                                   pady=(8, 0))

        ttk.Label(
            params_frame,
            text="Файлы разметки .seg сохраняются в ту же папку, "
                 "где лежит исходная запись. Позиции меток — в байтах.",
            foreground="#666666").grid(row=2, column=0, columnspan=6,
                                       sticky="w", pady=(6, 0))

        self.run_bar = RunBar(self, self.root, "Найти и разметить",
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

    def _on_fuzzy_toggle(self):
        self.similarity_entry.config(
            state="normal" if self.fuzzy_var.get() else "disabled")

    # ------------------------------------------------------------ слова
    def _add_word(self):
        word = self.word_var.get().strip()
        if not word:
            return
        existing = self.words_listbox.get(0, tk.END)
        if word.lower() in [w.lower() for w in existing]:
            return
        self.words_listbox.insert(tk.END, word)
        self.word_var.set("")

    def _remove_word(self):
        sel = self.words_listbox.curselection()
        if sel:
            self.words_listbox.delete(sel[0])

    def _clear_words(self):
        self.words_listbox.delete(0, tk.END)

    def _get_words(self) -> list:
        return list(self.words_listbox.get(0, tk.END))

    # ------------------------------------------------------------ запуск
    def _start(self):
        files = self.source.get_files()
        if not files:
            messagebox.showerror("Ошибка", "Выберите источник аудио")
            self.run_bar.finish()
            return
        words = self._get_words()
        if not words:
            messagebox.showerror(
                "Ошибка", "Добавьте хотя бы одно слово для поиска")
            self.run_bar.finish()
            return
        try:
            max_fragments = int(self.max_fragments.get())
            if max_fragments < 1:
                raise ValueError
        except ValueError:
            messagebox.showerror(
                "Ошибка", "Макс. число фрагментов — целое число >= 1")
            self.run_bar.finish()
            return

        fuzzy = self.fuzzy_var.get()
        similarity = 0.8
        if fuzzy:
            try:
                similarity = float(self.similarity_var.get()
                                   .replace(",", ".")) / 100.0
                if not (0 < similarity <= 1):
                    raise ValueError
            except ValueError:
                messagebox.showerror(
                    "Ошибка", "Сходство — число от 1 до 100 (в процентах)")
                self.run_bar.finish()
                return

        threading.Thread(
            target=self._worker,
            args=(files, words, max_fragments, self.model_var.get(),
                  self.language.get().strip(), fuzzy, similarity,
                  self.run_bar.cancel_event),
            daemon=True).start()

    def _worker(self, files, words, max_fragments, model_name, language,
                fuzzy, similarity, cancel_event):
        log = self.log_panel.log
        fuzzy_note = (f", неточное совпадение от "
                      f"{int(round(similarity * 100))}%") if fuzzy else ""
        log(f"Поиск: {', '.join(words)} "
            f"(макс. фрагментов: {max_fragments}, модель: {model_name}, "
            f"язык: {language or 'авто'}{fuzzy_note})")
        log("Модель Whisper при первом запуске скачивается — "
            "это может занять время.")
        try:
            results = search_words_in_files(
                files, words, max_fragments, model_name, language,
                fuzzy=fuzzy, similarity=similarity, log=log,
                progress=self.run_bar.set_progress,
                cancel_event=cancel_event)
            log(f"Создано файлов разметки: {len(results)}")
            for p in results:
                self.root.after(
                    0, lambda path=p: self.results.add_result(path, ".seg"))
        except Exception as e:
            log(f"ОШИБКА: {e}")
        log("Поиск завершён.")
        self.root.after(0, self._finish)

    def _finish(self):
        self.run_bar.finish()
        messagebox.showinfo("Готово", "Поиск и разметка завершены")

    # ------------------------------------------------------------ настройки
    def get_settings(self) -> dict:
        return {
            "max_fragments": self.max_fragments.get(),
            "model": self.model_var.get(),
            "language": self.language.get(),
            "fuzzy": self.fuzzy_var.get(),
            "similarity": self.similarity_var.get(),
            "source_mode": self.source.get_mode(),
            "words": self._get_words(),
        }

    def apply_settings(self, s: dict):
        if not s:
            return
        self.max_fragments.set(s.get("max_fragments", "1"))
        if s.get("model") in WHISPER_MODELS:
            self.model_var.set(s["model"])
        self.language.set(s.get("language", DEFAULT_LANGUAGE))
        self.fuzzy_var.set(s.get("fuzzy", False))
        self.similarity_var.set(s.get("similarity", "80"))
        self._on_fuzzy_toggle()
        self.source.set_mode(s.get("source_mode", "file"))
        for w in s.get("words", []):
            self.words_listbox.insert(tk.END, w)
