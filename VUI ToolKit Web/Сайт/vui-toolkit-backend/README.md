# VUI ToolKit — Backend API

Веб-бэкенд для VUI ToolKit: тот же движок (`core/`), что и в десктопной
версии, но с HTTP API (FastAPI) вместо tkinter-интерфейса. Фронтенд
(например, собранный в Lovable) общается с этим сервисом по REST.

## Возможности (7 инструментов)

1. **Обработка аудио** — пресеты и конструктор пайплайнов из 14 эффектов,
   предпрослушивание, выбор формата (WAV/FLAC/OGG/MP3) и PCM-разрядности.
2. **VAD (Silero)** — нарезка на фрагменты речи или пауз + таблица
   длительностей (xlsx/csv).
3. **Диаризация (pyannote)** — разделение спикеров, нужен HF-токен.
4. **Склейка аудио** — объединение записей с паузами, выбор частоты.
5. **TTS** — ElevenLabs (API) и OmniVoice (локальное клонирование голоса),
   одна фраза или таблица.
6. **Поиск и разметка** — поиск слов/словосочетаний через Whisper,
   .seg-разметка (UTF-8 BOM), неточное совпадение.
7. **Метаданные** — генерация `db_va_data_ai_assets_by_groups` из таблицы
   с нарезкой аудио по .seg и текстовый предпросмотр.

## Быстрый старт (ноутбук как сервер)

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
# Тяжёлые ML-зависимости — по мере необходимости (см. комментарии в requirements.txt):
pip install torch torchaudio openai-whisper numba pyannote.audio
python run.py
```

Сервер поднимется на `http://0.0.0.0:8000` — доступен и с других устройств
в локальной сети по `http://<IP-ноутбука>:8000`. Интерактивная документация
API: `http://localhost:8000/docs`.

Переменные окружения (см. `.env.example`):

| Переменная | По умолчанию | Назначение |
|---|---|---|
| `VUI_HOST` | `0.0.0.0` | интерфейс прослушивания |
| `VUI_PORT` | `8000` | порт |
| `VUI_CORS_ORIGINS` | `*` | разрешённые origin фронтенда (через запятую) |
| `VUI_JOB_TTL_HOURS` | `24` | срок хранения результатов задач |

## Перенос на арендованный сервер

Ничего специфичного для ноутбука в коде нет: скопируйте папку на сервер,
установите зависимости, запустите через systemd/supervisor/Docker.
Для продакшена:

- задайте `VUI_CORS_ORIGINS` = домену вашего фронтенда (а не `*`);
- поставьте перед сервисом nginx/Caddy с HTTPS;
- GPU не обязателен, но ускорит Whisper/pyannote/OmniVoice в разы.

## Архитектура

```
vui-toolkit-backend/
├── run.py                 # python run.py -> uvicorn
├── requirements.txt
├── core/                  # движок из десктопной версии (без изменений)
└── api/
    ├── app.py             # FastAPI, CORS
    ├── jobs.py            # менеджер задач: потоки, прогресс, логи, отмена, TTL
    ├── services.py        # адаптеры HTTP -> core
    └── routes/
        ├── meta.py        # /api/health, capabilities, effects, options,
        │                  # presets, settings
        ├── tools.py       # POST /api/jobs/{process,vad,diarize,merge,tts,
        │                  #                 search,metadata}, предпросмотры
        └── job_control.py # GET /api/jobs/{id}, cancel, files, archive
```

**Модель задач.** Любая длинная операция — это job: `POST` создаёт задачу
и сразу возвращает `{"id": "..."}`; дальше фронтенд опрашивает
`GET /api/jobs/{id}` (раз в 0.5–1 с) и получает `status`, `progress.percent`,
`logs` и список `files` результата. `POST /api/jobs/{id}/cancel` — прерывание.
Файлы скачиваются поштучно (`files[].url`) или одним ZIP (`/archive`).
Результаты живут на диске `workspace/jobs/<id>/` и удаляются через 24 ч.

Загрузка файлов — `multipart/form-data`: параметры всегда в поле `params`
(JSON-строка), файлы — в полях `files`, `table`, `ref_audio`, `ref_files`.

## Замечания

- Токены (HF, ElevenLabs) можно передавать в каждом запросе или сохранить
  на сервере через `PUT /api/settings` (хранятся в открытом виде —
  это личный инструмент, как и раньше).
- Модели (Silero, Whisper, pyannote, OmniVoice) скачиваются при первом
  использовании — первый запуск функции может занять минуты.
- `GET /api/capabilities` сообщает фронтенду, какие опциональные
  зависимости установлены — недоступные функции можно скрывать в UI.

## Поддерживаемые аудиоформаты

На вход принимаются: **WAV, MP3, OGG, FLAC, M4A, AAC, WMA, OPUS, AIFF, WEBM, AMR**.
Форматы, которые не читаются soundfile напрямую (m4a, wma, webm и др.),
автоматически конвертируются в WAV при загрузке — для этого на сервере
должен быть установлен **ffmpeg** (`sudo apt install ffmpeg`,
на Windows: `winget install ffmpeg`, затем перезапуск терминала).
Запись результата в MP3 также идёт через ffmpeg, если установленная
libsndfile этого не умеет. Проверить наличие ffmpeg можно через
`GET /api/capabilities` (поле `ffmpeg`).
