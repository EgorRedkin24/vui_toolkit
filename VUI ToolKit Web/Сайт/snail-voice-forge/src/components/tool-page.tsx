import { Link } from "@tanstack/react-router";
import { ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
import { JobPanel } from "@/components/job-panel";
import { OfflineState } from "@/components/offline-state";
import { ProcessForm } from "@/components/tool-forms/process-form";
import { DiarizeForm, MergeForm, SearchForm, TtsForm, VadForm } from "@/components/tool-forms/simple-forms";
import { MetadataForm } from "@/components/tool-forms/metadata-form";
import { useJob } from "@/hooks/use-job";
import { useAppData } from "@/lib/app-context";
import { getTool, type ToolId } from "@/lib/tools";

const forms = { process: ProcessForm, vad: VadForm, diarize: DiarizeForm, merge: MergeForm, tts: TtsForm, search: SearchForm, metadata: MetadataForm };

export function ToolPage({ toolId }: { toolId: ToolId }) {
  const { online, checking } = useAppData(); const tool = getTool(toolId); const runner = useJob(toolId); const Form = forms[toolId];
  if (!tool) return null;
  return <div><Button asChild variant="ghost" className="mb-4 -ml-3"><Link to="/"><ArrowLeft />Все инструменты</Link></Button><div className="mb-8 flex items-start gap-4"><div className="rounded-lg bg-primary/10 p-3 text-primary"><tool.icon className="h-6 w-6" /></div><div><h1 className="text-2xl font-semibold sm:text-3xl">{tool.title}</h1><p className="mt-2 text-sm text-muted-foreground">{tool.description}</p></div></div>{!checking && !online && <div className="mb-6"><OfflineState /></div>}<div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_420px]"><section className="surface-panel rounded-lg p-5 sm:p-6"><Form onSubmit={(params, fields) => void runner.start(params, fields)} disabled={runner.active || !online} /></section><aside className="xl:sticky xl:top-24 xl:self-start">{runner.job || runner.submitting ? <JobPanel job={runner.job} submitting={runner.submitting} onCancel={() => void runner.cancel()} /> : <div className="surface-panel rounded-lg p-6"><p className="text-sm font-medium">Задача ещё не запущена</p><p className="mt-2 text-sm leading-6 text-muted-foreground">Настройте параметры слева. Прогресс, логи и результаты появятся здесь.</p></div>}</aside></div></div>;
}