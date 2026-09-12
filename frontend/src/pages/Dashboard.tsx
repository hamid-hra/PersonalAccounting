import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import {
  Bar as RBar,
  BarChart,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { Bar, Empty, Loading, PageHeader, Pill, Stat } from "../components/ui";
import { api } from "../lib/api";
import { useChartColors, useReducedMotion } from "../lib/theme";
import { faDigits, jalaliDate, percent, toman, tomanShort } from "../lib/format";
import type {
  BudgetStatus,
  CategorySlice,
  Loan,
  MonthPoint,
  Summary,
  MarketItem,
  Observation,
  Portfolio,
} from "../lib/types";

export default function Dashboard() {
  const colors = useChartColors();
  const reduced = useReducedMotion();
  const summary = useQuery({
    queryKey: ["summary"],
    queryFn: () => api.get<Summary>("/api/analytics/summary"),
  });
  const prices = useQuery({
    queryKey: ["market-items"],
    queryFn: () => api.get<MarketItem[]>("/api/market/items"),
  });
  const portfolio = useQuery({
    queryKey: ["portfolio"],
    queryFn: () => api.get<Portfolio>("/api/market/portfolio"),
  });
  const observations = useQuery({
    queryKey: ["market-observations"],
    queryFn: () => api.get<{ text: string; tone: string }[]>("/api/market/observations"),
  });
  const monthly = useQuery({
    queryKey: ["monthly"],
    queryFn: () => api.get<MonthPoint[]>("/api/analytics/monthly", { months: 12 }),
  });
  const cats = useQuery({
    queryKey: ["by-category", "all"],
    queryFn: () => api.get<CategorySlice[]>("/api/analytics/by-category"),
  });
  const budgets = useQuery({
    queryKey: ["budget-status"],
    queryFn: () => api.get<BudgetStatus[]>("/api/budgets/status"),
  });
  const upcoming = useQuery({
    queryKey: ["loans-upcoming"],
    queryFn: () => api.get<any[]>("/api/loans/upcoming", { within_days: 15 }),
  });

  if (summary.isLoading) return <Loading />;
  const s = summary.data;
  if (!s || s.total_count === 0) {
    return (
      <>
        <PageHeader title="داشبورد" />
        <Empty
          title="هنوز تراکنشی وارد نشده است."
          hint="از صفحهٔ «ورود اکسل» فایل صورتحساب بانکت را اضافه کن تا تحلیل‌ها ساخته شوند."
        />
      </>
    );
  }

  const chartData = (monthly.data ?? []).map((m) => ({
    label: m.label.split(" ")[0],
    full: m.label,
    درآمد: Math.round(m.income_rial / 10),
    هزینه: Math.round(m.expense_rial / 10),
  }));

  const topCats = (cats.data ?? []).filter((c) => !c.parent_id).slice(0, 8);
  const pieData = topCats.map((c) => ({
    name: c.name,
    value: Math.round(c.total_rial / 10),
    color: c.color,
  }));

  return (
    <>
      <PageHeader
        title="داشبورد"
        subtitle={`آخرین تراکنش: ${jalaliDate(s.latest_transaction)}`}
      />

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat label={`درآمد ${s.label}`} rial={s.month_income_rial} tone="gain" />
        <Stat label={`هزینهٔ ${s.label}`} rial={s.month_expense_rial} tone="loss" />
        <Stat
          label={`خالص ${s.label}`}
          rial={s.month_net_rial}
          tone={s.month_net_rial >= 0 ? "gain" : "loss"}
        />
        <Stat
          label="سرمایه"
          rial={portfolio.data?.total_value_rial ?? 0}
          hint={
            portfolio.data?.today_change_rial
              ? `امروز ${portfolio.data.today_change_rial >= 0 ? "+" : "−"}${toman(
                  Math.abs(portfolio.data.today_change_rial),
                )} تومان`
              : "ارزش روز طلا و دلاری که داری"
          }
          tone={
            (portfolio.data?.today_change_rial ?? 0) > 0
              ? "gain"
              : (portfolio.data?.today_change_rial ?? 0) < 0
                ? "loss"
                : "neutral"
          }
        />
      </div>

      {!!prices.data?.length && (
        <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-4">
          {prices.data.map((p) => (
            <Link
              key={p.code}
              to="/market"
              className="card card-pad transition hover:border-brand"
            >
              <div className="flex items-center justify-between gap-2">
                <span className="truncate text-xs text-text-mute">{p.label_fa}</span>
                {p.change_percent !== null && p.change_percent !== undefined && (
                  <span
                    className={`shrink-0 text-[11px] font-medium tnum ${
                      p.change_percent >= 0 ? "text-gain" : "text-loss"
                    }`}
                  >
                    {p.change_percent >= 0 ? "▲" : "▼"}{" "}
                    {faDigits(Math.abs(p.change_percent).toFixed(2))}٪
                  </span>
                )}
              </div>
              <div className="mt-1 text-base font-bold tnum">
                {p.latest_rial ? toman(p.latest_rial) : "—"}
                <span className="ms-1 text-[11px] font-normal text-text-mute">تومان</span>
              </div>
            </Link>
          ))}
        </div>
      )}

      {!!observations.data?.length && (
        <div className="mt-3 card card-pad">
          <div className="mb-2 text-xs font-semibold text-text-mute">وضعیت بازار</div>
          <ul className="space-y-1.5">
            {observations.data.slice(0, 4).map((o, i) => (
              <li key={i} className="flex items-start gap-2 text-sm">
                <span
                  className={`mt-1.5 size-1.5 shrink-0 rounded-full ${
                    o.tone === "gain" ? "bg-gain" : o.tone === "loss" ? "bg-loss" : "bg-text-mute"
                  }`}
                  aria-hidden
                />
                <span className="text-text-soft">{o.text}</span>
              </li>
            ))}
          </ul>
          <p className="mt-2 text-[11px] text-text-mute">
            این‌ها گزارش وضعیت‌اند، نه پیش‌بینی یا پیشنهاد خرید و فروش.
          </p>
        </div>
      )}

      {s.pending_income_count > 0 && (
        <Link
          to="/review?tab=income"
          className="card card-pad mt-3 flex items-center justify-between transition hover:border-brand"
        >
          <div>
            <div className="text-sm font-semibold">
              {faDigits(s.pending_income_count)} واریزی منتظر تصمیم توست
            </div>
            <div className="mt-0.5 text-xs text-text-mute">
              {toman(s.pending_income_rial)} تومان — تا مشخص نکنی درآمد هست یا نه، در
              هیچ آماری شمرده نمی‌شود.
            </div>
          </div>
          <span className="text-text-mute" aria-hidden>←</span>
        </Link>
      )}

      {(s.pending_review > 0 || s.self_transfer_out_rial > 0) && (
        <div className="mt-3 grid gap-3 lg:grid-cols-2">
          {s.pending_review > 0 && (
            <Link
              to="/review"
              className="card card-pad flex items-center justify-between transition hover:border-brand"
            >
              <div>
                <div className="text-sm font-semibold">
                  {faDigits(s.pending_review)} تراکنش هنوز دسته ندارد
                </div>
                <div className="mt-0.5 text-xs text-text-mute">
                  فایل بانک نام فروشگاه را نمی‌دهد؛ با برچسب‌زدن چند پایانهٔ پرخرج،
                  بیشترِ پول معنا پیدا می‌کند.
                </div>
              </div>
              <span className="text-brand-text">←</span>
            </Link>
          )}
          <div className="card card-pad">
            <div className="text-sm font-semibold">
              {toman(s.self_transfer_out_rial)} تومان انتقال بین حساب‌های خودت
            </div>
            <div className="mt-0.5 text-xs text-text-mute">
              این‌ها هزینه نیستند و از همهٔ محاسبه‌ها کنار گذاشته شده‌اند.
            </div>
          </div>
        </div>
      )}

      {!!upcoming.data?.length && (
        <div className="card card-pad mt-3">
          <h2 className="text-sm font-semibold">اقساط نزدیک یا معوق</h2>
          <div className="mt-2 space-y-1.5">
            {upcoming.data.slice(0, 5).map((u) => (
              <Link
                key={u.installment_id}
                to={`/loans/${u.loan_id}`}
                className="flex items-center justify-between rounded-lg px-2 py-1.5 text-sm hover:bg-surface-raised"
              >
                <span>
                  {u.loan_title} — قسط {faDigits(u.seq)}
                </span>
                <span className="flex items-center gap-2">
                  <span className="tnum text-text-mute">{jalaliDate(u.due_jalali)}</span>
                  <Pill tone={u.status === "overdue" ? "red" : "amber"}>
                    {u.status === "overdue"
                      ? `${faDigits(Math.abs(u.days_left))} روز گذشته`
                      : `${faDigits(u.days_left)} روز مانده`}
                  </Pill>
                </span>
              </Link>
            ))}
          </div>
        </div>
      )}

      <div className="mt-3 grid gap-3 lg:grid-cols-5">
        <div className="card card-pad lg:col-span-3">
          <h2 className="text-sm font-semibold">درآمد و هزینه به تفکیک ماه</h2>
          <div className="mt-3 h-64" dir="ltr">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData} margin={{ top: 4, right: 4, left: 4, bottom: 4 }}>
                <XAxis
                  dataKey="label"
                  tick={{ fontSize: 11, fontFamily: "Vazirmatn", fill: colors.text }}
                  axisLine={false}
                  tickLine={false}
                />
                <YAxis
                  tickFormatter={(v) => tomanShort(v * 10)}
                  tick={{ fontSize: 10, fontFamily: "Vazirmatn", fill: colors.text }}
                  axisLine={false}
                  tickLine={false}
                  width={62}
                />
                <Tooltip
                  formatter={(v: number) => `${toman(v * 10)} تومان`}
                  contentStyle={{
                    fontFamily: "Vazirmatn",
                    fontSize: 12,
                    direction: "rtl",
                    background: colors.tooltipBg,
                    border: `1px solid ${colors.tooltipBorder}`,
                    borderRadius: 8,
                    color: "rgb(var(--text))",
                  }}
                />
                <Legend wrapperStyle={{ fontFamily: "Vazirmatn", fontSize: 12 }} />
                <RBar dataKey="درآمد" fill={colors.gain} radius={[4, 4, 0, 0]} isAnimationActive={!reduced} />
                <RBar dataKey="هزینه" fill={colors.loss} radius={[4, 4, 0, 0]} isAnimationActive={!reduced} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="card card-pad lg:col-span-2">
          <h2 className="text-sm font-semibold">هزینه به تفکیک دسته</h2>
          {pieData.length === 0 ? (
            <p className="mt-6 text-center text-xs text-text-mute">داده‌ای نیست.</p>
          ) : (
            <div className="mt-3 h-64" dir="ltr">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={pieData}
                    dataKey="value"
                    nameKey="name"
                    innerRadius="52%"
                    outerRadius="82%"
                    paddingAngle={2}
                    isAnimationActive={!reduced}
                  >
                    {pieData.map((d) => (
                      <Cell key={d.name} fill={d.color} />
                    ))}
                  </Pie>
                  <Tooltip
                    formatter={(v: number) => `${toman(v * 10)} تومان`}
                    contentStyle={{
                    fontFamily: "Vazirmatn",
                    fontSize: 12,
                    direction: "rtl",
                    background: colors.tooltipBg,
                    border: `1px solid ${colors.tooltipBorder}`,
                    borderRadius: 8,
                    color: "rgb(var(--text))",
                  }}
                  />
                </PieChart>
              </ResponsiveContainer>
            </div>
          )}
          <div className="mt-2 space-y-1">
            {topCats.slice(0, 5).map((c) => (
              <div key={c.name} className="flex items-center gap-2 text-xs">
                <span
                  className="size-2.5 shrink-0 rounded-full"
                  style={{ background: c.color }}
                />
                <span className="truncate">{c.name}</span>
                <span className="me-auto tnum text-text-mute">{toman(c.total_rial)}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {!!budgets.data?.length && (
        <div className="card card-pad mt-3">
          <h2 className="text-sm font-semibold">بودجهٔ {s.label}</h2>
          <div className="mt-3 space-y-3">
            {budgets.data.slice(0, 6).map((b) => (
              <div key={b.budget_id}>
                <div className="mb-1 flex items-center justify-between text-xs">
                  <span>{b.category_name}</span>
                  <span className={`tnum ${b.is_over ? "text-loss" : "text-text-mute"}`}>
                    {toman(b.spent_rial)} از {toman(b.amount_rial)} ({percent(b.ratio)})
                  </span>
                </div>
                <Bar ratio={b.ratio} color={b.color} />
              </div>
            ))}
          </div>
        </div>
      )}
    </>
  );
}
