"""Палитра Flet-версии — те же токены, что и веб-интерфейс (styles.css)."""

DARK = {
    "bg": "#070a12",
    "card": "#0f131f",
    "popover": "#131824",
    "border": "#222838",
    "fg": "#e8ebf4",
    "hint": "#8b92a4",
    "primary": "#9281ff",
    "primary_fg": "#f2f0ff",
    "secondary": "#1a1f2c",
    "accent": "#252641",
    "success": "#00ce88",
    "warning": "#e9b543",
    "destructive": "#ff6467",
    "shadow": "#00000000",
}

LIGHT = {
    "bg": "#f5f6fa",
    "card": "#ffffff",
    "popover": "#ffffff",
    "border": "#e5e7f0",
    "fg": "#141828",
    "hint": "#5f6678",
    "primary": "#6a5aec",
    "primary_fg": "#ffffff",
    "secondary": "#eef0f7",
    "accent": "#e7e4fd",
    "success": "#0da271",
    "warning": "#a97b12",
    "destructive": "#dc2626",
    "shadow": "#1a1f2c14",
}

_current = DARK


def set_dark(dark: bool):
    global _current
    _current = DARK if dark else LIGHT


def c(key: str) -> str:
    return _current[key]
