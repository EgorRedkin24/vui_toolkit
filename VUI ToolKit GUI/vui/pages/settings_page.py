"""Страница настроек приложения."""

import flet as ft

from vui.colors import c
from vui.controls import labeled, seg, txt, notice
from vui.pages.base import ToolPage
from vui import store


class SettingsPage(ToolPage):
    def __init__(self, page):
        super().__init__(
            page, "Настройки",
            "Тема интерфейса и ключи API, которые подставляются в формы.")
        self.page_ref = page

        saved = store.load()
        self.hf_token = txt(saved.get("hf_token", ""),
                            lambda v: setattr(self, "_hf", v), password=True)
        self.el_key = txt(saved.get("elevenlabs_api_key", ""),
                          lambda v: setattr(self, "_elk", v), password=True)
        self.el_voice = txt(saved.get("elevenlabs_voice_id", ""),
                            lambda v: setattr(self, "_elv", v))

        self.build_form([
            labeled("Токен Hugging Face", self.hf_token,
                    hint="Используется в диаризации"),
            labeled("API-ключ ElevenLabs", self.el_key),
            labeled("Voice ID ElevenLabs по умолчанию", self.el_voice),
            notice("Значения сохраняются в настройки при запуске задачи "
                   "или по кнопке ниже.", "info"),
        ])

        save_btn = ft.FilledButton(
            "Сохранить настройки", icon=ft.Icons.SAVE,
            on_click=self._save)
        self.form_sections.controls.append(save_btn)

        # настройки не запускают задач — прячем кнопку запуска и панель
        self.run_btn.visible = False
        self.panel.visible = False

    def _val(self, attr, field):
        return (getattr(self, attr, None) or field.value or "").strip()

    def _save(self, _e):
        data = store.load()
        data["hf_token"] = self._val("_hf", self.hf_token)
        data["elevenlabs_api_key"] = self._val("_elk", self.el_key)
        data["elevenlabs_voice_id"] = self._val("_elv", self.el_voice)
        store.save(data)
        self.page_ref.show_dialog(ft.SnackBar(ft.Text("Настройки сохранены.")))

    def collect(self):
        # настройки не запускают задач — кнопка запуска скрыта
        raise ValueError("Настройки сохраняются кнопкой «Сохранить»")
