"""Страница «TTS» — синтез речи (ElevenLabs / OmniVoice)."""

import os

import flet as ft

from vui.colors import c
from vui.controls import AudioFilesPicker, FilePickField, OutputDirPicker, \
    labeled, seg, txt, drop, notice, is_mounted
from vui.pages.base import ToolPage
from vui import store
from core.audio_io import is_audio_file
from core.tts_elevenlabs import TTS_MODELS, DEFAULT_MODEL


class TtsPage(ToolPage):
    def __init__(self, page):
        super().__init__(
            page, "Синтез речи (TTS)",
            "Озвучивает текст или таблицу реплик. Имена файлов задаются "
            "в столбце filename таблицы или шаблоном с {n}.")
        self.page_ref = page

        saved = store.load()

        # --- движок и режим
        self.engine = "elevenlabs"
        self.mode = "single"

        engine_seg = seg(
            [("elevenlabs", "ElevenLabs"), ("omnivoice", "OmniVoice")],
            "elevenlabs", self._set_engine)
        mode_seg = seg([("single", "Один текст"), ("table", "Таблица")],
                       "single", self._set_mode)

        # --- ElevenLabs
        self.api_key = txt(saved.get("elevenlabs_api_key", ""),
                           lambda v: setattr(self, "_api_key", v),
                           password=True)
        self.voice_id = txt(saved.get("elevenlabs_voice_id", ""),
                            lambda v: setattr(self, "_voice_id", v))
        self.model_id = DEFAULT_MODEL
        model_drop = drop([(m, m) for m in TTS_MODELS], DEFAULT_MODEL,
                          lambda v: setattr(self, "model_id", v), width=260)

        self.el_col = ft.Column([
            labeled("API-ключ ElevenLabs", self.api_key),
            labeled("Voice ID", self.voice_id),
            labeled("Модель", model_drop),
        ], tight=True, spacing=10)

        # --- OmniVoice: эталон + пул эталонов
        self.ref_audio_picker = AudioFilesPicker(page,
                                                 "Эталонная запись голоса")

        self.ref_pool_files = []
        self.ref_pool_col = ft.Column(spacing=4, tight=True)
        self.ref_pool_picker = ft.FilePicker(on_result=self._on_pool_picked)
        pool_pick = ft.FilledTonalButton(
            "Добавить эталоны…", icon=ft.Icons.UPLOAD_FILE,
            on_click=lambda _e: page.run_task(self._pool_pick_async))
        pool_clear = ft.TextButton("Очистить", on_click=self._pool_clear)

        self.ov_col = ft.Column([
            self.ref_audio_picker,
            ft.Column([
                ft.Text("Пул эталонов для таблицы", size=13,
                        weight=ft.FontWeight.W_600, color=c("fg")),
                ft.Row([pool_pick, pool_clear]),
                self.ref_pool_col,
                ft.Text("Имена файлов должны совпадать со значениями "
                        "столбца voice в таблице", size=11, color=c("hint")),
            ], tight=True, spacing=6),
        ], tight=True, spacing=10, visible=False)
        self._render_pool()

        # --- режим single
        self.text_field = txt("", multiline=True, min_lines=6)
        self.single_name_field = txt(
            "tts_phrase", lambda v: setattr(self, "_single_name", v),
            width=240)
        self.single_col = ft.Column([
            labeled("Текст", self.text_field),
            labeled("Имя файла", self.single_name_field,
                    hint="Без расширения — добавится автоматически. "
                         "По умолчанию: tts_phrase (ElevenLabs) / "
                         "omnivoice_phrase (OmniVoice)"),
        ], tight=True, spacing=10)

        # --- режим table
        self.table_field = FilePickField(page, "Таблица реплик",
                                         extensions=["xlsx", "csv"])
        self.filename_template = txt(
            "", lambda v: setattr(self, "_tmpl", v), width=260)
        self.table_col = ft.Column([
            labeled("Таблица (xlsx/csv)", self.table_field,
                    hint="Колонки: text — текст реплики, voice — голос, "
                         "filename — имя файла (необязательно)"),
            labeled("Шаблон имён файлов", self.filename_template,
                    hint="Используется, если в таблице нет столбца filename. "
                         "{n} — номер реплики, например reply_{n:03}. "
                         "Расширение указывать не нужно — добавится "
                         "автоматически (.mp3 и т.п.)"),
            notice("Если задан и столбец filename, и шаблон — приоритет у "
                   "столбца. Имя из столбца можно писать с расширением или "
                   "без — расширение добавится, только если его нет.",
                   "info"),
        ], tight=True, spacing=10, visible=False)

        # --- формат синтеза
        self.container = "mp3"
        self.sr_choice = 24000
        self.bitrate = 128
        container_seg = seg(
            [("mp3", "MP3"), ("wav", "WAV (PCM)"), ("ogg", "OGG Vorbis")],
            "mp3", self._set_container)
        self.sr_drop = drop(
            [(str(s), f"{s} Гц") for s in (16000, 24000, 44100, 48000)],
            "24000", lambda v: setattr(self, "sr_choice", int(v)), width=130)
        self.br_drop = drop(
            [(str(b), f"{b} кбит/с") for b in (32, 64, 128, 192)],
            "128", lambda v: setattr(self, "bitrate", int(v)), width=130)
        self.sr_row = ft.Row([
            ft.Text("Частота дискретизации", size=12, color=c("hint")),
            self.sr_drop,
        ], vertical_alignment=ft.CrossAxisAlignment.CENTER,
            visible=False)
        self.br_row = ft.Row([
            ft.Text("Битрейт", size=12, color=c("hint")),
            self.br_drop,
        ], vertical_alignment=ft.CrossAxisAlignment.CENTER)
        self.fmt_col = ft.Column([
            ft.Text("Формат синтеза", size=13, weight=ft.FontWeight.W_600,
                    color=c("fg")),
            container_seg,
            self.sr_row,
            self.br_row,
            ft.Text("WAV: ElevenLabs отдаёт PCM выбранной частоты, OmniVoice "
                    "реземплирует с 24 кГц. MP3/OGG: битрейт применяется к "
                    "ElevenLabs (у OmniVoice свои настройки кодека).",
                    size=11, color=c("hint")),
        ], tight=True, spacing=8)

        self.out_dir_picker = OutputDirPicker(page)

        self.build_form([
            labeled("Движок", engine_seg),
            self.el_col,
            self.ov_col,
            labeled("Режим", mode_seg),
            self.single_col,
            self.table_col,
            self.fmt_col,
            self.out_dir_picker,
        ])

    async def _pool_pick_async(self):
        picked_files = await self.ref_pool_picker.pick_files(
            dialog_title="Эталонные записи голосов", allow_multiple=True)
        for f in (picked_files or []):
            if f.path and is_audio_file(f.path) \
                    and f.path not in self.ref_pool_files:
                self.ref_pool_files.append(f.path)
        self._render_pool()

    # ------------------------------------------------------------ пул ----
    def _on_pool_picked(self, e: ft.FilePickerResultEvent):
        for f in (e.files or []):
            if f.path and is_audio_file(f.path) \
                    and f.path not in self.ref_pool_files:
                self.ref_pool_files.append(f.path)
        self._render_pool()

    def _pool_clear(self, _e=None):
        self.ref_pool_files = []
        self._render_pool()

    def _pool_del(self, i):
        del self.ref_pool_files[i]
        self._render_pool()

    def _render_pool(self):
        self.ref_pool_col.controls.clear()
        if not self.ref_pool_files:
            self.ref_pool_col.controls.append(
                ft.Text("Эталоны не выбраны", size=12, color=c("hint")))
        for i, path in enumerate(self.ref_pool_files):
            self.ref_pool_col.controls.append(ft.Row([
                ft.Text(os.path.basename(path), size=12, color=c("fg"),
                        expand=True, selectable=True),
                ft.IconButton(ft.Icons.DELETE_OUTLINE, icon_size=16,
                              on_click=lambda _e, idx=i: self._pool_del(idx)),
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=2))
        if is_mounted(self.ref_pool_col):
            self.ref_pool_col.update()

    # ---------------------------------------------------------------------
    def _set_engine(self, v):
        self.engine = v
        is_el = v == "elevenlabs"
        self.el_col.visible = is_el
        self.ov_col.visible = not is_el
        self.el_col.update()
        self.ov_col.update()

    def _set_mode(self, v):
        self.mode = v
        self.single_col.visible = v == "single"
        self.table_col.visible = v == "table"
        self.single_col.update()
        self.table_col.update()

    def _set_container(self, v):
        self.container = v
        self.sr_row.visible = v == "wav"
        self.br_row.visible = v in ("mp3", "ogg")
        if is_mounted(self.sr_row):
            self.sr_row.update()
        if is_mounted(self.br_row):
            self.br_row.update()

    # ---------------------------------------------------------------------
    @property
    def api_key_val(self):
        return getattr(self, "_api_key", self.api_key.value) or ""

    @property
    def voice_id_val(self):
        return getattr(self, "_voice_id", self.voice_id.value) or ""

    @property
    def tmpl_val(self):
        return getattr(self, "_tmpl", self.filename_template.value) or ""

    def collect(self):
        params = {
            "engine": self.engine,
            "mode": self.mode,
            "filename_template": self.tmpl_val.strip() or None,
            "single_name": (getattr(self, "_single_name", None)
                            or self.single_name_field.value or "").strip()
                           or None,
            "output_dir": self.out_dir_picker.get_dir(),
            "audio_format": {
                "container": self.container,
                "sample_rate": self.sr_choice,
                "bitrate": self.bitrate,
            },
        }
        table = None
        ref_audio = None
        ref_files = None

        if self.engine == "elevenlabs":
            if not self.api_key_val.strip() or not self.voice_id_val.strip():
                raise ValueError("Для ElevenLabs нужны API-ключ и Voice ID")
            params.update({
                "api_key": self.api_key_val.strip(),
                "voice_id": self.voice_id_val.strip(),
                "model_id": self.model_id,
            })
            # сохраняем ключи на будущее
            saved = store.load()
            saved["elevenlabs_api_key"] = params["api_key"]
            saved["elevenlabs_voice_id"] = params["voice_id"]
            store.save(saved)
        else:
            refs = self.ref_audio_picker.get_files()
            if not refs and not self.ref_pool_files:
                raise ValueError("Для OmniVoice нужна эталонная запись")
            ref_audio = refs[0] if refs else None
            ref_files = list(self.ref_pool_files) or None

        if self.mode == "single":
            text = self.text_field.value or ""
            if not text.strip():
                raise ValueError("Введите текст для озвучки")
            params["text"] = text
        else:
            table = self.table_field.get()
            if not table:
                raise ValueError("Выберите таблицу реплик")

        return {"tool": "tts", "params": params, "table": table,
                "ref_audio": ref_audio, "ref_files": ref_files}
