import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { apiFetch, cancelJob, createMultipart, getJob, HISTORY_KEY } from "@/lib/vui-api";
import type { HistoryJob, Job } from "@/lib/vui-types";

function writeHistory(job: HistoryJob) {
  const current = JSON.parse(window.localStorage.getItem(HISTORY_KEY) || "[]") as HistoryJob[];
  const next = [job, ...current.filter((item) => item.id !== job.id)].slice(0, 100);
  window.localStorage.setItem(HISTORY_KEY, JSON.stringify(next));
}

export function useJob(tool: string) {
  const [job, setJob] = useState<Job | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const timer = useRef<number | null>(null);
  const stop = () => { if (timer.current) window.clearInterval(timer.current); timer.current = null; };
  useEffect(() => stop, []);
  const poll = (id: string) => {
    stop();
    const tick = async () => {
      try {
        const next = await getJob(id); setJob(next);
        writeHistory({ id, tool: next.tool || tool, createdAt: next.created_at * 1000 || Date.now(), status: next.status });
        if (["done", "error", "canceled"].includes(next.status)) stop();
      } catch (error) { stop(); toast.error(error instanceof Error ? error.message : "Не удалось получить статус задачи"); }
    };
    void tick(); timer.current = window.setInterval(tick, 850);
  };
  const start = async (params: unknown, fields: Record<string, File | File[] | undefined>) => {
    setSubmitting(true);
    try {
      const result = await apiFetch<{ id: string }>(`/api/jobs/${tool}`, { method: "POST", body: createMultipart(params, fields) });
      writeHistory({ id: result.id, tool, createdAt: Date.now(), status: "queued" }); poll(result.id);
    } catch (error) { toast.error(error instanceof Error ? error.message : "Не удалось запустить задачу"); }
    finally { setSubmitting(false); }
  };
  const cancel = async () => { if (!job) return; try { await cancelJob(job.id); } catch (error) { toast.error(error instanceof Error ? error.message : "Не удалось прервать задачу"); } };
  return { job, setJob, submitting, active: submitting || job?.status === "queued" || job?.status === "running", start, cancel, poll };
}