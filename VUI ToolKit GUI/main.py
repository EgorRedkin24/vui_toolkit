"""VUI ToolKit — точка входа. Запуск: python main.py"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from vui.app import main

if __name__ == "__main__":
    import flet as ft
    ft.run(main)
