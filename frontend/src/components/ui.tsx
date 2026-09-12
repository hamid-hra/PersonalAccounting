import { AlertTriangle, CheckCircle2, Inbox } from "lucide-react";

import { faDigits, percent, toman } from "../lib/format";
import { CountUp, Item, Stagger } from "./motion";

export function PageHeader({
  title,
  subtitle,
  action,
}: {
  title: string;
  subtitle?: string;
  action?: React.ReactNode;
}) {
  return (
    <header className="mb-5 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="text-xl font-bold sm:text-2xl">{title}</h1>
        {subtitle && <p className="mt-1 text-sm text-text-mute">{subtitle}</p>}
      </div>
      {action}
    </header>
  );
}

export function Stat({
  label,
  rial,
  hint,
  tone = "neutral",
}: {
  label: string;
  rial: number;
  hint?: string;
  tone?: "neutral" | "gain" | "loss";
}) {
  const color = tone === "gain" ? "text-gain" : tone === "loss" ? "text-loss" : "text-text";
  return (
    <div className="card card-pad">
      <div className="text-xs text-text-mute">{label}</div>
      <div className={`mt-1.5 text-xl font-bold tnum sm:text-2xl ${color}`}>
        <CountUp value={rial} format={(n) => toman(n)} />
        <span className="ms-1 text-xs font-normal text-text-mute">تومان</span>
      </div>
      {hint && <div className="mt-1 text-[11px] text-text-mute">{hint}</div>}
    </div>
  );
}

export function Empty({ title, hint }: { title: string; hint?: string }) {
  return (
    <div className="card card-pad grid place-items-center py-14 text-center">
      <Inbox size={28} className="mb-3 text-text-mute" aria-hidden />
      <div className="text-sm font-medium text-text-soft">{title}</div>
      {hint && <div className="mt-1.5 max-w-md text-xs text-text-mute">{hint}</div>}
    </div>
  );
}

/** اسکلت لودینگ — جای محتوا را نگه می‌دارد تا صفحه هنگام آمدن داده نپرد. */
export function Loading({ rows = 4 }: { rows?: number }) {
  return (
    <div className="card card-pad space-y-3" aria-busy="true" aria-label="در حال بارگذاری">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="flex items-center gap-3">
          <div className="skeleton h-9 w-9 rounded-full" />
          <div className="flex-1 space-y-2">
            <div className="skeleton h-3" style={{ width: `${60 + ((i * 13) % 30)}%` }} />
            <div className="skeleton h-2.5" style={{ width: `${35 + ((i * 17) % 25)}%` }} />
          </div>
          <div className="skeleton h-3 w-20" />
        </div>
      ))}
    </div>
  );
}

export function StatSkeleton({ count = 4 }: { count?: number }) {
  return (
    <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="card card-pad space-y-2">
          <div className="skeleton h-2.5 w-16" />
          <div className="skeleton h-6 w-28" />
        </div>
      ))}
    </div>
  );
}

export function Bar({ ratio, color }: { ratio: number; color?: string }) {
  const pct = Math.min(Math.max(ratio, 0), 1) * 100;
  const over = ratio > 1;
  return (
    <div className="h-2 w-full overflow-hidden rounded-full bg-surface-raised">
      <div
        className={`h-full rounded-full transition-[width] duration-500 ${
          over ? "bg-loss" : color ? "" : "bg-brand"
        }`}
        style={{ width: `${pct}%`, background: over ? undefined : color }}
      />
    </div>
  );
}

const TONES = {
  slate: "bg-surface-raised text-text-soft",
  amber: "bg-warn-soft text-warn",
  green: "bg-gain-soft text-gain",
  red: "bg-loss-soft text-loss",
  brand: "bg-brand-soft text-brand-text",
} as const;

export function Pill({
  children,
  tone = "slate",
}: {
  children: React.ReactNode;
  tone?: keyof typeof TONES;
}) {
  return <span className={`chip ${TONES[tone]}`}>{children}</span>;
}

export function ErrorBox({ message }: { message: string }) {
  return (
    <div
      role="alert"
      className="flex items-start gap-2 rounded-lg border border-loss/30 bg-loss-soft px-3.5 py-2.5 text-sm text-loss"
    >
      <AlertTriangle size={16} className="mt-0.5 shrink-0" aria-hidden />
      <span>{message}</span>
    </div>
  );
}

export function SuccessBox({ message }: { message: string }) {
  return (
    <div
      role="status"
      className="flex items-start gap-2 rounded-lg border border-gain/30 bg-gain-soft px-3.5 py-2.5 text-sm text-gain"
    >
      <CheckCircle2 size={16} className="mt-0.5 shrink-0" aria-hidden />
      <span>{message}</span>
    </div>
  );
}

export { faDigits, percent, CountUp, Item, Stagger };
