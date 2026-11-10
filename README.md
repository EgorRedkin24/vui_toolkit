# VUI ToolKit

Набор инструментов для работы с аудио: обработка эффектами, детектор речи (VAD),
диаризация, склейка записей, синтез речи (ElevenLabs / OmniVoice), поиск слов
с разметкой и генерация метаданных реплик.

Один движок (`core/`) — два интерфейса: **веб-приложение** (React + FastAPI,
открывается в браузере) и **десктопное приложение** на Flet. Функционал
интерфейсов одинаковый.

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![React](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black)](https://react.dev/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110%2B-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Flet](https://img.shields.io/badge/Flet-1.0-00A8E8?logo=flutter&logoColor=white)](https://flet.dev/)

## Содержание

- [Возможности](#возможности)
- [Две версии](#две-версии)
- [Быстрый старт](#быстрый-старт)
- [Запуск для разработки](#запуск-для-разработки)
- [Настройки, данные и секреты](#настройки-данные-и-секреты)
- [HTTP API](#http-api)
- [Структура репозитория](#структура-репозитория)
- [Движок](#движок)
- [Форматы аудио](#форматы-аудио)
- [Особенности разметки `.seg`](#особенности-разметки-seg)
- [Частые проблемы](#частые-проблемы)
- [Лицензия](#лицензия)

## Возможности

| Инструмент | Что делает |
|---|---|
| **Обработка аудио** | 14 эффектов, встроенные и пользовательские пресеты, конструктор пайплайна, предпрослушивание «до/после», сохранение в WAV / FLAC / OGG / MP3 с выбором PCM-разрядности |
| **VAD (Silero)** | Нарезка на фрагменты речи или пауз с ограничениями минимальной/максимальной длительности, таблица длительностей (xlsx/csv) |
| **Диаризация (pyannote)** | Разделение спикеров моделью `pyannote/speaker-diarization-community-1`, результат — `<имя>_dia.txt` |
| **Склейка аудио** | Объединение записей в нужном порядке с паузами и выбором частоты дискретизации результата |
| **TTS** | ElevenLabs (API) или OmniVoice (локально, с клонированием голоса); одна фраза или таблица, имена файлов через `filename` и шаблон `{n}` |
| **Поиск и разметка** | Поиск слов и словосочетаний через Whisper, нечёткое совпадение, файл разметки `.seg` (UTF-8 с BOM) |
| **Метаданные** | Генерация `db_va_data_ai_assets_by_groups` из таблицы с нарезкой аудио по `.seg`, переменными и предпросмотром |

Общее для обоих интерфейсов:

- прогресс-бар и кнопка **«Прервать»** — длинную задачу можно остановить между файлами/строками;
- панель **«Результаты»** — созданные файлы можно прослушать или открыть в папке;
- **защита от перезаписи** — существующие файлы не затираются, к имени добавляется `_1`, `_2`, …;
- **тёмная и светлая темы**;
- настройки и токены сохраняются между запусками.

## Две версии

| | Веб-версия | Десктопная версия |
|---|---|---|
| Папка | `VUI ToolKit Web` | `VUI ToolKit GUI` |
| Интерфейс | Браузер: React 19, TanStack Start, Tailwind CSS, shadcn/ui | Окно приложения на Flet |
| Бэкенд | Локальный FastAPI (`:8000`) + dev-сервер Vite (`:5173`) | Встроен в приложение |
| Запуск | `python main.py` внутри папки | `python main.py` внутри папки |
| Требуется | Python, Node.js (для фронтенда) | Python |
| Где результаты | `workspace/jobs/<id>/` на бэкенде | `workspace/jobs/<id>/outputs` |

В корне лежит `Запустить VUI ToolKit.bat`: он спрашивает, какую версию открыть
(`1` — веб, `2` — десктоп).

Если Node.js не найден, веб-лаунчер автоматически открывает десктопный
tkinter-интерфейс (старая версия GUI лежит в `VUI ToolKit Web/gui/` и
`VUI ToolKit GUI/_backup_tkinter_gui/`, в обычном запуске не участвует).

## Быстрый старт

### Требования

| Компонент | Версия | Зачем |
|---|---|---|
| Python | 3.10+ | движок и оба интерфейса |
| Node.js | 20.19+ или 22.12+ | только для веб-интерфейса |
| ffmpeg | любая свежая | опционально: чтение m4a/wma/webm и запись MP3 |
| GPU (CUDA) | опционально | ускоряет Whisper, pyannote и OmniVoice |

### Веб-версия

```bash
cd "VUI ToolKit Web"
python -m venv .venv
.venv\Scripts\activate            # Linux/macOS: source .venv/bin/activate

pip install -r requirements.txt
pip install -r "Сайт/vui-toolkit-backend/requirements.txt"

cd "Сайт/snail-voice-forge"
npm install
cd ../..

python main.py                    # откроет http://localhost:5173
```

`python main.py` поднимает бэкенд (порт 8000) и фронтенд (порт 5173), ждёт
ответа API и открывает браузер. Остановка — `Ctrl+C` или закрыть окно.

Другой порт фронтенда: `python main.py --port 7100`.

Если тяжёлые ML-зависимости не нужны, вместо полного `requirements.txt`
достаточно установить только бэкенд-набор — обработка, склейка, TTS
ElevenLabs и метаданные будут работать без `torch`:

```bash
pip install -r "Сайт/vui-toolkit-backend/requirements.txt"
```

VAD, поиск слов (Whisper), диаризация и OmniVoice требуют `torch`,
`openai-whisper`, `pyannote.audio` и `omnivoice` — ставьте их по мере
необходимости (это несколько гигабайт).

### Десктопная версия

```bash
cd "VUI ToolKit GUI"
python -m venv .venv
.venv\Scripts\activate            # Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

Либо двойным кликом по `Запустить VUI ToolKit.bat` внутри папки (нужен
`python` в `PATH`).

## Запуск для разработки

Веб-версия запускается из папки `VUI ToolKit Web`:

| Команда | Что запускает |
|---|---|
| `python main.py` | бэкенд + фронтенд + браузер |
| `python main.py --desktop` | старый tkinter-GUI (без Node.js) |
| `cd "Сайт/snail-voice-forge" && npm run dev` | бэкенд + фронтенд (аргументы передаются в Vite) |
| `cd "Сайт/vui-toolkit-backend" && python run.py` | только API на `http://0.0.0.0:8000` |
| `cd "Сайт/snail-voice-forge" && npm run dev:web` | только фронтенд (API должен быть запущен) |

Интерактивная документация API — `http://localhost:8000/docs`.

Python для бэкенда ищется в таком порядке: переменная `VUI_PYTHON`, `py -3.10`,
`python`. Если в выбранном интерпретаторе нет `fastapi`/`uvicorn`, установите
зависимости бэкенда или задайте `VUI_PYTHON` вручную.

## Настройки, данные и секреты

| Файл | Где | Что хранит |
|---|---|---|
| `user_settings.json` | рядом с `main.py` | тема, `hf_token`, ключи ElevenLabs, последние режимы |
| `user_presets.json` | рядом с `main.py` | пользовательские пресеты обработки |
| `workspace/jobs/<id>/` | рядом с `main.py` | входные файлы, логи и результаты задач |
| `.env` | `Сайт/vui-toolkit-backend/` | настройки сервера (см. `.env.example`) |

> **Внимание:** токены и ключи хранятся в открытом виде. Не коммитьте
> `user_settings.json`, `user_presets.json` и `.env` — они уже в `.gitignore`.

Переменные окружения бэкенда:

| Переменная | По умолчанию | Назначение |
|---|---|---|
| `VUI_HOST` | `0.0.0.0` | интерфейс прослушивания |
| `VUI_PORT` | `8000` | порт API |
| `VUI_CORS_ORIGINS` | `*` | разрешённые origin фронтенда (через запятую) |
| `VUI_JOB_TTL_HOURS` | `24` | срок хранения результатов задач |

Модели (Silero, Whisper, pyannote, OmniVoice) скачиваются при первом
использовании функции — первый запуск может занять несколько минут.

## HTTP API

Базовый адрес — `http://localhost:8000/api`, документация — `/docs`.

| Метод | Путь | Назначение |
|---|---|---|
| `GET` | `/health` | проверка живости |
| `GET` | `/capabilities` | какие опциональные зависимости и ffmpeg доступны |
| `GET` | `/effects`, `/options` | список эффектов и параметров |
| `GET`/`POST`/`DELETE` | `/presets` | пользовательские пресеты |
| `GET`/`PUT` | `/settings` | токены и ключи на сервере |
| `POST` | `/jobs/{process,vad,diarize,merge,tts,search,metadata}` | запуск задачи |
| `POST` | `/preview/process`, `/metadata/preview` | предпросмотр без сохранения |
| `GET` | `/jobs/{id}` | статус, прогресс, логи, файлы |
| `POST` | `/jobs/{id}/cancel` | прерывание |
| `GET` | `/jobs/{id}/files/{path}` | скачивание файла |
| `GET` | `/jobs/{id}/archive` | ZIP со всеми результатами |

**Модель задач.** Любая длинная операция — это job: `POST` создаёт задачу и
сразу возвращает `{"id": "..."}`. Дальше фронтенд опрашивает `GET /api/jobs/{id}`
раз в 0.5–1 с и получает `status`, `progress.percent`, `logs` и список `files`.
Файлы загружаются как `multipart/form-data`: параметры — в поле `params`
(JSON-строка), файлы — в `files`, `table`, `ref_audio`, `ref_files`.
Результаты лежат в `workspace/jobs/<id>/` и удаляются через `VUI_JOB_TTL_HOURS`.

## Структура репозитория

```
VUI_ToolKit/
├── README.md
├── .gitignore
├── Запустить VUI ToolKit.bat        # 1 — веб, 2 — десктоп
│
├── VUI ToolKit Web/
│   ├── main.py                      # бэкенд + фронтенд + браузер
│   ├── requirements.txt             # движок + ML-зависимости
│   ├── core/                        # движок (копия для веб-версии)
│   ├── gui/                         # старый tkinter-GUI (fallback --desktop)
│   └── Сайт/
│       ├── snail-voice-forge/       # React 19 + TanStack Start + Tailwind
│       └── vui-toolkit-backend/     # FastAPI: api/, core/, run.py
│
└── VUI ToolKit GUI/
    ├── main.py                      # запуск Flet-приложения
    ├── requirements.txt             # Flet + движок + ML-зависимости
    ├── core/                        # тот же движок
    ├── vui/                         # интерфейс на Flet (страницы, тема, runner)
    ├── _backup_tkinter_gui/         # прежний tkinter-интерфейс
    └── workspace/                   # результаты задач (не в git)
```

`VUI ToolKit Web/core/` и `VUI ToolKit GUI/core/`, а также
`Сайт/vui-toolkit-backend/core/` — копии одного и того же движка. При правках
логики синхронизируйте их.

## Движок

| Модуль | Ответственность |
|---|---|
| `audio_io.py` | чтение/запись аудио, форматы, PCM, уникальные имена |
| `effects.py` | 14 эффектов, встроенные пресеты, применение пайплайна |
| `vad_silero.py` | VAD Silero: речь/паузы, нарезка, таблица |
| `diarization.py` | диаризация pyannote |
| `merge_audio.py` | склейка с паузами и ресемплингом |
| `word_search.py` | Whisper, поиск слов/фраз, запись `.seg` |
| `metadata_gen.py` | генерация метаданных и нарезка по `.seg` |
| `tts_elevenlabs.py` | синтез через ElevenLabs |
| `tts_omnivoice.py` | локальный синтез OmniVoice |
| `playback.py` | предпрослушивание (simpleaudio или плеер ОС) |
| `presets.py` | пользовательские пресеты |
| `settings.py` | настройки приложения |

## Форматы аудио

На вход: **WAV, MP3, OGG, FLAC, M4A, AAC, WMA, OPUS, AIFF, WEBM, AMR**.
Форматы, которые `soundfile` не читает напрямую, конвертируются в WAV через
`ffmpeg`.

На выход: **WAV / FLAC / OGG / MP3** с разрядностью PCM_16, PCM_24, PCM_32
или FLOAT (где поддерживается форматом). Запись MP3 также идёт через `ffmpeg`,
если `libsndfile` этого не умеет.

Установка ffmpeg:

```bash
winget install ffmpeg        # Windows, затем перезапустить терминал
brew install ffmpeg          # macOS
sudo apt install ffmpeg      # Debian/Ubuntu
```

Наличие ffmpeg проверяется через `GET /api/capabilities`.

## Особенности разметки `.seg`

- Файл сохраняется рядом с исходной записью в **UTF-8 с BOM** — так кириллица
  корректно читается в Wave Assistant.
- На каждый найденный фрагмент пишутся **две метки**: начало (со словом) и
  конец (пустая).
- Первое число метки — **номер байта** в аудиопотоке, а не отсчёта:
  `byte = время × частота × байт/отсчёт × каналы`.

## Частые проблемы

| Симптом | Решение |
|---|---|
| «Node.js или папка `Сайт/snail-voice-forge` не найдены» | Установить Node.js 20.19+ и выполнить `npm install`; либо запустить `python main.py --desktop` |
| «Не найден Python с fastapi/uvicorn» | `pip install -r "Сайт/vui-toolkit-backend/requirements.txt"` или задать `VUI_PYTHON` |
| Порт 5173/8000 занят | `python main.py --port 7100`, для API — `VUI_PORT` |
| `ffmpeg not found` при чтении m4a/mp3 | Установить ffmpeg и перезапустить терминал |
| Ошибка 401 при диаризации | HF-токен должен иметь доступ к `pyannote/speaker-diarization-community-1` (принять лицензию на Hugging Face) |
| Первый запуск функции долгий | Скачиваются модели Silero/Whisper/pyannote/OmniVoice |
| Кириллица в `.seg` «кракозябрами» | Использовать файл как есть (UTF-8 BOM) или открывать в редакторе с UTF-8 |

## Лицензия

Файл лицензии в репозитории отсутствует. Проект личный; перед публичным
использованием кода уточните условия у автора.
