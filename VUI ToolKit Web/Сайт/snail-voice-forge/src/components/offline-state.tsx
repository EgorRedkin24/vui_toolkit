import { Link } from "@tanstack/react-router";
import { ServerOff, Settings } from "lucide-react";
import { Button } from "@/components/ui/button";

export function OfflineState() {
  return <div className="surface-panel mx-auto flex max-w-2xl flex-col items-center rounded-lg px-6 py-14 text-center">
    <div className="mb-5 rounded-lg bg-destructive/10 p-4 text-destructive"><ServerOff className="h-8 w-8" /></div>
    <h1 className="text-2xl font-semibold">Сервер недоступен</h1>
    <p className="mt-3 max-w-lg text-sm leading-6 text-muted-foreground">Запустите бэкенд: <code className="rounded bg-muted px-1.5 py-0.5 font-mono text-foreground">python run.py</code> (порт 8000) и проверьте URL API в настройках.</p>
    <Button asChild variant="outline" className="mt-6"><Link to="/settings"><Settings />Открыть настройки</Link></Button>
  </div>;
}