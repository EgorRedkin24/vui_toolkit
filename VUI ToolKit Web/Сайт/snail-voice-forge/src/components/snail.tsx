import { cn } from "@/lib/utils";
import type { JobStatus } from "@/lib/vui-types";

export function Snail({ className, celebrating = false }: { className?: string; celebrating?: boolean }) {
  return (
    <svg viewBox="0 0 64 38" aria-hidden="true" className={cn("overflow-visible", className, celebrating && "animate-[snail-celebrate_.7s_ease-in-out]")}>
      <g className="origin-bottom animate-[snail-crawl_1.2s_ease-in-out_infinite]">
        <path d="M5 30c5-8 15-7 22-4 6 3 12 4 23 4 6 0 9 2 9 5H8c-4 0-5-3-3-5Z" fill="var(--success)" />
        <circle cx="29" cy="19" r="13" fill="var(--primary)" />
        <path d="M29 10c7 0 11 8 6 13-4 4-11 1-10-4 1-4 7-4 8 0" fill="none" stroke="var(--primary-foreground)" strokeWidth="2.5" strokeLinecap="round" opacity=".75" />
        <g style={{ transformOrigin: "48px 26px" }} className="animate-[antenna-left_1.6s_ease-in-out_infinite]">
          <path d="M48 27 46 16" stroke="var(--success)" strokeWidth="2" strokeLinecap="round" /><circle cx="46" cy="14" r="2" fill="var(--success)" />
        </g>
        <g style={{ transformOrigin: "54px 27px" }} className="animate-[antenna-right_1.45s_ease-in-out_infinite]">
          <path d="m53 27 5-9" stroke="var(--success)" strokeWidth="2" strokeLinecap="round" /><circle cx="59" cy="16" r="2" fill="var(--success)" />
        </g>
        <circle cx="52" cy="25" r="1.2" fill="var(--success-foreground)" />
      </g>
    </svg>
  );
}

export function SnailProgress({ percent, status, label }: { percent: number; status: JobStatus; label?: string | undefined }) {
  const value = Math.max(0, Math.min(100, percent || 0));
  const terminal = status === "done";
  const failed = status === "error";
  const canceled = status === "canceled";
  return (
    <div className="space-y-4" aria-label={`Прогресс ${Math.round(value)} процентов`}>
      <div className="flex items-end justify-between gap-4">
        <div>
          <p className="text-sm font-medium text-foreground">{terminal ? "Готово!" : label || (status === "queued" ? "Задача в очереди" : "Выполняется")}</p>
          <p className="mt-1 font-mono text-xs text-muted-foreground">{status}</p>
        </div>
        <span className="font-mono text-sm font-semibold text-foreground">{Math.round(value)}%</span>
      </div>
      <div className="relative h-10 pt-5">
        <div className="h-1 overflow-hidden rounded-full bg-border">
          <div className={cn("relative h-full rounded-full transition-[width] duration-500 ease-out", failed ? "bg-destructive" : canceled ? "bg-muted-foreground" : "bg-[linear-gradient(90deg,var(--primary),var(--success))]")} style={{ width: `${value}%` }}>
            <span className="absolute inset-0 animate-[slime-shimmer_2.2s_ease-in-out_infinite] bg-[linear-gradient(90deg,transparent,var(--success))]" />
          </div>
        </div>
        <div className="absolute top-0 w-12 -translate-x-1/2 transition-[left] duration-500 ease-out" style={{ left: `clamp(24px, ${value}%, calc(100% - 24px))` }}>
          <Snail className="h-8 w-12" celebrating={terminal} />
        </div>
      </div>
    </div>
  );
}