"""
Темы оформления VUI ToolKit: светлая (по умолчанию) и тёмная.

Тёмная тема реализована поверх ttk-темы 'clam'; простые tk-виджеты
(Text, Listbox) перекрашиваются рекурсивным обходом дерева виджетов.
"""

import tkinter as tk
from tkinter import ttk

DARK = {
    "bg": "#2b2b2b",
    "fg": "#e8e8e8",
    "field_bg": "#3c3c3c",      # поля ввода, списки, текст
    "field_fg": "#f0f0f0",
    "select_bg": "#4a6fa5",
    "button_bg": "#404040",
    "button_active": "#505050",
    "border": "#555555",
    "hint": "#9a9a9a",          # приглушённый текст-подсказка
    "disabled_fg": "#7a7a7a",
}

LIGHT = {
    "bg": "#f0f0f0",
    "fg": "#000000",
    "field_bg": "#ffffff",
    "field_fg": "#000000",
    "select_bg": "#4a6fa5",
    "button_bg": "#e0e0e0",
    "button_active": "#d0d0d0",
    "border": "#adadad",
    "hint": "#666666",
    "disabled_fg": "#6d6d6d",
}

_current = LIGHT


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

    style.configure(".", background=c["bg"], foreground=c["fg"],
                    bordercolor=c["border"], font=("Segoe UI", 10))
    style.configure("TFrame", background=c["bg"])
    style.configure("TLabel", background=c["bg"], foreground=c["fg"])
    style.configure("TLabelframe", background=c["bg"], foreground=c["fg"],
                    bordercolor=c["border"])
    style.configure("TLabelframe.Label", background=c["bg"],
                    foreground=c["fg"])
    style.configure("TButton", background=c["button_bg"], foreground=c["fg"],
                    bordercolor=c["border"], focusthickness=1)
    style.map("TButton",
              background=[("active", c["button_active"])],
              foreground=[("disabled", c["disabled_fg"])])
    style.configure("TCheckbutton", background=c["bg"], foreground=c["fg"])
    style.map("TCheckbutton",
              foreground=[("disabled", c["disabled_fg"])])
    style.configure("TRadiobutton", background=c["bg"], foreground=c["fg"])
    style.configure("TEntry", fieldbackground=c["field_bg"],
                    foreground=c["field_fg"], bordercolor=c["border"])
    style.configure("TCombobox", fieldbackground=c["field_bg"],
                    foreground=c["field_fg"], bordercolor=c["border"],
                    background=c["button_bg"])
    style.map("TCombobox",
              fieldbackground=[("readonly", c["field_bg"])],
              foreground=[("readonly", c["field_fg"])])
    style.configure("TNotebook", background=c["bg"],
                    bordercolor=c["border"])
    style.configure("TNotebook.Tab", padding=(14, 6),
                    background=c["button_bg"], foreground=c["fg"])
    style.map("TNotebook.Tab",
              background=[("selected", c["field_bg"])])
    style.configure("TProgressbar", background=c["select_bg"],
                    troughcolor=c["field_bg"], bordercolor=c["border"])
    style.configure("Treeview", background=c["field_bg"],
                    foreground=c["field_fg"], fieldbackground=c["field_bg"],
                    bordercolor=c["border"])
    style.configure("Treeview.Heading", background=c["button_bg"],
                    foreground=c["fg"])
    style.configure("TScrollbar", background=c["button_bg"],
                    troughcolor=c["bg"], bordercolor=c["border"])

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
                            highlightbackground=c["border"])
        elif isinstance(child, tk.Listbox):
            # у Listbox нет опции -insertbackground
            child.configure(bg=c["field_bg"], fg=c["field_fg"],
                            selectbackground=c["select_bg"],
                            highlightbackground=c["border"])
        elif isinstance(child, tk.Spinbox):
            child.configure(bg=c["field_bg"], fg=c["field_fg"],
                            insertbackground=c["field_fg"],
                            buttonbackground=c["button_bg"],
                            selectbackground=c["select_bg"],
                            highlightbackground=c["border"])
        elif isinstance(child, tk.Canvas):
            child.configure(bg=c["bg"], highlightbackground=c["bg"])
        elif isinstance(child, tk.Frame):
            try:
                child.configure(bg=c["bg"])
            except tk.TclError:
                pass
