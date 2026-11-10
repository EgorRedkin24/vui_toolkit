"""Точка входа VUI ToolKit API. Запуск: python run.py"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "api.app:app",
        host=os.environ.get("VUI_HOST", "0.0.0.0"),
        port=int(os.environ.get("VUI_PORT", "8000")),
        reload=False,
    )
