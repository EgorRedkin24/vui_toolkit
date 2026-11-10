"""Страница «Обработка аудио» — пайплайн эффектов."""

import os
import threading

import flet as ft

from core import playback
from vui.colors import c
from vui import runner, services
from vui.controls import (AudioFilesPicker, OutputDirPicker, labeled, seg,
                          txt, drop, switch, notice, is_mounted)
from vui.pages.base import ToolPage
from core.effects import EFFECTS, PRESETS
from core.presets import load_user_presets, save_user_preset, \
    delete_user_preset
from core.audio_io import SAVE_FORMATS


class ProcessPage(ToolPage):
    def __init__(self, page):
        super().__init__(
            page, "Обработка аудио",
            "Пакетно применяйте эффекты к записям: пресеты или свой пайплайн.")
        self.page_ref = page

        # --- источник
        self.files_picker = AudioFilesPicker(page, "Аудиофайлы")

        # --- режим: пресет / пайплайн
        self.mode = "preset"
        self.mode_seg = seg(
            [("preset", "Пресет"), ("pipeline", "Свой пайплайн")],
            "preset", self._set_mode)

        # пресеты
        self.preset_names = []
        self.preset_drop = drop([], "", self._on_preset, width=280)
        self._reload_presets(select=None)

        self.btn_edit = ft.TextButton("Редактировать",
                                      on_click=self._edit_preset)
        self.btn_del = ft.TextButton("Удалить", on_click=self._del_preset)
        self.btn_add_to_preset = ft.OutlinedButton(
            "＋ Добавить эффект к пресету", on_click=self._add_to_preset)

        self.preset_row = ft.Column([
            labeled("Пресет", ft.Row([
                self.preset_drop, self.btn_edit, self.btn_del,
                self.btn_add_to_preset],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                wrap=True)),
        ], tight=True)

        # конструктор пайплайна
        self.steps = []          # [{"effect": id, "params": {...}}]
        self.steps_list = ft.Column(spacing=4, tight=True)
        self.btn_add_step = ft.OutlinedButton(
            "＋ Добавить эффект", on_click=self._add_step)
        self.pipeline_col = ft.Column([
            self.steps_list,
            self.btn_add_step,
        ], tight=True, visible=False)

        self._render_steps()

        # --- тишина по краям
        self.sil_start_on = False
        self.sil_end_on = False
        sil_start = ft.Row([
            switch(False, self._sil_start, "Тишина в начале"),
            txt("0.2", self._sil_start_dur_ch, width=70),
            ft.Text("с", size=12, color=c("hint")),
        ], vertical_alignment=ft.CrossAxisAlignment.CENTER)
        sil_end = ft.Row([
            switch(False, self._sil_end, "Тишина в конце"),
            txt("0.2", self._sil_end_dur_ch, width=70),
            ft.Text("с", size=12, color=c("hint")),
        ], vertical_alignment=ft.CrossAxisAlignment.CENTER)

        # --- формат
        self.format = "WAV"
        self.subtype = "PCM_16"
        self.fmt_drop = drop(
            [(k, k) for k in SAVE_FORMATS], "WAV", self._set_format,
            width=110)
        self.sub_drop = drop(
            [(s, s) for s in SAVE_FORMATS["WAV"]["subtypes"]], "PCM_16",
            lambda v: setattr(self, "subtype", v), width=120)
        self.keep_names = False

        # --- имена результатов
        self.naming_mode = "source"
        self.name_seg = seg(
            [("source", "Как исходники"), ("template", "Шаблон с {n}"),
             ("single", "Своё имя")],
            "source", self._set_naming)
        self.tmpl_field = txt("track_{n}", self._set_tmpl, width=220)
        self.single_field = txt("result", self._set_single_name, width=220)
        self.tmpl_field.visible = False
        self.single_field.visible = False

        self.out_dir_picker = OutputDirPicker(page)

        format_row = labeled(
            "Формат сохранения",
            ft.Row([self.fmt_drop, self.sub_drop],
                   vertical_alignment=ft.CrossAxisAlignment.CENTER))

        naming_col = ft.Column([
            ft.Text("Имена файлов результатов", size=13,
                    weight=ft.FontWeight.W_600, color=c("fg")),
            self.name_seg,
            ft.Row([self.tmpl_field, self.single_field],
                   vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ft.Text("Расширение (.wav и т.п.) добавляется автоматически — "
                    "указывайте имя без него. По умолчанию: "
                    "<имя исходника>_processed.<расширение>.",
                    size=11, color=c("hint")),
        ], tight=True, spacing=6)

        # --- предпросмотр
        self.btn_preview = ft.OutlinedButton(
            "Предпросмотр первого файла", icon=ft.Icons.PLAY_CIRCLE,
            on_click=self._preview)

        self.build_form([
            self.files_picker,
            self.mode_seg,
            self.preset_row,
            self.pipeline_col,
            ft.Column([sil_start, sil_end], tight=True, spacing=4),
            format_row,
            switch(False, lambda v: setattr(self, "keep_names", v),
                   "Не добавлять суффикс _processed к именам файлов"),
            naming_col,
            self.out_dir_picker,
            ft.Row([self.btn_preview,
                    ft.Text("обрабатывает первый файл текущими настройками",
                            size=11, color=c("hint"))],
                   vertical_alignment=ft.CrossAxisAlignment.CENTER),
        ])

    # ------------------------------------------------------------- пресеты
    def _reload_presets(self, select=""):
        builtin = list(PRESETS)
        user = list(load_user_presets())
        self.preset_names = builtin + ["★ " + n for n in user]
        self.preset_drop.options = [
            ft.dropdown.Option(n, n) for n in self.preset_names]
        if select and select in self.preset_names:
            self.preset_drop.value = select
        elif self.preset_names:
            self.preset_drop.value = self.preset_names[0]
        if is_mounted(self.preset_drop):
            self.preset_drop.update()

    def _on_preset(self, name):
        pass  # значение лежит в preset_drop.value

    def _set_mode(self, mode):
        self.mode = mode
        self.preset_row.visible = mode == "preset"
        self.pipeline_col.visible = mode == "pipeline"
        self.preset_row.update()
        self.pipeline_col.update()

    def _selected_preset_name(self):
        return (self.preset_drop.value or "").strip()

    # ---------------------------------------------------- конструктор шагов
    def _render_steps(self):
        self.steps_list.controls.clear()
        if not self.steps:
            self.steps_list.controls.append(
                ft.Text("Эффектов пока нет", size=12, color=c("hint")))
        for i, step in enumerate(self.steps):
            title = EFFECTS[step["effect"]]["title"]
            params = ", ".join(f"{k}={v}" for k, v in
                               step["params"].items())
            row = ft.Row([
                ft.Text(f"{i + 1}. {title}", size=13, color=c("fg"),
                        expand=True),
                ft.Text(params, size=11, color=c("hint")),
                ft.IconButton(ft.Icons.ARROW_UPWARD, icon_size=16,
                              tooltip="Выше",
                              on_click=lambda _e, idx=i: self._move(idx, -1)),
                ft.IconButton(ft.Icons.ARROW_DOWNWARD, icon_size=16,
                              tooltip="Ниже",
                              on_click=lambda _e, idx=i: self._move(idx, +1)),
                ft.IconButton(ft.Icons.DELETE_OUTLINE, icon_size=16,
                              tooltip="Удалить",
                              on_click=lambda _e, idx=i: self._del(idx)),
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=2)
            self.steps_list.controls.append(row)
        if is_mounted(self.steps_list):
            self.steps_list.update()

    def _move(self, i, d):
        j = i + d
        if 0 <= j < len(self.steps):
            self.steps[i], self.steps[j] = self.steps[j], self.steps[i]
            self._render_steps()

    def _del(self, i):
        del self.steps[i]
        self._render_steps()

    def _add_step(self, _e=None, initial=None):
        """Диалог добавления эффекта в пайплайн (или в пресет)."""
        effect_id = ft.Ref[ft.Dropdown]()
        params_col = ft.Ref[ft.Column]()
        state = {"effect": None, "fields": {}}

        def build_params(eff):
            state["effect"] = eff
            state["fields"] = {}
            params_col.current.controls.clear()
            spec = EFFECTS[eff]
            for name, p in spec["params"].items():
                field = txt(str(p["default"]),
                            lambda v, n=name: state["fields"].__setitem__(n, v),
                            width=140)
                state["fields"][name] = str(p["default"])
                params_col.current.controls.append(
                    ft.Row([
                        ft.Text(p["label"], size=12, color=c("fg"),
                                width=210),
                        field,
                    ], vertical_alignment=ft.CrossAxisAlignment.CENTER))
            if spec.get("note"):
                params_col.current.controls.append(
                    notice(spec["note"], "warning"))
            params_col.current.update()

        def on_effect(_e):
            build_params(effect_id.current.value)

        effect_id.current = ft.Dropdown(
            options=[ft.dropdown.Option(k, v["title"])
                     for k, v in EFFECTS.items()],
            value=initial or next(iter(EFFECTS)),
            width=300, color=c("fg"), on_change=on_effect)

        def do_add(_e):
            eff = effect_id.current.value
            params = {}
            spec = EFFECTS[eff]
            for name, p in spec["params"].items():
                raw = state["fields"].get(name, str(p["default"]))
                try:
                    params[name] = p["type"](float(raw))
                except (TypeError, ValueError):
                    params[name] = p["default"]
            dlg.open = False
            self.page_ref.update()
            if initial is not None:
                # режим «добавить к пресету»
                name = self._selected_preset_name().lstrip("★ ").strip()
                if not name:
                    return
                user = load_user_presets()
                steps = list(user.get(name, PRESETS.get(name, [])))
                steps.append({"effect": eff, "params": params})
                save_user_preset(name, steps)
                self.page_ref.show_dialog(ft.SnackBar(
                    ft.Text(f"Эффект добавлен в пресет «{name}».")))
            else:
                self.steps.append({"effect": eff, "params": params})
                self._render_steps()

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("Добавить эффект", color=c("fg")),
            content=ft.Column([
                ft.Text("Эффект", size=12, color=c("hint")),
                effect_id.current,
                ft.Column([], ref=params_col, tight=True, spacing=8),
            ], tight=True, spacing=8, width=460),
            actions=[
                ft.TextButton("Отмена", on_click=lambda _e: (
                    setattr(dlg, "open", False), self.page_ref.update())),
                ft.FilledButton("Добавить", on_click=do_add),
            ])
        self.page_ref.show_dialog(dlg)
        build_params(effect_id.current.value)

    def _add_to_preset(self, _e):
        name = self._selected_preset_name()
        if not name:
            return
        if not name.startswith("★"):
            self.page_ref.show_dialog(ft.SnackBar(ft.Text(
                "Можно редактировать только пользовательские пресеты (★).")))
            return
        self._add_step(initial="add_random_noise")

    def _edit_preset(self, _e):
        name = self._selected_preset_name()
        if not name:
            return
        if not name.startswith("★"):
            self.page_ref.show_dialog(ft.SnackBar(ft.Text(
                "Встроенные пресеты не редактируются — сохраните свой.")))
            return
        name = name.lstrip("★ ").strip()
        user = load_user_presets()
        self.steps = [dict(s, params=dict(s["params"]))
                      for s in user.get(name, [])]
        self._set_mode("pipeline")
        self.mode_seg.selected = ["pipeline"]
        self.mode_seg.update()
        self._render_steps()
        self.page_ref.show_dialog(ft.SnackBar(ft.Text(
            f"Пресет «{name}» загружен в конструктор. После правок — "
            f"«Сохранить как пресет».")))

    def _del_preset(self, _e):
        name = self._selected_preset_name()
        if not name:
            return
        if not name.startswith("★"):
            self.page_ref.show_dialog(ft.SnackBar(ft.Text(
                "Встроенные пресеты удалить нельзя.")))
            return
        name = name.lstrip("★ ").strip()
        delete_user_preset(name)
        self._reload_presets()
        self.page_ref.show_dialog(ft.SnackBar(ft.Text(f"Пресет «{name}» удалён.")))

    # -------------------------------------------------------------- тишина
    def _sil_start(self, v):
        self.sil_start_on = bool(v)

    def _sil_end(self, v):
        self.sil_end_on = bool(v)

    def _sil_start_dur_ch(self, v):
        self._sil_start_dur = v

    def _sil_end_dur_ch(self, v):
        self._sil_end_dur = v

    @property
    def sil_start_dur(self):
        return self._parse_float(getattr(self, "_sil_start_dur", "0.2"), 0.2)

    @property
    def sil_end_dur(self):
        return self._parse_float(getattr(self, "_sil_end_dur", "0.2"), 0.2)

    @staticmethod
    def _parse_float(raw, default):
        try:
            return float(str(raw).replace(",", "."))
        except (TypeError, ValueError):
            return default

    # -------------------------------------------------------------- формат
    def _set_format(self, fmt):
        self.format = fmt
        subs = SAVE_FORMATS[fmt]["subtypes"]
        self.sub_drop.options = [ft.dropdown.Option(s, s) for s in subs]
        self.sub_drop.value = subs[0] if subs else None
        self.subtype = subs[0] if subs else ""
        self.sub_drop.update()

    # -------------------------------------------------------------- имена
    def _set_naming(self, mode):
        self.naming_mode = mode
        self.tmpl_field.visible = mode == "template"
        self.single_field.visible = mode == "single"
        for ctrl in (self.tmpl_field, self.single_field):
            if is_mounted(ctrl):
                ctrl.update()

    def _set_tmpl(self, v):
        self._tmpl = v

    def _set_single_name(self, v):
        self._single_name = v

    # ------------------------------------------------------------ параметры
    def _current_params(self):
        return {
            "mode": self.mode,
            "preset_name": self._selected_preset_name(),
            "steps": [dict(s, params=dict(s["params"])) for s in self.steps],
            "silence_start": {"enabled": self.sil_start_on,
                              "duration": self.sil_start_dur},
            "silence_end": {"enabled": self.sil_end_on,
                            "duration": self.sil_end_dur},
            "format": self.format,
            "subtype": self.subtype or None,
            "keep_names": self.keep_names,
            "naming": {
                "mode": self.naming_mode,
                "template": (getattr(self, "_tmpl", None)
                             or self.tmpl_field.value or "track_{n}").strip(),
                "name": (getattr(self, "_single_name", None)
                         or self.single_field.value or "result").strip(),
            },
            "output_dir": self.out_dir_picker.get_dir(),
        }

    def collect(self):
        files = self.files_picker.get_files()
        if not files:
            raise ValueError("Добавьте хотя бы один аудиофайл")
        if self.mode == "preset" and not self._selected_preset_name():
            raise ValueError("Выберите пресет")
        return {"tool": "process", "params": self._current_params(),
                "files": files}

    # ---------------------------------------------------------- предпросмотр
    def _preview(self, _e):
        files = self.files_picker.get_files()
        if not files:
            self.page_ref.show_dialog(ft.SnackBar(ft.Text(
                "Сначала выберите аудиофайл.")))
            return
        params = self._current_params()
        try:
            services.resolve_pipeline(params)
        except ValueError as ex:
            self.page_ref.show_dialog(ft.SnackBar(
                ft.Text(str(ex), color=c("primary_fg")),
                bgcolor=c("destructive")))
            return

        job = runner.create_job("preview", params)
        uploaded = services.stage_file(job["id"], files[0])
        path_lbl = ft.Text("Обработка…", size=12, color=c("hint"))
        play_btn = ft.FilledTonalButton(
            "Прослушать", icon=ft.Icons.PLAY_ARROW, disabled=True,
            on_click=lambda _e: playback.play_file(path_lbl.data))
        open_btn = ft.TextButton(
            "Открыть папку", on_click=lambda _e:
            playback.open_in_folder(path_lbl.data))

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("Предпросмотр", color=c("fg")),
            content=ft.Column([path_lbl], tight=True, width=420),
            actions=[play_btn, open_btn,
                     ft.TextButton("Закрыть", on_click=lambda _e: (
                         setattr(dlg, "open", False),
                         self.page_ref.update()))])
        self.page_ref.show_dialog(dlg)

        def work():
            try:
                uploaded_wav = services.normalize_audio(job["id"],
                                                        [uploaded])[0]
                out = services.process_preview(job, uploaded_wav, params)
                path_lbl.data = out
                path_lbl.value = "Готово: " + out.split(os.sep)[-1]
                runner.add_log(job, f"Предпросмотр сохранён: {out}")
            except Exception as ex:
                path_lbl.value = f"Ошибка: {ex}"
            path_lbl.update()
            play_btn.disabled = not path_lbl.data
            open_btn.disabled = not path_lbl.data
            play_btn.update()
            open_btn.update()

        threading.Thread(target=work, daemon=True).start()
