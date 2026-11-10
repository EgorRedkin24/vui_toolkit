import type { ReactNode } from "react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";

export function Field({ label, hint, children }: { label: string; hint?: string | undefined; children: ReactNode }) {
  return <div className="space-y-2"><Label>{label}</Label>{children}{hint && <p className="text-xs leading-5 text-muted-foreground">{hint}</p>}</div>;
}

export function NumberField({ label, value, onChange, min, max, step = 1, hint }: { label: string; value: number; onChange: (n: number) => void; min?: number; max?: number; step?: number; hint?: string }) {
  return <Field label={label} hint={hint}><Input type="number" value={value} min={min} max={max} step={step} onChange={(e) => onChange(Number(e.target.value))} className="font-mono" /></Field>;
}

export function Choice({ label, value, onChange, options, disabled }: { label: string; value: string; onChange: (v: string) => void; options: { value: string; label: string }[]; disabled?: boolean | undefined }) {
  return <Field label={label}><Select value={value} onValueChange={onChange} {...(disabled === undefined ? {} : { disabled })}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent>{options.map((option) => <SelectItem key={option.value} value={option.value}>{option.label}</SelectItem>)}</SelectContent></Select></Field>;
}

export function ToggleRow({ label, hint, checked, onChange, disabled }: { label: string; hint?: string; checked: boolean; onChange: (v: boolean) => void; disabled?: boolean }) {
  return <div className="flex items-start justify-between gap-4 rounded-md border border-border bg-muted/30 p-3"><div><p className="text-sm font-medium">{label}</p>{hint && <p className="mt-1 text-xs text-muted-foreground">{hint}</p>}</div><Switch checked={checked} onCheckedChange={onChange} disabled={disabled} /></div>;
}

export function Notice({ tone = "info", children }: { tone?: "info" | "warning" | "error"; children: ReactNode }) {
  const style = tone === "error" ? "border-destructive/40 bg-destructive/10 text-destructive" : tone === "warning" ? "border-warning/40 bg-warning/10 text-foreground" : "border-primary/30 bg-primary/10 text-foreground";
  return <div className={`rounded-md border px-4 py-3 text-sm leading-6 ${style}`}>{children}</div>;
}