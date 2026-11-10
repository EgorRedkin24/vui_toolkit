import { AudioLines, FileJson, ListMusic, Mic2, Search, SlidersHorizontal, Users } from "lucide-react";

export const tools = [
  { id: "process", title: "Обработка аудио", description: "Эффекты, пресеты и конвейеры обработки", icon: SlidersHorizontal },
  { id: "vad", title: "VAD", description: "Поиск фрагментов речи и пауз", icon: AudioLines, capability: "torch" },
  { id: "diarize", title: "Диаризация", description: "Разделение записи по говорящим", icon: Users, capability: "pyannote" },
  { id: "merge", title: "Склейка аудио", description: "Сборка файлов в заданном порядке", icon: ListMusic },
  { id: "tts", title: "Синтез речи", description: "ElevenLabs и локальное клонирование", icon: Mic2 },
  { id: "search", title: "Поиск и разметка", description: "Распознавание фраз и экспорт .seg", icon: Search, capability: "whisper" },
  { id: "metadata", title: "Метаданные", description: "Генерация структурированных метаданных", icon: FileJson },
] as const;

export type ToolId = (typeof tools)[number]["id"];
export const getTool = (id: string) => tools.find((tool) => tool.id === id);