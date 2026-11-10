"""
Общие виджеты GUI VUI ToolKit.

Унифицированные компоненты для всех вкладок: выбор источника аудио
(одна запись / несколько записей / папка, с drag-and-drop), выбор
папки, панель лога, панель результатов (прослушать / открыть папку),
панель запуска с детерминированным прогрессом и кнопкой «Прервать».
"""

import os
import queue
import tkinter as tk
from tkinter import filedialog, ttk

from core.audio_io import AUDIO_EXTENSIONS, collect_audio_files, is_audio_file
from core import playback

# Drag-and-drop — опционально (tkinterdnd2)
try:
    from tkinterdnd2 import DND_FILES
    HAS_DND = True
except ImportError:
    HAS_DND = False


def _parse_dropped_paths(widget, data: str) -> list:
    """Разбирает строку путей из события drop (учитывает пробелы/скобки)."""
    try:
        return list(widget.tk.splitlist(data))
    except Exception:
        return [data]


class AudioSourceSelector(ttk.LabelFrame):
    """
    Унифицированный выбор источника аудио:
    'file' — одна запись, 'files' — несколько записей, 'folder' — папка.
    Поддерживает drag-and-drop файлов и папок.
    Метод get_files() возвращает список путей к аудиофайлам.
    """

    MODES = (("file", "Одна запись"),
             ("files", "Несколько записей"),
             ("folder", "Папка с записями"))

    def __init__(self, parent, title="Источник аудио"):
        super().__init__(parent, text=title, padding=8)
        self.mode = tk.StringVar(value="file")
        self._paths = []

        for i, (value, text) in enumerate(self.MODES):
            ttk.Radiobutton(self, text=text, variable=self.mode, value=value,
                            command=self._on_mode_change).grid(
                row=0, column=i, sticky="w", padx=(0, 12))

        self.path_var = tk.StringVar()
        self.path_entry = ttk.Entry(self, textvariable=self.path_var,
                                    state="readonly", width=60)
        self.path_entry.grid(row=1, column=0, columnspan=2, sticky="ew",
                             padx=(0, 5), pady=(6, 0))
        ttk.Button(self, text="Обзор...", command=self._browse).grid(
            row=1, column=2, pady=(6, 0))

        hint = "Файлы не выбраны"
        if HAS_DND:
            hint += "  (можно перетащить файлы/папку мышью)"
        self.count_label = ttk.Label(self, text=hint)
        self.count_label.grid(row=2, column=0, columnspan=3, sticky="w",
                              pady=(4, 0))
        self.columnconfigure(0, weight=1)

        if HAS_DND:
            self._enable_dnd()

    # ---------------------------------------------------------- DnD
    def _enable_dnd(self):
        try:
            for w in (self.path_entry, self):
                w.drop_target_register(DND_FILES)
                w.dnd_bind("<<Drop>>", self._on_drop)
        except tk.TclError:
            # корневое окно без поддержки tkdnd — работаем без DnD
            pass

    def _on_drop(self, event):
        paths = _parse_dropped_paths(self, event.data)
        folders = [p for p in paths if os.path.isdir(p)]
        files = [p for p in paths if os.path.isfile(p) and is_audio_file(p)]
        if len(paths) == 1 and folders:
            self.mode.set("folder")
            self._paths = collect_audio_files(folders[0])
        elif len(files) == 1 and len(paths) == 1:
            self.mode.set("file")
            self._paths = files
        elif files:
            self.mode.set("files")
            self._paths = files
        else:
            self._paths = []
        self._refresh_label()

    # -------------------------------------------------------- выбор
    def _on_mode_change(self):
        self._paths = []
        self.path_var.set("")
        self._refresh_count()

    def _refresh_count(self):
        hint = "Файлы не выбраны"
        if HAS_DND:
            hint += "  (можно перетащить файлы/папку мышью)"
        self.count_label.config(text=hint)

    def _browse(self):
        mode = self.mode.get()
        filetypes = [("Аудиофайлы", " ".join(f"*{e}" for e in AUDIO_EXTENSIONS)),
                     ("Все файлы", "*.*")]
        if mode == "file":
            path = filedialog.askopenfilename(filetypes=filetypes)
            self._paths = [path] if path else []
        elif mode == "files":
            paths = filedialog.askopenfilenames(filetypes=filetypes)
            self._paths = [p for p in paths if is_audio_file(p)]
        else:
            folder = filedialog.askdirectory()
            self._paths = collect_audio_files(folder) if folder else []
        self._refresh_label()

    def _refresh_label(self):
        mode = self.mode.get()
        if not self._paths:
            self.path_var.set("")
            self._refresh_count()
            return
        if mode == "folder":
            self.path_var.set(os.path.dirname(self._paths[0]))
        elif len(self._paths) == 1:
            self.path_var.set(self._paths[0])
        else:
            self.path_var.set(f"Выбрано файлов: {len(self._paths)}")
        self.count_label.config(
            text=f"Найдено аудиофайлов: {len(self._paths)}")

    def get_files(self) -> list:
        return list(self._paths)

    def get_mode(self) -> str:
        return self.mode.get()

    def set_mode(self, mode: str):
        if mode in dict(self.MODES):
            self.mode.set(mode)


class DirectorySelector(ttk.LabelFrame):
    """Выбор папки (например, для сохранения результатов). Поддерживает DnD."""

    def __init__(self, parent, title="Папка для сохранения"):
        super().__init__(parent, text=title, padding=8)
        self.path_var = tk.StringVar()
        self.entry = ttk.Entry(self, textvariable=self.path_var, width=60)
        self.entry.grid(row=0, column=0, sticky="ew", padx=(0, 5))
        ttk.Button(self, text="Обзор...",
                   command=self._browse).grid(row=0, column=1)
        self.columnconfigure(0, weight=1)

        if HAS_DND:
            try:
                self.entry.drop_target_register(DND_FILES)
                self.entry.dnd_bind("<<Drop>>", self._on_drop)
            except tk.TclError:
                pass

    def _on_drop(self, event):
        paths = _parse_dropped_paths(self, event.data)
        for p in paths:
            folder = p if os.path.isdir(p) else os.path.dirname(p)
            if folder:
                self.path_var.set(folder)
                break

    def _browse(self):
        path = filedialog.askdirectory()
        if path:
            self.path_var.set(path)

    def get(self) -> str:
        return self.path_var.get().strip()

    def set(self, value: str):
        self.path_var.set(value)


class LogPanel(ttk.LabelFrame):
    """Панель лога. Потокобезопасная: log() можно звать из рабочих потоков."""

    def __init__(self, parent, root, title="Лог", height=8):
        super().__init__(parent, text=title, padding=8)
        self.root = root
        self._queue = queue.Queue()

        self.text = tk.Text(self, height=height, state="disabled",
                            wrap="word")
        scrollbar = ttk.Scrollbar(self, orient="vertical",
                                  command=self.text.yview)
        self.text.configure(yscrollcommand=scrollbar.set)
        self.text.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self._poll()

    def log(self, message: str):
        self._queue.put(str(message))

    def _poll(self):
        try:
            while True:
                msg = self._queue.get_nowait()
                self.text.config(state="normal")
                self.text.insert("end", msg + "\n")
                self.text.see("end")
                self.text.config(state="disabled")
        except queue.Empty:
            pass
        self.root.after(100, self._poll)

    def clear(self):
        self.text.config(state="normal")
        self.text.delete("1.0", "end")
        self.text.config(state="disabled")


class ResultsPanel(ttk.LabelFrame):
    """
    Панель результатов обработки: таблица файлов с кнопками
    «Прослушать», «Открыть папку», «Очистить».
    """

    def __init__(self, parent, root, log, title="Результаты", height=4):
        super().__init__(parent, text=title, padding=8)
        self.root = root
        self._log = log
        self._items = {}  # iid -> path

        columns = ("file", "info")
        self.tree = ttk.Treeview(self, columns=columns, show="headings",
                                 height=height)
        self.tree.heading("file", text="Файл")
        self.tree.heading("info", text="Детали")
        self.tree.column("file", width=320)
        self.tree.column("info", width=340)
        scrollbar = ttk.Scrollbar(self, orient="vertical",
                                  command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        btns = ttk.Frame(self)
        btns.pack(side="right", fill="y", padx=(8, 0))
        ttk.Button(btns, text="Прослушать",
                   command=self._play_selected).pack(fill="x", pady=2)
        ttk.Button(btns, text="Открыть папку",
                   command=self._open_folder).pack(fill="x", pady=2)
        ttk.Button(btns, text="Очистить",
                   command=self.clear).pack(fill="x", pady=2)

    def add_result(self, path: str, info: str = ""):
        """Добавляет файл в таблицу результатов."""
        iid = self.tree.insert("", "end",
                               values=(os.path.basename(path), info))
        self._items[iid] = path
        self.tree.see(iid)

    def _selected_path(self):
        sel = self.tree.selection()
        if not sel:
            return None
        return self._items.get(sel[0])

    def _play_selected(self):
        path = self._selected_path()
        if path:
            playback.play_file(path, log=self._log)

    def _open_folder(self):
        path = self._selected_path()
        if path:
            playback.open_in_folder(path)

    def clear(self):
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        self._items.clear()


class ScrollFrame(ttk.Frame):
    """
    Прокручиваемый контейнер для длинных вкладок.
    Содержимое добавляйте в .content. Колёсико мыши прокручивает
    содержимое, когда курсор над контейнером.
    """

    def __init__(self, parent):
        super().__init__(parent)
        self.canvas = tk.Canvas(self, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self, orient="vertical",
                                  command=self.canvas.yview)
        self.content = ttk.Frame(self.canvas)
        self._window = self.canvas.create_window(
            (0, 0), window=self.content, anchor="nw")
        self.canvas.configure(yscrollcommand=scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.content.bind(
            "<Configure>",
            lambda e: self.canvas.configure(
                scrollregion=self.canvas.bbox("all")))
        self.canvas.bind(
            "<Configure>",
            lambda e: self.canvas.itemconfigure(self._window,
                                                width=e.width))
        # колёсико мыши — только когда курсор над этим контейнером
        self.canvas.bind("<Enter>", self._bind_wheel)
        self.canvas.bind("<Leave>", self._unbind_wheel)

    def _on_wheel(self, event):
        if event.num == 4 or getattr(event, "delta", 0) > 0:
            self.canvas.yview_scroll(-1, "units")
        else:
            self.canvas.yview_scroll(1, "units")

    def _bind_wheel(self, _event):
        self.canvas.bind_all("<MouseWheel>", self._on_wheel)
        self.canvas.bind_all("<Button-4>", self._on_wheel)
        self.canvas.bind_all("<Button-5>", self._on_wheel)

    def _unbind_wheel(self, _event):
        self.canvas.unbind_all("<MouseWheel>")
        self.canvas.unbind_all("<Button-4>")
        self.canvas.unbind_all("<Button-5>")


class RunBar(ttk.Frame):
    """
    Панель запуска задачи: кнопка запуска, кнопка «Прервать»
    и детерминированный прогресс-бар.
    on_run() вызывается при старте; задача должна вызывать
    set_progress(i, total) и в конце finish().
    """

    def __init__(self, parent, root, run_text, on_run):
        super().__init__(parent)
        self.root = root
        self._on_run = on_run
        import threading
        self.cancel_event = threading.Event()

        self.run_btn = ttk.Button(self, text=run_text, command=self._start)
        self.run_btn.pack(side="left")
        self.cancel_btn = ttk.Button(self, text="Прервать",
                                     command=self.cancel, state="disabled")
        self.cancel_btn.pack(side="left", padx=(8, 0))
        self.progress = ttk.Progressbar(self, mode="determinate",
                                        length=250)
        self.progress.pack(side="left", padx=12)
        self.status = ttk.Label(self, text="")
        self.status.pack(side="left")

    def _start(self):
        self.cancel_event.clear()
        self.run_btn.config(state="disabled")
        self.cancel_btn.config(state="normal")
        self.progress.configure(value=0, maximum=100)
        self.status.config(text="")
        self._on_run()

    def cancel(self):
        self.cancel_event.set()
        self.status.config(text="Прерывание...")
        self.cancel_btn.config(state="disabled")

    def set_progress(self, i: int, total: int):
        """Потокобезопасное обновление прогресса."""
        def _upd():
            self.progress.configure(maximum=max(1, total), value=i)
            self.status.config(text=f"{i}/{total}")
        self.root.after(0, _upd)

    def finish(self):
        """Вызывается по завершении задачи (из потока — через after)."""
        def _fin():
            self.progress.configure(value=self.progress["maximum"])
            self.run_btn.config(state="normal")
            self.cancel_btn.config(state="disabled")
            self.status.config(text="Готово")
        self.root.after(0, _fin)
