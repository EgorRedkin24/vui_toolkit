import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Choice, Field } from "@/components/form-controls";
import { useAppData } from "@/lib/app-context";

export function FormatFields({ format, subtype, onFormat, onSubtype }: { format: string; subtype: string; onFormat: (v: string) => void; onSubtype: (v: string) => void }) {
  const { options } = useAppData(); const formats = Object.keys(options?.save_formats || { WAV: { ext: ".wav", subtypes: ["PCM_16"] } });
  const subtypes = options?.save_formats?.[format]?.subtypes || [];
  return <><Choice label="Формат" value={format} onChange={(value) => { onFormat(value); onSubtype(options?.save_formats?.[value]?.subtypes?.[0] || ""); }} options={formats.map((value) => ({ value, label: value }))} />{format !== "MP3" && subtypes.length > 0 && <Choice label="Разрядность" value={subtype || subtypes[0] || ""} onChange={onSubtype} options={subtypes.map((value) => ({ value, label: value }))} />}</>;
}

export function CheckField({ label, checked, onChange, children }: { label: string; checked: boolean; onChange: (v: boolean) => void; children?: React.ReactNode }) {
  return <div className="flex min-h-10 items-center gap-3"><Checkbox checked={checked} onCheckedChange={(v) => onChange(v === true)} /><span className="text-sm">{label}</span>{children}</div>;
}

export function Segmented({ value, onChange, options }: { value: string; onChange: (v: string) => void; options: { value: string; label: string }[] }) {
  return <div className="grid grid-cols-2 gap-1 rounded-md bg-muted p-1">{options.map((o) => <Button key={o.value} type="button" variant={value === o.value ? "default" : "ghost"} onClick={() => onChange(o.value)}>{o.label}</Button>)}</div>;
}

export function TokenInput({ label, value, onChange, onSave }: { label: string; value: string; onChange: (v: string) => void; onSave: () => void }) {
  const [visible, setVisible] = useState(false);
  return <Field label={label}><div className="flex gap-2"><Input type={visible ? "text" : "password"} value={value} onChange={(e) => onChange(e.target.value)} className="font-mono" /><Button type="button" variant="outline" onClick={() => setVisible(!visible)}>{visible ? "Скрыть" : "Показать"}</Button><Button type="button" onClick={onSave}>Сохранить</Button></div></Field>;
}