import { createContext, useCallback, useContext, useEffect, useState } from "react";

type Mode = "light" | "dark" | "system";
export type Palette =
  | "neutral" | "emerald" | "navy" | "amber"
  | "violet" | "rose" | "teal" | "mono";

export const PALETTES: { id: Palette; label: string; swatch: string }[] = [
  { id: "neutral", label: "خنثی حرفه‌ای", swatch: "#33547a" },
  { id: "emerald", label: "زمردی", swatch: "#046c4e" },
  { id: "navy", label: "آبی نفتی", swatch: "#1e3a6e" },
  { id: "amber", label: "کهربایی", swatch: "#a16207" },
  { id: "violet", label: "بنفش", swatch: "#4f46e5" },
  { id: "rose", label: "گلبهی", swatch: "#b01b59" },
  { id: "teal", label: "فیروزه‌ای", swatch: "#0d6e76" },
  { id: "mono", label: "تک‌رنگ", swatch: "#262626" },
];

const PALETTE_IDS = new Set(PALETTES.map((p) => p.id));

const KEY = "pa-theme";
const PALETTE_KEY = "pa-palette";
const ThemeContext = createContext<{
  mode: Mode;
  isDark: boolean;
  setMode: (m: Mode) => void;
  palette: Palette;
  setPalette: (p: Palette) => void;
}>({
  mode: "system",
  isDark: false,
  setMode: () => {},
  palette: "neutral",
  setPalette: () => {},
});

function systemPrefersDark() {
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches ?? false;
}

function readStored(): Mode {
  const raw = localStorage.getItem(KEY);
  return raw === "light" || raw === "dark" ? raw : "system";
}

function readPalette(): Palette {
  const raw = localStorage.getItem(PALETTE_KEY);
  return raw && PALETTE_IDS.has(raw as Palette) ? (raw as Palette) : "neutral";
}

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [mode, setModeState] = useState<Mode>(readStored);
  const [isDark, setIsDark] = useState(
    () => readStored() === "dark" || (readStored() === "system" && systemPrefersDark()),
  );

  useEffect(() => {
    const resolve = () => mode === "dark" || (mode === "system" && systemPrefersDark());
    const apply = () => {
      const dark = resolve();
      setIsDark(dark);
      document.documentElement.classList.toggle("dark", dark);
    };
    apply();

    // اگر روی «سیستم» است، تغییر تم سیستم‌عامل باید بلافاصله دیده شود
    if (mode !== "system") return;
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    mq.addEventListener("change", apply);
    return () => mq.removeEventListener("change", apply);
  }, [mode]);

  const [palette, setPaletteState] = useState<Palette>(readPalette);

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", palette);
  }, [palette]);

  const setPalette = useCallback((p: Palette) => {
    setPaletteState(p);
    localStorage.setItem(PALETTE_KEY, p);
  }, []);

  const setMode = useCallback((m: Mode) => {
    setModeState(m);
    if (m === "system") localStorage.removeItem(KEY);
    else localStorage.setItem(KEY, m);
  }, []);

  return (
    <ThemeContext.Provider value={{ mode, isDark, setMode, palette, setPalette }}>
      {children}
    </ThemeContext.Provider>
  );
}

export const useTheme = () => useContext(ThemeContext);

/** آیا کاربر حرکت کمتر خواسته؟ انیمیشن‌ها باید احترام بگذارند. */
export function useReducedMotion(): boolean {
  const [reduced, setReduced] = useState(
    () => window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false,
  );
  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    const onChange = () => setReduced(mq.matches);
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);
  return reduced;
}

/**
 * رنگ نمودارها.
 *
 * Recharts رشتهٔ رنگ می‌خواهد و کلاس CSS نمی‌فهمد، پس مقدار واقعی توکن‌ها
 * از خودِ صفحه خوانده می‌شود. این‌طور با عوض‌شدن تم، نمودارها هم عوض
 * می‌شوند بدون آنکه هگز ثابتی در کد بماند.
 */
export function useChartColors() {
  const { isDark, palette } = useTheme();
  const [colors, setColors] = useState(() => readChartColors());
  useEffect(() => {
    // یک فریم صبر تا مرورگر توکن‌های تم تازه را اعمال کند
    const id = requestAnimationFrame(() => setColors(readChartColors()));
    return () => cancelAnimationFrame(id);
  }, [isDark, palette]);
  return colors;
}

function token(style: CSSStyleDeclaration, name: string, fallback: string): string {
  const raw = style.getPropertyValue(name).trim();
  return raw ? `rgb(${raw})` : fallback;
}

function readChartColors() {
  if (typeof window === "undefined") {
    return {
      gain: "#047857", loss: "#be123c", brand: "#33547a", grid: "#e2e8f0",
      text: "#64748b", tooltipBg: "#ffffff", tooltipBorder: "#e2e8f0",
    };
  }
  const s = getComputedStyle(document.documentElement);
  return {
    gain: token(s, "--gain", "#047857"),
    loss: token(s, "--loss", "#be123c"),
    brand: token(s, "--brand", "#33547a"),
    grid: token(s, "--border", "#e2e8f0"),
    text: token(s, "--text-mute", "#64748b"),
    tooltipBg: token(s, "--surface", "#ffffff"),
    tooltipBorder: token(s, "--border", "#e2e8f0"),
  };
}
