import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeftRight,
  CircleDollarSign,
  Coins,
  Contact2,
  Gauge,
  HandCoins,
  Landmark,
  ListChecks,
  LogOut,
  ListTodo,
  PanelRightClose,
  PanelRightOpen,
  Monitor,
  Moon,
  PiggyBank,
  Receipt,
  Settings2,
  Sun,
  Upload,
} from "lucide-react";
import { useEffect, useState } from "react";
import { NavLink, useLocation } from "react-router-dom";

import { api } from "../lib/api";
import { faDigits } from "../lib/format";
import { useTheme } from "../lib/theme";
import type { Summary } from "../lib/types";

const NAV = [
  { to: "/", label: "داشبورد", Icon: Gauge },
  { to: "/review", label: "صف بررسی", Icon: ListChecks, badge: true },
  { to: "/transactions", label: "تراکنش‌ها", Icon: Receipt },
  { to: "/insights", label: "تحلیل هدررفت", Icon: CircleDollarSign },
  { to: "/market", label: "بازار و دارایی", Icon: Coins },
  { to: "/debts", label: "قرض‌ها", Icon: HandCoins },
  { to: "/loans", label: "وام‌ها", Icon: Landmark },
  { to: "/wishlist", label: "لیست نیازها", Icon: ListTodo },
  { to: "/budgets", label: "بودجه", Icon: PiggyBank },
  { to: "/contacts", label: "مخاطبین", Icon: Contact2 },
  { to: "/links", label: "انتقال بین‌بانکی", Icon: ArrowLeftRight },
  { to: "/import", label: "ورود اکسل", Icon: Upload },
  { to: "/settings", label: "تنظیمات", Icon: Settings2 },
];

function ThemeToggle() {
  const { mode, setMode } = useTheme();
  const options = [
    { value: "light", label: "روشن", Icon: Sun },
    { value: "dark", label: "تیره", Icon: Moon },
    { value: "system", label: "سیستم", Icon: Monitor },
  ] as const;

  return (
    <div
      className="flex items-center gap-0.5 rounded-lg bg-surface-raised p-0.5"
      role="group"
      aria-label="حالت نمایش"
    >
      {options.map(({ value, label, Icon }) => (
        <button
          key={value}
          onClick={() => setMode(value)}
          aria-label={label}
          aria-pressed={mode === value}
          title={label}
          className={`flex size-8 items-center justify-center rounded-md transition-colors ${
            mode === value
              ? "bg-surface text-brand-text shadow-sm"
              : "text-text-mute hover:text-text"
          }`}
        >
          <Icon size={15} aria-hidden />
        </button>
      ))}
    </div>
  );
}

export default function Shell({ children }: { children: React.ReactNode }) {
  const qc = useQueryClient();
  const location = useLocation();
  // حالت جمع‌شده مثل تم یادش می‌ماند
  const [collapsed, setCollapsed] = useState(
    () => localStorage.getItem("pa-sidebar") === "collapsed",
  );
  useEffect(() => {
    localStorage.setItem("pa-sidebar", collapsed ? "collapsed" : "open");
  }, [collapsed]);

  const { data: summary } = useQuery({
    queryKey: ["summary"],
    queryFn: () => api.get<Summary>("/api/analytics/summary"),
    refetchInterval: 60_000,
  });

  const logout = async () => {
    await api.post("/api/auth/logout");
    qc.clear();
    window.location.reload();
  };

  return (
    <div
      className="min-h-screen lg:grid lg:transition-[grid-template-columns] lg:duration-300"
      style={{ gridTemplateColumns: `${collapsed ? "4.25rem" : "15.5rem"} 1fr` }}
    >
      {/*
        نوار کناری از surface-raised رنگ می‌گیرد نه surface، تا ته‌رنگ تم
        انتخابی در حالت روشن هم واقعاً دیده شود.
      */}
      <aside className="border-border bg-surface-raised lg:sticky lg:top-0 lg:h-screen lg:overflow-y-auto lg:border-l">
        <div className="flex items-center justify-between gap-2 px-3 py-4 lg:px-4">
          {!collapsed && (
            <div className="min-w-0">
              <div className="truncate text-base font-bold">حسابداری شخصی</div>
              <div className="truncate text-xs text-text-mute">دخل و خرج، بدون حدس</div>
            </div>
          )}
          <button
            onClick={() => setCollapsed((v) => !v)}
            className="btn-icon hidden shrink-0 lg:inline-flex"
            aria-label={collapsed ? "باز کردن نوار کناری" : "بستن نوار کناری"}
            aria-expanded={!collapsed}
            title={collapsed ? "باز کردن نوار کناری" : "بستن نوار کناری"}
          >
            {collapsed ? <PanelRightOpen size={17} /> : <PanelRightClose size={17} />}
          </button>
        </div>

        {collapsed && <ThemeToggleCompact />}
        {!collapsed && (
          <div className="px-4 pb-3">
            <ThemeToggle />
          </div>
        )}

        <nav className="flex gap-1 overflow-x-auto px-2 pb-3 lg:flex-col lg:overflow-visible">
          {NAV.map(({ to, label, Icon, badge }) => (
            <NavLink
              key={to}
              to={to}
              end={to === "/"}
              title={label}
              className={({ isActive }) =>
                `flex shrink-0 items-center gap-2.5 rounded-lg py-2 text-sm transition-colors ${
                  collapsed ? "lg:justify-center lg:px-0" : ""
                } px-3 ${
                  isActive
                    ? "bg-brand-soft font-semibold text-brand-text"
                    : "text-text-soft hover:bg-surface hover:text-text"
                }`
              }
            >
              <Icon size={17} aria-hidden className="shrink-0" />
              <span className={collapsed ? "whitespace-nowrap lg:hidden" : "whitespace-nowrap"}>
                {label}
              </span>
              {badge && !!summary?.pending_review && (
                <span
                  className={`rounded-full bg-warn-soft px-1.5 py-0.5 text-[11px] font-semibold text-warn tnum ${
                    collapsed ? "me-auto lg:hidden" : "me-auto"
                  }`}
                >
                  {faDigits(summary.pending_review)}
                </span>
              )}
            </NavLink>
          ))}
        </nav>

        <div className="hidden px-3 py-4 lg:block">
          <button
            onClick={logout}
            className={`btn-ghost w-full text-xs ${collapsed ? "lg:px-0" : ""}`}
            aria-label="خروج از حساب"
            title="خروج از حساب"
          >
            <LogOut size={14} aria-hidden />
            {!collapsed && "خروج از حساب"}
          </button>
        </div>
      </aside>

      <main key={location.pathname} className="p-4 sm:p-6 lg:p-8">
        <div className="mx-auto max-w-7xl">{children}</div>
      </main>
    </div>
  );
}

/** در حالت جمع‌شده فقط یک دکمه، تا فضای عمودی هدر نرود. */
function ThemeToggleCompact() {
  const { mode, setMode } = useTheme();
  const next = mode === "light" ? "dark" : mode === "dark" ? "system" : "light";
  const Icon = mode === "light" ? Sun : mode === "dark" ? Moon : Monitor;
  return (
    <div className="mb-2 flex justify-center">
      <button
        onClick={() => setMode(next)}
        className="btn-icon"
        aria-label="تغییر حالت نمایش"
        title="تغییر حالت نمایش"
      >
        <Icon size={16} aria-hidden />
      </button>
    </div>
  );
}
