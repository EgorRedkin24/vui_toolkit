export type JobStatus = "queued" | "running" | "done" | "error" | "canceled";

export type JobFile = { name: string; size: number; url: string };
export type JobLog = { t: number; msg: string };
export type Job = {
  id: string;
  tool: string;
  status: JobStatus;
  progress: { current: number; total: number; percent: number };
  logs: JobLog[];
  files: JobFile[];
  error: string | null;
  created_at: number;
};

export type Capabilities = {
  rubberband: boolean;
  parselmouth: boolean;
  torch: boolean;
  whisper: boolean;
  pyannote: boolean;
  omnivoice: boolean;
};

export type SaveFormat = { ext: string; subtypes: string[] };
export type ApiOptions = {
  save_formats: Record<string, SaveFormat>;
  whisper_models: string[];
  tts_models: string[];
  vad_modes: string[];
  table_formats: string[];
};

export type EffectParam = { type: "float" | "int"; default: number; label: string };
export type Effect = { id: string; title: string; params: Record<string, EffectParam>; note: string | null };
export type PipelineStep = { effect: string; params: Record<string, number> };
export type Preset = { name: string; steps: PipelineStep[] };
export type Presets = { builtin: Preset[]; user: Preset[] };
export type ServerSettings = Record<string, unknown>;

export type HistoryJob = {
  id: string;
  tool: string;
  createdAt: number;
  status: JobStatus | "missing";
};