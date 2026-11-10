"""VUI ToolKit — точка входа.

По умолчанию запускает новый веб-интерфейс (дизайн из папки «Сайт»):
поднимает локальный бэкенд (порт 8000) и фронтенд (порт 5173),
затем открывает браузер.

Старый десктопный GUI (tkinter) доступен так:
    python main.py --desktop
Он также запускается автоматически, если в системе не найден Node.js.

Порт фронтенда можно переопределить: python main.py --port 7100
Python для бэкенда выбирается так: VUI_PYTHON, интерпретатор, запустивший
main.py (если в нём есть fastapi), py -3.10, python.
"""

import os
import shutil
import subprocess
import sys
import time
import urllib.request
import webbrowser

ROOT = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.join(ROOT, "Сайт", "snail-voice-forge")
DEV_SCRIPT = os.path.join(FRONTEND_DIR, "scripts", "dev.mjs")


def _arg_value(name, default=None):
    if name in sys.argv:
        i = sys.argv.index(name)
        if i + 1 < len(sys.argv):
            return sys.argv[i + 1]
    return default


def _run_desktop():
    from gui.app import main as desktop_main
    desktop_main()


def _wait_for(url, timeout_s=90):
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=3) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            time.sleep(1)
    return False


def _run_web():
    node = shutil.which("node")
    if not node or not os.path.isfile(DEV_SCRIPT):
        print("Node.js или папка Сайт\\snail-voice-forge не найдены — "
              "открываю старый интерфейс.\n"
              "(веб-интерфейс: установите Node.js и запустите снова; "
              "либо явно: python main.py --desktop)")
        _run_desktop()
        return

    port = _arg_value("--port", "5173")
    print(f"Запуск VUI ToolKit (веб-интерфейс)...\n"
          f"  интерфейс: http://localhost:{port}\n"
          f"  API:       http://localhost:8000\n"
          f"Остановка: закройте это окно или Ctrl+C.\n")

    proc = subprocess.Popen(
        [node, DEV_SCRIPT, "--port", port, "--strictPort"],
        cwd=FRONTEND_DIR,
        env={**os.environ,
             "VUI_PYTHON": _python_for_backend()},
    )
    try:
        if _wait_for(f"http://localhost:{port}/"):
            webbrowser.open(f"http://localhost:{port}/")
        else:
            print("Фронтенд не ответил вовремя — проверьте сообщения выше.")
        proc.wait()
    except KeyboardInterrupt:
        pass
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


def _python_for_backend():
    """Интерпретатор с fastapi/uvicorn для бэкенда."""
    if os.environ.get("VUI_PYTHON"):
        return os.environ["VUI_PYTHON"]
    # интерпретатор, запустивший main.py, — если в нём есть зависимости
    try:
        subprocess.run(
            [sys.executable, "-c", "import fastapi, uvicorn"],
            capture_output=True, timeout=30)
        return sys.executable
    except Exception:
        pass
    return ""  # dev.mjs сам попробует py -3.10 / python


if __name__ == "__main__":
    if "--desktop" in sys.argv:
        _run_desktop()
    else:
        _run_web()
