"""FastAPI-приложение VUI ToolKit."""

import os
import sys
import threading
import time

# core/ импортируется как пакет от корня проекта
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api import jobs as job_store
from api.routes import job_control, meta, tools


def create_app() -> FastAPI:
    app = FastAPI(
        title="VUI ToolKit API",
        version="1.0.0",
        description="Бэкенд для веб-версии VUI ToolKit: обработка аудио, "
                    "VAD, диаризация, склейка, TTS, поиск слов, метаданные.",
    )

    # Локальный запуск: фронтенд (Lovable/dev-сервер) на другом порту.
    # Для продакшена сузьте список origins до домена фронтенда.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=os.environ.get("VUI_CORS_ORIGINS", "*").split(","),
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(meta.router)
    app.include_router(tools.router)
    app.include_router(job_control.router)

    @app.on_event("startup")
    def _start_cleaner():
        def _loop():
            while True:
                job_store.cleanup_old_jobs()
                time.sleep(3600)
        threading.Thread(target=_loop, daemon=True).start()

    return app


app = create_app()
