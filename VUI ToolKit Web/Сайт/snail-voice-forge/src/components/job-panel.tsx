import { Archive, Download, Eye, LoaderCircle, OctagonX } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { apiBlob, getApiUrl } from "@/lib/vui-api";
import type { Job } from "@/lib/vui-types";
import { formatBytes } from "./file-drop";
import { SnailProgress } from "./snail";

export function JobPanel({ job, submitting, onCancel }: { job: Job | null; submitting: boolean; onCancel: () => void }) {
  const logs = useRef<HTMLDivElement>(null);
  const [viewer, setViewer] = useState<{ name: string; text: string } | null>(null);
  useEffect(() => { logs.current?.scrollTo({ top: logs.current.scrollHeight, behavior: "smooth" }); }, [job?.logs]);
  if (!job && !submitting) return null;
  if (submitting && !job) return <section className="surface-panel mt-6 rounded-lg p-6"><div className="flex items-center gap-3 text-sm"><LoaderCircle className="h-5 w-5 animate-spin text-primary" />Отправляем файлы на сервер…</div></section>;
  if (!job) return null;
  const active = job.status === "queued" || job.status === "running";
  const viewText = async (name: string, url: string) => { try { const text = await (await apiBlob(url)).text(); setViewer({ name, text }); } catch (error) { toast.error(error instanceof Error ? error.message : "Не удалось открыть файл"); } };
  return <section className="surface-panel mt-6 space-y-6 rounded-lg p-5 sm:p-6">
    <SnailProgress percent={job.progress?.percent || 0} status={job.status} label={job.logs?.at(-1)?.msg} />
    {active && <Button variant="destructive" onClick={onCancel}><OctagonX />Прервать</Button>}
    {job.logs?.length > 0 && <div><h3 className="mb-2 text-sm font-medium">Живой лог</h3><div ref={logs} className="max-h-52 overflow-y-auto rounded-md border border-border bg-background p-4 font-mono text-xs leading-6 text-muted-foreground">{job.logs.map((line, index) => <div key={`${line.t}-${index}`}><span className="mr-3 text-primary">{new Date(line.t * 1000).toLocaleTimeString("ru-RU")}</span>{line.msg}</div>)}</div></div>}
    {job.status === "error" && <div className="rounded-md border border-destructive/40 bg-destructive/10 p-4 text-sm text-destructive"><strong>Ошибка:</strong> {job.error || "Задача завершилась с ошибкой"}</div>}
    {job.status === "done" && <div><div className="mb-3 flex flex-wrap items-center justify-between gap-3"><h3 className="text-lg font-semibold">Результаты</h3><Button asChild variant="outline"><a href={`${getApiUrl()}/api/jobs/${job.id}/archive`} download><Archive />Скачать всё (ZIP)</a></Button></div><div className="space-y-3">{job.files?.map((file) => { const audio = /\.(wav|mp3|ogg|flac|m4a)$/i.test(file.name); const text = /\.(txt|seg|json|yaml|yml)$/i.test(file.name); return <div key={file.url} className="rounded-md border border-border bg-muted/20 p-3"><div className="flex flex-wrap items-center gap-3"><div className="min-w-0 flex-1"><p className="truncate font-mono text-xs">{file.name}</p><p className="mt-1 text-xs text-muted-foreground">{formatBytes(file.size)}</p></div>{text && <Button variant="ghost" size="sm" onClick={() => void viewText(file.name, file.url)}><Eye />Просмотр</Button>}<Button asChild variant="ghost" size="sm"><a href={`${getApiUrl()}${file.url}`} download><Download />Скачать</a></Button></div>{audio && <audio controls src={`${getApiUrl()}${file.url}`} className="mt-3 h-9 w-full" />}</div>; })}</div></div>}
    <Dialog open={!!viewer} onOpenChange={(open) => !open && setViewer(null)}><DialogContent className="max-h-[80vh] max-w-3xl overflow-hidden"><DialogHeader><DialogTitle className="font-mono text-sm">{viewer?.name}</DialogTitle></DialogHeader><pre className="max-h-[62vh] overflow-auto rounded-md bg-muted p-4 font-mono text-xs leading-6">{viewer?.text}</pre></DialogContent></Dialog>
  </section>;
}