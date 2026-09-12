import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, Info, Plus, RefreshCw, Trash2 } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import {
  Area,
  AreaChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import JalaliDate from "../components/JalaliDate";
import { Empty, ErrorBox, Loading, PageHeader, Pill, SuccessBox } from "../components/ui";
import { api } from "../lib/api";
import { faDigits, jalaliDate, latinDigits, parseTomanInput, toman, tomanShort } from "../lib/format";
import { useChartColors, useReducedMotion } from "../lib/theme";
import type { ItemStats, MarketItem, Portfolio, PricePoint, Quota } from "../lib/types";

const RANGES = [
  { days: 30, label: "۱ ماه" },
  { days: 90, label: "۳ ماه" },
  { days: 365, label: "۱ سال" },
  { days: 2000, label: "همه" },
];

function Pct({ value }: { value: number | null }) {
  if (value === null || value === undefined) return <span className="text-text-mute">—</span>;
  const positive = value >= 0;
  return (
    <span className={`tnum font-medium ${positive ? "text-gain" : "text-loss"}`}>
      {positive ? "+" : "−"}
      {faDigits(Math.abs(value * 100).toFixed(1))}٪
    </span>
  );
}

export default function Market() {
  const qc = useQueryClient();
  const colors = useChartColors();
  const reduced = useReducedMotion();
  const [selected, setSelected] = useState<string | null>(null);
  const [days, setDays] = useState(365);
  const [flash, setFlash] = useState("");
  const [error, setError] = useState("");
  const [holding, setHolding] = useState({ item_code: "", quantity: "", cost: "", date: "" });

  const quota = useQuery({ queryKey: ["quota"], queryFn: () => api.get<Quota>("/api/market/quota") });
  const items = useQuery({
    queryKey: ["market-items"],
    queryFn: () => api.get<MarketItem[]>("/api/market/items"),
  });
  // تا وقتی فهرست نیامده، اولین قلم انتخاب می‌شود — نمادها به سرویس
  // بستگی دارند و نباید در کد ثابت باشند.
  const activeCode = selected ?? items.data?.[0]?.code ?? null;
  const holdingCode = holding.item_code || items.data?.[0]?.code || "";

  const stats = useQuery({
    queryKey: ["market-stats", activeCode],
    queryFn: () => api.get<ItemStats>(`/api/market/items/${activeCode}/stats`),
    enabled: !!activeCode,
  });
  const series = useQuery({
    queryKey: ["market-series", activeCode, days],
    queryFn: () => api.get<PricePoint[]>(`/api/market/items/${activeCode}/series`, { days }),
    enabled: !!activeCode,
  });
  const portfolio = useQuery({
    queryKey: ["portfolio"],
    queryFn: () => api.get<Portfolio>("/api/market/portfolio"),
  });

  const run = (fn: () => Promise<unknown>, ok: string) =>
    fn()
      .then(() => {
        setFlash(ok);
        setError("");
        qc.invalidateQueries();
      })
      .catch((e: Error) => {
        setError(e.message);
        setFlash("");
      });

  const addHolding = useMutation({
    mutationFn: (body: unknown) => api.post("/api/market/holdings", body),
    onSuccess: () => {
      setHolding({ ...holding, quantity: "", cost: "", date: "" });
      setError("");
      qc.invalidateQueries();
    },
    onError: (e: Error) => setError(e.message),
  });

  const q = quota.data;
  const chartData = (series.data ?? []).map((p) => ({
    label: p.jalali_date.slice(2),
    value: Math.round(p.close_rial / 10),
  }));
  const current = items.data?.find((i) => i.code === activeCode);

  return (
    <>
      <PageHeader
        title="بازار و دارایی"
        subtitle="قیمت طلا و ارز — و ارزش روزِ چیزی که نگه داشته‌ای"
        action={
          <button
            className="btn-primary"
            onClick={() => run(() => api.post("/api/market/refresh"), "قیمت‌ها به‌روز شد.")}
            disabled={!q?.configured || (q?.usable ?? 0) <= 0}
          >
            <RefreshCw size={15} aria-hidden />
            به‌روزرسانی قیمت‌ها
          </button>
        }
      />

      {flash && (
        <div className="mb-3">
          <SuccessBox message={flash} />
        </div>
      )}
      {error && (
        <div className="mb-3">
          <ErrorBox message={error} />
        </div>
      )}

      {q && !q.configured && (
        <div className="mb-4 flex items-start gap-2 rounded-lg border border-warn/30 bg-warn-soft px-3.5 py-3 text-sm text-warn">
          <Info size={16} className="mt-0.5 shrink-0" aria-hidden />
          <div>
            کلید سرویس قیمت هنوز ثبت نشده است.{" "}
            <Link to="/settings" className="font-semibold underline">
              در تنظیمات واردش کن
            </Link>{" "}
            — کلید رایگان است و بقیهٔ برنامه بدون آن هم کامل کار می‌کند.
          </div>
        </div>
      )}

      {q?.configured && (
        <div className="card card-pad mb-4 flex flex-wrap items-center justify-between gap-3">
          <div className="text-sm">
            {q.provider_label} — سهمیهٔ {q.window_label}:{" "}
            <b className="tnum">{faDigits(q.used)}</b> از{" "}
            <b className="tnum">{faDigits(q.limit)}</b> درخواست مصرف شده
          </div>
          <div className="flex items-center gap-2">
            <div className="h-2 w-40 overflow-hidden rounded-full bg-surface-raised">
              <div
                className={`h-full rounded-full ${q.usable > 0 ? "bg-brand" : "bg-loss"}`}
                style={{ width: `${Math.min((q.used / q.limit) * 100, 100)}%` }}
              />
            </div>
            <Pill tone={q.usable > 20 ? "green" : q.usable > 0 ? "amber" : "red"}>
              {faDigits(q.usable)} قابل استفاده
            </Pill>
          </div>
        </div>
      )}

      {/* ---------------- قیمت‌ها ---------------- */}
      <div className="mb-4 grid gap-3 lg:grid-cols-[18rem_1fr]">
        <div className="card card-pad">
          <h2 className="mb-2 text-sm font-semibold">قیمت‌ها</h2>
          {items.isLoading ? (
            <Loading rows={5} />
          ) : (
            <div className="space-y-1">
              {(items.data ?? []).map((i) => (
                <button
                  key={i.code}
                  onClick={() => setSelected(i.code)}
                  className={`flex w-full items-center justify-between rounded-lg px-2.5 py-2 text-right text-sm transition-colors ${
                    activeCode === i.code
                      ? "bg-brand-soft font-semibold text-brand-text"
                      : "hover:bg-surface-raised"
                  }`}
                >
                  <span className="truncate">{i.label_fa}</span>
                  <span className="shrink-0 tnum text-xs">
                    {i.latest_rial ? toman(i.latest_rial) : "—"}
                  </span>
                </button>
              ))}
            </div>
          )}
        </div>

        <div className="card card-pad">
          <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
            <div>
              <h2 className="text-sm font-semibold">{current?.label_fa}</h2>
              {stats.data?.has_data && (
                <p className="mt-0.5 text-xs text-text-mute">
                  {current?.unit_fa} · آخرین قیمت {jalaliDate(stats.data.latest_date)}
                </p>
              )}
            </div>
            <div className="flex gap-1">
              {RANGES.map((r) => (
                <button
                  key={r.days}
                  onClick={() => setDays(r.days)}
                  className={`rounded-md px-2.5 py-1 text-xs transition-colors ${
                    days === r.days
                      ? "bg-brand text-brand-fg"
                      : "bg-surface-raised text-text-soft hover:text-text"
                  }`}
                >
                  {r.label}
                </button>
              ))}
            </div>
          </div>

          {!stats.data?.has_data ? (
            <div className="py-8 text-center">
              <p className="text-sm text-text-mute">هنوز تاریخچه‌ای برای این قلم نیست.</p>
              <button
                className="btn-ghost mt-3 text-xs"
                disabled={!q?.configured || (q?.usable ?? 0) <= 0}
                onClick={() =>
                  run(
                    () => api.post(`/api/market/items/${activeCode}/backfill?days=365`),
                    "تاریخچهٔ یک سال گرفته شد (۱ درخواست).",
                  )
                }
              >
                <Download size={14} aria-hidden />
                گرفتن تاریخچهٔ یک سال — فقط ۱ درخواست
              </button>
            </div>
          ) : (
            <>
              <div className="h-52" dir="ltr">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={chartData} margin={{ top: 4, right: 4, left: 4, bottom: 0 }}>
                    <defs>
                      <linearGradient id="priceFill" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor={colors.brand} stopOpacity={0.35} />
                        <stop offset="100%" stopColor={colors.brand} stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <XAxis
                      dataKey="label"
                      tick={{ fontSize: 10, fontFamily: "Vazirmatn", fill: colors.text }}
                      axisLine={false}
                      tickLine={false}
                      minTickGap={40}
                    />
                    <YAxis
                      tickFormatter={(v) => tomanShort(v * 10)}
                      tick={{ fontSize: 10, fontFamily: "Vazirmatn", fill: colors.text }}
                      axisLine={false}
                      tickLine={false}
                      width={64}
                      domain={["dataMin", "dataMax"]}
                    />
                    <Tooltip
                      formatter={(v: number) => [`${toman(v * 10)} تومان`, ""]}
                      contentStyle={{
                        fontFamily: "Vazirmatn",
                        fontSize: 12,
                        direction: "rtl",
                        background: colors.tooltipBg,
                        border: `1px solid ${colors.tooltipBorder}`,
                        borderRadius: 8,
                      }}
                    />
                    <Area
                      type="monotone"
                      dataKey="value"
                      stroke={colors.brand}
                      strokeWidth={2}
                      fill="url(#priceFill)"
                      isAnimationActive={!reduced}
                    />
                  </AreaChart>
                </ResponsiveContainer>
              </div>

              <div className="mt-3 grid grid-cols-2 gap-3 border-t border-border pt-3 sm:grid-cols-4">
                {[
                  ["۷ روز", stats.data.change_7d],
                  ["۳۰ روز", stats.data.change_30d],
                  ["۹۰ روز", stats.data.change_90d],
                  ["۱ سال", stats.data.change_365d],
                ].map(([label, v]) => (
                  <div key={label as string}>
                    <div className="text-[11px] text-text-mute">{label as string}</div>
                    <Pct value={v as number | null} />
                  </div>
                ))}
              </div>

              <div className="mt-3 grid grid-cols-2 gap-3 text-xs sm:grid-cols-4">
                <div>
                  <div className="text-[11px] text-text-mute">بیشترین</div>
                  <div className="tnum">{toman(stats.data.high_rial!)}</div>
                </div>
                <div>
                  <div className="text-[11px] text-text-mute">کمترین</div>
                  <div className="tnum">{toman(stats.data.low_rial!)}</div>
                </div>
                <div>
                  <div className="text-[11px] text-text-mute">میانگین ۳۰ روزه</div>
                  <div className="tnum">
                    {stats.data.ma_30 ? toman(stats.data.ma_30) : "—"}
                  </div>
                </div>
                <div>
                  <div className="text-[11px] text-text-mute">نوسان سالانه</div>
                  <div className="tnum">
                    {stats.data.volatility_annual
                      ? `${faDigits((stats.data.volatility_annual * 100).toFixed(0))}٪`
                      : "—"}
                  </div>
                </div>
              </div>

              <p className="mt-3 rounded-lg bg-surface-raised px-3 py-2 text-[11px] leading-5 text-text-mute">
                این اعداد <b>توصیفی‌اند، نه پیش‌بینی</b>. آنچه در گذشته رخ داده را نشان
                می‌دهند و دربارهٔ آینده چیزی نمی‌گویند. تصمیم نگه‌داشتن یا فروختن دارایی با
                خودت است — این برنامه مشاور مالی نیست و سیگنال خرید و فروش نمی‌دهد.
              </p>
            </>
          )}
        </div>
      </div>

      {/* ---------------- سبد دارایی ---------------- */}
      <h2 className="mb-2 text-sm font-semibold">سبد دارایی من</h2>

      <form
        className="card card-pad mb-3 flex flex-wrap items-end gap-3"
        onSubmit={(e) => {
          e.preventDefault();
          const qty = Number(latinDigits(holding.quantity));
          const d = latinDigits(holding.date).replace(/-/g, "/");
          if (!qty || !/^\d{4}\/\d{1,2}\/\d{1,2}$/.test(d)) {
            setError("مقدار و تاریخ خرید (مثل ۱۴۰۵/۰۱/۱۰) لازم است.");
            return;
          }
          addHolding.mutate({
            item_code: holdingCode,
            quantity: qty,
            acquired_jalali: d,
            cost_rial: parseTomanInput(holding.cost),
          });
        }}
      >
        <div className="min-w-[10rem]">
          <label className="label" htmlFor="h-item">
            دارایی
          </label>
          <select
            id="h-item"
            className="input"
            value={holdingCode}
            onChange={(e) => setHolding((h) => ({ ...h, item_code: e.target.value }))}
          >
            {(items.data ?? []).map((i) => (
              <option key={i.code} value={i.code}>
                {i.label_fa}
              </option>
            ))}
          </select>
        </div>
        {[
          ["quantity", "مقدار", "۱۰"],
          ["cost", "قیمت تمام‌شده (تومان، اختیاری)", "۵۰۰۰۰۰۰۰"],
        ].map(([key, label, ph]) => (
          <div className="min-w-[10rem] flex-1" key={key}>
            <label className="label" htmlFor={`h-${key}`}>
              {label}
            </label>
            <input
              id={`h-${key}`}
              className="input tnum"
              dir="ltr"
              placeholder={ph}
              value={holding[key as keyof typeof holding]}
              onChange={(e) => setHolding((h) => ({ ...h, [key]: e.target.value }))}
            />
          </div>
        ))}
        <div className="min-w-[11rem] flex-1">
          <label className="label" htmlFor="h-date">
            تاریخ خرید
          </label>
          <JalaliDate
            id="h-date"
            value={holding.date}
            onChange={(v) => setHolding((h) => ({ ...h, date: v }))}
          />
        </div>
        <button className="btn-primary" disabled={addHolding.isPending}>
          <Plus size={15} aria-hidden />
          افزودن
        </button>
      </form>

      {!portfolio.data?.holdings.length ? (
        <Empty
          title="هنوز دارایی‌ای ثبت نشده."
          hint="مثلاً «۱۰ گرم طلای ۱۸ عیار» را ثبت کن تا ارزش روز و سود/زیانش را ببینی."
        />
      ) : (
        <>
          <div className="card scroll-x">
            <table className="w-full min-w-[48rem]">
              <thead className="border-b border-border bg-surface-raised">
                <tr>
                  <th className="th">دارایی</th>
                  <th className="th">مقدار</th>
                  <th className="th">قیمت تمام‌شده</th>
                  <th className="th">ارزش امروز</th>
                  <th className="th">سود / زیان</th>
                  <th className="th"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {portfolio.data.holdings.map((h) => (
                  <tr key={h.id}>
                    <td className="td">
                      <div className="font-medium">{h.item_label}</div>
                      <div className="text-[11px] text-text-mute">
                        خرید {jalaliDate(h.acquired_jalali)}
                      </div>
                    </td>
                    <td className="td tnum">
                      {faDigits(h.quantity)}{" "}
                      <span className="text-[11px] text-text-mute">{h.unit_fa}</span>
                    </td>
                    <td className="td tnum">{h.cost_rial ? toman(h.cost_rial) : "—"}</td>
                    <td className="td font-semibold tnum">
                      {h.value_rial ? toman(h.value_rial) : "—"}
                    </td>
                    <td className="td">
                      {h.profit_rial === null ? (
                        <span className="text-text-mute">—</span>
                      ) : (
                        <span
                          className={`tnum font-medium ${h.profit_rial >= 0 ? "text-gain" : "text-loss"}`}
                        >
                          {h.profit_rial >= 0 ? "+" : "−"}
                          {toman(Math.abs(h.profit_rial))}
                          <span className="ms-1 text-[11px]">
                            (<Pct value={h.profit_ratio} />)
                          </span>
                        </span>
                      )}
                    </td>
                    <td className="td">
                      <button
                        className="btn-icon text-loss"
                        aria-label="حذف دارایی"
                        onClick={() =>
                          api
                            .del(`/api/market/holdings/${h.id}`)
                            .then(() => qc.invalidateQueries())
                        }
                      >
                        <Trash2 size={15} aria-hidden />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="card card-pad mt-3 flex flex-wrap items-center justify-between gap-3">
            <div>
              <div className="text-xs text-text-mute">ارزش کل سبد</div>
              <div className="text-xl font-bold tnum">
                {toman(portfolio.data.total_value_rial)}
                <span className="ms-1 text-xs font-normal text-text-mute">تومان</span>
              </div>
            </div>
            {portfolio.data.total_profit_rial !== null && (
              <div className="text-left">
                <div className="text-xs text-text-mute">سود / زیان تحقق‌نیافته</div>
                <div
                  className={`text-xl font-bold tnum ${
                    portfolio.data.total_profit_rial >= 0 ? "text-gain" : "text-loss"
                  }`}
                >
                  {portfolio.data.total_profit_rial >= 0 ? "+" : "−"}
                  {toman(Math.abs(portfolio.data.total_profit_rial))}
                  <span className="ms-2 text-sm">
                    <Pct value={portfolio.data.total_profit_ratio} />
                  </span>
                </div>
              </div>
            )}
          </div>
        </>
      )}
    </>
  );
}
