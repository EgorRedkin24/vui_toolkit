import { ChevronDown, ChevronUp, FileAudio, FileSpreadsheet, Play, UploadCloud, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export function formatBytes(bytes: number) {
  if (!bytes) return "0 Б";
  const units = ["Б", "КБ", "МБ", "ГБ"];
  const i = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  return `${(bytes / 1024 ** i).toFixed(i ? 1 : 0)} ${units[i]}`;
}

export function FileDrop({ files, onChange, accept, multiple = true, label = "Перетащите файлы сюда или нажмите для выбора", compact = false }: { files: File[]; onChange: (files: File[]) => void; accept: string; multiple?: boolean; label?: string; compact?: boolean }) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [drag, setDrag] = useState(false);
  const [playing, setPlaying] = useState<number | null>(null);
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [expanded, setExpanded] = useState(true);
  useEffect(() => () => { if (audioUrl) URL.revokeObjectURL(audioUrl); }, [audioUrl]);
  const add = (incoming: File[]) => onChange(multiple ? [...files, ...incoming.filter((f) => !files.some((x) => x.name === f.name && x.size === f.size))] : incoming.slice(0, 1));
  const preview = (file: File, index: number) => { if (audioUrl) URL.revokeObjectURL(audioUrl); setAudioUrl(URL.createObjectURL(file)); setPlaying(index); };
  return <div className="space-y-3">
    <Button variant="ghost" type="button" onClick={() => inputRef.current?.click()} onDragOver={(e) => { e.preventDefault(); setDrag(true); }} onDragLeave={() => setDrag(false)} onDrop={(e) => { e.preventDefault(); setDrag(false); add(Array.from(e.dataTransfer.files)); }} className={cn("flex h-auto w-full flex-col items-center justify-center whitespace-normal rounded-lg border border-dashed border-border bg-muted/20 px-5 text-center text-foreground transition-colors hover:border-primary/60 hover:bg-primary/5", compact ? "min-h-28 py-5" : "min-h-40 py-8", drag && "border-primary bg-primary/10")}>
      <UploadCloud className="mb-3 h-7 w-7 text-primary" /><span className="text-sm font-medium">{label}</span><span className="mt-1 font-mono text-xs text-muted-foreground">{accept.replaceAll(",", " · ")}</span>
    </Button>
    <input ref={inputRef} hidden type="file" accept={accept} multiple={multiple} onChange={(e) => { add(Array.from(e.target.files || [])); e.target.value = ""; }} />
    {files.length > 0 && <div><Button type="button" variant="ghost" size="sm" aria-expanded={expanded} onClick={() => setExpanded(!expanded)} className="w-full justify-between px-2 text-muted-foreground"><span>Прикреплено: {files.length}</span>{expanded ? <ChevronUp /> : <ChevronDown />}</Button></div>}
    {files.length > 0 && expanded && <div className="space-y-2">{files.map((file, index) => { const audio = /\.(wav|mp3|ogg|flac|m4a)$/i.test(file.name); return <div key={`${file.name}-${file.size}`} className="flex items-center gap-3 rounded-md border border-border bg-card px-3 py-2">
      {audio ? <FileAudio className="h-4 w-4 text-primary" /> : <FileSpreadsheet className="h-4 w-4 text-primary" />}<div className="min-w-0 flex-1"><p className="truncate font-mono text-xs">{file.name}</p><p className="mt-0.5 text-[11px] text-muted-foreground">{formatBytes(file.size)}</p></div>
      {audio && <Button type="button" variant="ghost" size="icon" onClick={() => preview(file, index)} aria-label={`Прослушать ${file.name}`}><Play /></Button>}
       <Button type="button" variant="ghost" size="icon" onClick={() => { onChange(files.filter((_, i) => i !== index)); if (playing === index) { setPlaying(null); setAudioUrl(null); } else if (playing !== null && playing > index) setPlaying(playing - 1); }} aria-label={`Удалить ${file.name}`}><X /></Button>
    </div>; })}</div>}
     {expanded && playing !== null && audioUrl && <div className="rounded-md bg-muted p-3"><p className="mb-2 truncate font-mono text-xs text-muted-foreground">{files[playing]?.name}</p><audio controls src={audioUrl} className="h-9 w-full" /></div>}
  </div>;
}