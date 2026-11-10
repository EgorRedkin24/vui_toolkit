"""
Темы оформления VUI ToolKit: светлая и тёмная.

Палитра повторяет дизайн веб-версии (Сайт/snail-voice-forge):
тёмная тема — фон/карточки/фиолетовый акцент сайта, светлая — её аналог.
Тёмная тема реализована поверх ttk-темы 'clam'; простые tk-виджеты
(Text, Listbox, Spinbox) перекрашиваются рекурсивным обходом дерева.
"""

import tkinter as tk
from tkinter import ttk

# Тёмная тема — те же токены, что и .dark в styles.css веб-версии
DARK = {
    "bg": "#070a12",            # --background
    "fg": "#e8ebf4",            # --foreground
    "card": "#0f131f",          # --card: панели, surface
    "field_bg": "#131824",      # --popover: поля ввода, списки, лог
    "field_fg": "#e8ebf4",
    "select_bg": "#9281ff",     # --primary: выделение
    "select_fg": "#0b0d16",
    "button_bg": "#1a1f2c",     # --secondary
    "button_active": "#252641",  # --accent (hover)
    "border": "#222838",        # --border
    "hint": "#8b92a4",          # --muted-foreground
    "disabled_fg": "#565d6e",
    "primary": "#9281ff",
    "primary_fg": "#f2f0ff",
    "accent_fg": "#b3a7ff",
    "success": "#00ce88",
    "warning": "#e9b543",
    "destructive": "#ff6467",
}

# Светлая тема — :root из styles.css
LIGHT = {
    "bg": "#f5f7fb",
    "fg": "#0e111d",
    "card": "#ffffff",          # --card
    "field_bg": "#ffffff",
    "field_fg": "#0e111d",
    "select_bg": "#7c69f4",     # --primary
    "select_fg": "#ffffff",
    "button_bg": "#e8ebf4",     # --secondary
    "button_active": "#e1e2fc",  # --accent
    "border": "#d3d7e4",        # --border
    "hint": "#5a6072",          # --muted-foreground
    "disabled_fg": "#9aa0b0",
    "primary": "#7c69f4",
    "primary_fg": "#ffffff",
    "accent_fg": "#5b48d8",
    "success": "#12c281",
    "warning": "#b78a1f",
    "destructive": "#e7000b",
}

_current = DARK


def current_theme() -> dict:
    return _current


def hint_color() -> str:
    return _current["hint"]


def apply_theme(root: tk.Tk, dark: bool):
    """Применяет тему ко всему окну. dark=True — тёмная."""
    global _current
    _current = DARK if dark else LIGHT
    c = _current

    style = ttk.Style(root)
    if "clam" in style.theme_names():
        style.theme_use("clam")

    font = ("Segoe UI", 10)
    style.configure(".", background=c["bg"], foreground=c["fg"],
                    bordercolor=c["border"], darkcolor=c["bg"],
                    lightcolor=c["bg"], font=font,
                    troughcolor=c["field_bg"])

    style.configure("TFrame", background=c["bg"])
    style.configure("TLabel", background=c["bg"], foreground=c["fg"])
    style.configure("TLabelframe", background=c["bg"], foreground=c["fg"],
                    bordercolor=c["border"], relief="solid", borderwidth=1)
    style.configure("TLabelframe.Label", background=c["bg"],
                    foreground=c["fg"], font=("Segoe UI", 10, "bold"))

    # Обычная кнопка: плоская, фон --secondary, при наведении --accent
    style.configure("TButton", background=c["button_bg"],
                    foreground=c["fg"], bordercolor=c["button_bg"],
                    focusthickness=1, focuscolor=c["button_bg"],
                    padding=(10, 5))
    style.map("TButton",
              background=[("disabled", c["bg"]),
                          ("pressed", c["button_active"]),
                          ("active", c["button_active"])],
              foreground=[("disabled", c["disabled_fg"])],
              bordercolor=[("active", c["border"])])

    # Акцентная кнопка (запуск задач): фон --primary
    style.configure("Accent.TButton", background=c["primary"],
                    foreground=c["primary_fg"],
                    bordercolor=c["primary"], focuscolor=c["primary"],
                    padding=(14, 6), font=("Segoe UI", 10, "bold"))
    style.map("Accent.TButton",
              background=[("disabled", c["button_bg"]),
                          ("pressed", c["primary"]),
                          ("active", c["accent_fg"] if not dark
                           else "#a193ff")],
              foreground=[("disabled", c["disabled_fg"])])

    style.configure("TCheckbutton", background=c["bg"], foreground=c["fg"])
    style.map("TCheckbutton",
              foreground=[("disabled", c["disabled_fg"])])
    style.configure("TRadiobutton", background=c["bg"], foreground=c["fg"])
    style.map("TRadiobutton",
              foreground=[("disabled", c["disabled_fg"])])

    style.configure("TEntry", fieldbackground=c["field_bg"],
                    foreground=c["field_fg"], bordercolor=c["border"],
                    insertcolor=c["field_fg"], padding=3)
    style.configure("TCombobox", fieldbackground=c["field_bg"],
                    foreground=c["field_fg"], bordercolor=c["border"],
                    background=c["button_bg"], arrowcolor=c["fg"],
                    padding=3)
    style.map("TCombobox",
              fieldbackground=[("readonly", c["field_bg"])],
              foreground=[("readonly", c["field_fg"])])
    style.configure("TSpinbox", fieldbackground=c["field_bg"],
                    foreground=c["field_fg"], bordercolor=c["border"],
                    arrowcolor=c["fg"], background=c["button_bg"])

    # Вкладки: неактивные сливаются с фоном, активная — «карточка»
    style.configure("TNotebook", background=c["bg"],
                    bordercolor=c["border"], tabmargins=(6, 4, 6, 0))
    style.configure("TNotebook.Tab", padding=(14, 7),
                    background=c["button_bg"], foreground=c["hint"],
                    bordercolor=c["bg"])
    style.map("TNotebook.Tab",
              background=[("selected", c["card"])],
              foreground=[("selected", c["fg"])])

    style.configure("TProgressbar", background=c["primary"],
                    troughcolor=c["field_bg"], bordercolor=c["border"])

    style.configure("Treeview", background=c["card"],
                    foreground=c["field_fg"], fieldbackground=c["card"],
                    bordercolor=c["border"], rowheight=24)
    style.configure("Treeview.Heading", background=c["button_bg"],
                    foreground=c["fg"], relief="flat", padding=(6, 4))
    style.map("Treeview",
              background=[("selected", c["button_active"])],
              foreground=[("selected", c["fg"])])

    style.configure("TScrollbar", background=c["button_bg"],
                    troughcolor=c["bg"], bordercolor=c["bg"],
                    arrowcolor=c["hint"], relief="flat")
    style.map("TScrollbar",
              background=[("active", c["button_active"])])

    style.configure("TPanedwindow", background=c["bg"])
    style.configure("TSeparator", background=c["border"])
    style.configure("TMenubutton", background=c["button_bg"],
                    foreground=c["fg"])

    root.configure(bg=c["bg"])
    _restyle_plain_widgets(root, c)


def _restyle_plain_widgets(widget, c: dict):
    """Перекрашивает обычные tk-виджеты (не ttk) во всём дереве."""
    for child in widget.winfo_children():
        _restyle_plain_widgets(child, c)
        if isinstance(child, tk.Text):
            child.configure(bg=c["field_bg"], fg=c["field_fg"],
                            insertbackground=c["field_fg"],
                            selectbackground=c["select_bg"],
                            selectforeground=c["select_fg"],
                            highlightthickness=1,
                            highlightbackground=c["border"],
                            highlightcolor=c["primary"])
        elif isinstance(child, tk.Listbox):
            # у Listbox нет опции -insertbackground
            child.configure(bg=c["card"], fg=c["field_fg"],
                            selectbackground=c["button_active"],
                            selectforeground=c["fg"],
                            highlightthickness=1,
                            highlightbackground=c["border"],
                            highlightcolor=c["primary"])
        elif isinstance(child, tk.Spinbox):
            child.configure(bg=c["field_bg"], fg=c["field_fg"],
                            insertbackground=c["field_fg"],
                            buttonbackground=c["button_bg"],
                            selectbackground=c["select_bg"],
                            highlightthickness=1,
                            highlightbackground=c["border"],
                            highlightcolor=c["primary"])
        elif isinstance(child, tk.Canvas):
            child.configure(bg=c["bg"], highlightbackground=c["bg"])
        elif isinstance(child, tk.Frame):
            try:
                child.configure(bg=c["bg"])
            except tk.TclError:
                pass
        elif isinstance(child, tk.Label):
            try:
                child.configure(bg=c["bg"])
            except tk.TclError:
                pass
