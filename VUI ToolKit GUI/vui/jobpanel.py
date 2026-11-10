"""Панель задачи (прогресс, лог, результаты) и диспетчер запуска."""

import asyncio
import os

import flet as ft

from core import playback
from vui import runner, services
from vui.colors import c
from vui.controls import card, fmt_size

_RUNNING = {"queued", "running"}

_STATUS_TEXT = {"queued": "В очереди", "running": "Выполняется…",
                "done": "Готово", "error": "Ошибка", "canceled": "Прервано"}


class JobPanel(ft.Container):
    """Правая колонка страницы инструмента: прогресс, лог, результаты."""

    def __init__(self, page):
        super().__init__(width=420, bgcolor=c("card"),
                         border=ft.Border.all(1, c("border")),
                         border_radius=14, padding=16,
                         shadow=ft.BoxShadow(blur_radius=18, color=c("shadow"),
                                             offset=ft.Offset(0, 3)))
        self.page_ref = page
        self._job = None
        self._log_index = 0

        self.status_text = ft.Text("Задача ещё не запущена", size=13,
                                   color=c("hint"), expand=True)
        self.progress = ft.ProgressBar(value=0, color=c("primary"),
                                       bgcolor=c("secondary"), height=6)
        self.cancel_btn = ft.TextButton(
            "Прервать", icon=ft.Icons.STOP,
            on_click=self._cancel, disabled=True)
        self.log_view = ft.ListView(
            controls=[], height=260, spacing=2,
            auto_scroll=True)
        self.results = ft.Column(spacing=4, tight=True)
        self.open_all_btn = ft.TextButton(
            "Открыть папку результатов", icon=ft.Icons.FOLDER_OPEN,
            on_click=self._open_outputs, visible=False)

        self.content = ft.Column([
            ft.Text("Задача", size=13, weight=ft.FontWeight.W_600,
                    color=c("fg")),
            ft.Row([self.status_text, self.cancel_btn],
                   vertical_alignment=ft.CrossAxisAlignment.CENTER),
            self.progress,
            ft.Container(self.log_view, bgcolor=c("bg"), border_radius=8,
                         padding=8, border=ft.Border.all(1, c("border"))),
            ft.Column([self.results], tight=True),
            self.open_all_btn,
        ], spacing=10, tight=True)

    # ------------------------------------------------------------ запуск
    def submit(self, tool, params, files=None, table=None, ref_audio=None,
               ref_files=None):
        """Диспетчер: собирает задачу и запускает её в потоке."""
        try:
            job, args, kwargs = _prepare(tool, params, files, table,
                                         ref_audio, ref_files)
        except ValueError as e:
            _snack(self.page_ref, str(e), error=True)
            return None

        self._reset()
        self._job = job
        runner.run_job(job, *args, **kwargs)
        self.page_ref.run_task(self._watch)
        return job

    def _reset(self):
        self._log_index = 0
        self.log_view.controls.clear()
        self.results.controls.clear()
        self.progress.value = 0
        self.open_all_btn.visible = False
        self.cancel_btn.disabled = False

    # ------------------------------------------------------------- поллинг
    async def _watch(self):
        job = self._job
        while job["status"] in _RUNNING:
            self._render(job)
            try:
                await self.update_async()
            except Exception:
                return
            await asyncio.sleep(0.3)
        self._render(job, final=True)
        try:
            await self.update_async()
        except Exception:
            pass

    def _render(self, job, final=False):
        status = job["status"]
        self.status_text.value = _STATUS_TEXT.get(status, status)
        self.status_text.color = (c("destructive") if status == "error"
                                  else c("hint"))
        pct = job["progress"]["percent"]
        self.progress.value = min(1.0, pct / 100.0) if status != "done" else 1.0

        logs = job["logs"]
        for entry in logs[self._log_index:]:
            msg = entry["msg"]
            color = c("fg")
            if "ОШИБКА" in msg or "КРИТИЧЕСКАЯ" in msg:
                color = c("destructive")
            elif msg.startswith("  "):
                color = c("hint")
            self.log_view.controls.append(
                ft.Text(msg, size=11, color=color, selectable=True,
                        font_family="Consolas", no_wrap=False))
        if len(self.log_view.controls) > 400:
            del self.log_view.controls[:-300]
        self._log_index = len(logs)

        if final:
            self.cancel_btn.disabled = True
            if job["files"]:
                self._render_results(job)
                self.open_all_btn.visible = True

    def _render_results(self, job):
        self.results.controls.append(
            ft.Text("Результаты", size=12, weight=ft.FontWeight.W_600,
                    color=c("fg")))
        for f in job["files"]:
            row = ft.Row([
                ft.IconButton(ft.Icons.FOLDER_OPEN, icon_size=18,
                              tooltip="Открыть папку",
                              on_click=lambda _e, p=f["path"]:
                              playback.open_in_folder(p)),
                ft.IconButton(ft.Icons.PLAY_ARROW, icon_size=18,
                              tooltip="Прослушать",
                              on_click=lambda _e, p=f["path"]:
                              playback.play_file(p)),
                ft.Text(f["name"], size=12, color=c("fg"), expand=True,
                        selectable=True),
                ft.Text(fmt_size(f["size"]), size=11, color=c("hint")),
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=2)
            self.results.controls.append(row)

    # -------------------------------------------------------------- кнопки
    def _cancel(self, _e):
        if self._job:
            runner.cancel_job(self._job["id"])

    def _open_outputs(self, _e):
        if self._job:
            playback.open_in_folder(runner.outputs_dir(self._job["id"]))


def _snack(page, message, error=False):
    page.show_dialog(ft.SnackBar(
        content=ft.Text(message, color=c("primary_fg") if error else None),
        bgcolor=c("destructive") if error else None))


def _prepare(tool, params, files, table, ref_audio, ref_files):
    """Создаёт job, копирует входные файлы в её папку, выбирает целевую
    функцию. Бросает ValueError с понятным текстом при проблемах."""
    job = runner.create_job(tool, params)

    if tool == "process":
        steps = services.resolve_pipeline(params)  # ValueError → текст
        paths = services.stage_files(job["id"], files or [])
        if not paths:
            raise ValueError("Добавьте хотя бы один аудиофайл")
        return job, (services.with_normalization, paths,
                     services.run_processing, steps,
                     (params.get("format") or "WAV").upper(),
                     params.get("subtype") or "PCM_16",
                     bool(params.get("keep_names"))), {}

    if tool in ("vad", "diarize", "merge", "search"):
        paths = services.stage_files(job["id"], files or [])
        if not paths:
            raise ValueError("Добавьте хотя бы один аудиофайл")
        target = {"vad": services.run_vad, "diarize": services.run_diarization,
                  "merge": services.run_merge, "search": services.run_search}[tool]
        return job, (services.with_normalization, paths, target, params), {}

    if tool == "tts":
        if params.get("mode") == "table" and not table:
            raise ValueError("В режиме «таблица» нужен файл таблицы")
        table_path = services.stage_file(job["id"], table) if table else None
        ref_path = (services.stage_file(job["id"], ref_audio)
                    if ref_audio else None)
        ref_pool = {}
        for f in (ref_files or []):
            ref_pool[os.path.basename(f)] = services.stage_file(job["id"], f)
        return job, (services.run_tts, params, table_path, ref_path,
                     ref_pool or None), {}

    if tool == "metadata":
        if not table:
            raise ValueError("Нужна таблица (xlsx/csv)")
        table_path = services.stage_file(job["id"], table)
        if files:
            services.stage_files(job["id"], files)
        cfg = services.metadata_cfg(params, table_path,
                                    runner.uploads_dir(job["id"]), job)
        return job, (services.run_metadata, cfg), {}

    raise ValueError(f"Неизвестный инструмент: {tool}")
