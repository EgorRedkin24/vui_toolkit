import { Link, useLocation } from "@tanstack/react-router";
import { History, Home, Menu, Moon, Settings, Sun, X } from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { Snail } from "@/components/snail";
import { useAppData } from "@/lib/app-context";
import { THEME_KEY } from "@/lib/vui-api";
import { cn } from "@/lib/utils";

const nav = [
  { to: "/", label: "Инструменты", icon: Home },
  { to: "/jobs", label: "История", icon: History },
  { to: "/settings", label: "Настройки", icon: Settings },
] as const;

export function AppShell({ children }: { children: ReactNode }) {
  const { online, checking } = useAppData();
  const [menu, setMenu] = useState(false);
  const [dark, setDark] = useState(true);
  const location = useLocation();

  useEffect(() => {
    const stored = window.localStorage.getItem(THEME_KEY);
    const nextDark = stored ? stored === "dark" : true;
    setDark(nextDark); document.documentElement.classList.toggle("dark", nextDark);
  }, []);
  const toggleTheme = () => {
    const next = !dark; setDark(next); document.documentElement.classList.toggle("dark", next);
    window.localStorage.setItem(THEME_KEY, next ? "dark" : "light");
  };

  return (
    <div className="app-canvas min-h-screen text-foreground">
      <header className="sticky top-0 z-40 border-b border-border bg-background/90 backdrop-blur-xl">
        <div className="mx-auto flex h-16 max-w-[1440px] items-center gap-3 px-4 sm:px-6 lg:px-8">
          <Link to="/" className="flex items-center gap-2.5" aria-label="VUI ToolKit — главная">
            <Snail className="h-7 w-10" />
            <span className="font-semibold">VUI <span className="text-primary">ToolKit</span></span>
          </Link>
          <nav className="ml-8 hidden items-center gap-1 md:flex">
            {nav.map(({ to, label, icon: Icon }) => <Link key={to} to={to} className={cn("flex items-center gap-2 rounded-md px-3 py-2 text-sm text-muted-foreground transition-colors hover:bg-accent hover:text-foreground", location.pathname === to && "bg-accent text-foreground")}><Icon className="h-4 w-4" />{label}</Link>)}
          </nav>
          <div className="ml-auto flex items-center gap-2">
            <div className="hidden items-center gap-2 rounded-full border border-border bg-card px-3 py-1.5 text-xs sm:flex">
              <span className={cn("h-2 w-2 rounded-full", checking ? "animate-pulse bg-warning" : online ? "bg-success" : "bg-destructive")} />
              {checking ? "Проверка API" : online ? "API онлайн" : "API недоступен"}
            </div>
            <Button variant="ghost" size="icon" onClick={toggleTheme} aria-label={dark ? "Включить светлую тему" : "Включить тёмную тему"}>{dark ? <Sun /> : <Moon />}</Button>
            <Button variant="ghost" size="icon" className="md:hidden" onClick={() => setMenu(!menu)} aria-label="Открыть меню">{menu ? <X /> : <Menu />}</Button>
          </div>
        </div>
        {menu && <nav className="border-t border-border p-3 md:hidden">{nav.map(({ to, label, icon: Icon }) => <Link key={to} to={to} onClick={() => setMenu(false)} className="flex items-center gap-3 rounded-md px-3 py-3 text-sm text-muted-foreground hover:bg-accent hover:text-foreground"><Icon className="h-4 w-4" />{label}</Link>)}</nav>}
      </header>
      <main className="relative mx-auto min-h-[calc(100vh-128px)] max-w-[1440px] px-4 py-8 sm:px-6 lg:px-8">{children}</main>
      <footer className="border-t border-border px-4 py-6 text-center text-xs text-muted-foreground">VUI ToolKit · локальные аудиоинструменты</footer>
    </div>
  );
}