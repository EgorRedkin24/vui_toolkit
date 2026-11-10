import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { getCapabilities, getEffects, getHealth, getOptions, getPresets, getSettings } from "./vui-api";
import type { ApiOptions, Capabilities, Effect, Presets, ServerSettings } from "./vui-types";

type AppData = {
  online: boolean;
  checking: boolean;
  capabilities: Capabilities | null;
  options: ApiOptions | null;
  effects: Effect[];
  presets: Presets;
  effectsError: boolean;
  presetsError: boolean;
  serverSettings: ServerSettings;
  refresh: () => Promise<void>;
};

const AppContext = createContext<AppData | null>(null);

export function AppProvider({ children }: { children: ReactNode }) {
  const [online, setOnline] = useState(false);
  const [checking, setChecking] = useState(true);
  const [capabilities, setCapabilities] = useState<Capabilities | null>(null);
  const [options, setOptions] = useState<ApiOptions | null>(null);
  const [effects, setEffects] = useState<Effect[]>([]);
  const [presets, setPresets] = useState<Presets>({ builtin: [], user: [] });
  const [effectsError, setEffectsError] = useState(false);
  const [presetsError, setPresetsError] = useState(false);
  const [serverSettings, setServerSettings] = useState<ServerSettings>({});

  const refresh = useCallback(async () => {
    setChecking(true);
    try {
      await getHealth();
      setOnline(true);
      const [caps, opts, effectData, presetData, settingsData] = await Promise.allSettled([
        getCapabilities(), getOptions(), getEffects(), getPresets(), getSettings(),
      ]);
      setCapabilities(caps.status === "fulfilled" ? caps.value : null);
      setOptions(opts.status === "fulfilled" ? opts.value : null);
      setEffects(effectData.status === "fulfilled" ? effectData.value.effects : []);
      setPresets(presetData.status === "fulfilled" ? presetData.value : { builtin: [], user: [] });
      setServerSettings(settingsData.status === "fulfilled" ? settingsData.value : {});
      setEffectsError(effectData.status === "rejected");
      setPresetsError(presetData.status === "rejected");
    } catch {
      setOnline(false);
      setEffects([]); setPresets({ builtin: [], user: [] });
      setEffectsError(false); setPresetsError(false);
    } finally {
      setChecking(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
    const timer = window.setInterval(async () => {
      try { await getHealth(); setOnline(true); } catch { setOnline(false); }
    }, 15_000);
    return () => window.clearInterval(timer);
  }, [refresh]);

  const value = useMemo(() => ({ online, checking, capabilities, options, effects, presets, effectsError, presetsError, serverSettings, refresh }), [online, checking, capabilities, options, effects, presets, effectsError, presetsError, serverSettings, refresh]);
  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

export function useAppData() {
  const value = useContext(AppContext);
  if (!value) throw new Error("useAppData must be used inside AppProvider");
  return value;
}