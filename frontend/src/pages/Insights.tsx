import { useQuery } from "@tanstack/react-query";

import { Bar, Empty, Loading, PageHeader, Pill } from "../components/ui";
import { api } from "../lib/api";
import { faDigits, jalaliDate, percent, toman } from "../lib/format";
import type { MicroSpend, MomReport, Recurring } from "../lib/types";

/** تحلیل هدررفت: اشتراک‌های تکرارشونده، جمع خردخرجی، جهش ماه‌به‌ماه. */
function RecurringTable({ rows, tone }: { rows: Recurring[]; tone: "loss" | "mute" }) {
  return (
    <div className="card scroll-x">
      <table className="w-full min-w-[52rem]">
        <thead className="border-b border-border bg-surface-raised">
          <tr>
            <th className="th">مورد</th>
            <th className="th">دوره</th>
            <th className="th">تکرار</th>
            <th className="th">میانگین هر بار</th>
            <th className="th">پرداخت‌شده تا حالا</th>
            <th className="th">برآورد سالانه</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {rows.map((r) => (
            <tr key={`${r.key_kind}:${r.key_value}`}>
              <td className="td max-w-[20rem]">
                <div className="font-medium">{r.name}</div>
                <div className="mt-0.5 truncate text-[11px] text-text-mute">
                  {r.category_name ?? "بدون دسته"} · آخرین بار {jalaliDate(r.last_seen)}
                </div>
              </td>
              <td className="td">
                <Pill tone="brand">{r.cadence}</Pill>
                <div className="mt-0.5 text-[11px] tnum text-text-mute">
                  هر {faDigits(r.median_gap_days)} روز
                </div>
              </td>
              <td className="td tnum">{faDigits(r.occurrences)} بار</td>
              <td className="td tnum">{toman(r.avg_amount_rial)}</td>
              <td className="td tnum text-text-mute">{toman(r.total_paid_rial)}</td>
              <td
                className={`td font-semibold tnum ${tone === "loss" ? "text-loss" : "text-text"}`}
              >
                {toman(r.estimated_annual_rial)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function Insights() {
  const recurring = useQuery({
    queryKey: ["recurring"],
    queryFn: () => api.get<Recurring[]>("/api/analytics/insights/recurring"),
  });
  const micro = useQuery({
    queryKey: ["micro"],
    queryFn: () => api.get<MicroSpend>("/api/analytics/insights/micro-spend"),
  });
  const mom = useQuery({
    queryKey: ["mom"],
    queryFn: () => api.get<MomReport>("/api/analytics/insights/month-over-month"),
  });

  if (recurring.isLoading) return <Loading />;

  /*
    قسط وام و اجاره هم تکرارشونده‌اند ولی «هدررفت» نیستند — نمی‌شود
    قطعشان کرد. جدا نگه داشتنشان باعث می‌شود عدد هدررفت واقعی بماند.
  */
  const all = recurring.data ?? [];
  const commitments = all.filter((r) => r.is_commitment);
  const subscriptions = all.filter((r) => !r.is_commitment);
  const annualTotal = subscriptions.reduce((s, r) => s + r.estimated_annual_rial, 0);
  const commitmentTotal = commitments.reduce((s, r) => s + r.estimated_annual_rial, 0);
  const spikes = (mom.data?.categories ?? []).filter((c) => c.is_spike);

  return (
    <>
      <PageHeader
        title="تحلیل هدررفت"
        subtitle="سه نگاه به پولی که بی‌آنکه حس شود از حساب می‌رود"
      />

      {/* ---------------- اشتراک‌های قابل قطع ---------------- */}
      <section className="mb-6">
        <div className="mb-2 flex flex-wrap items-baseline justify-between gap-2">
          <h2 className="text-sm font-semibold">اشتراک‌ها و خرج‌های تکرارشونده</h2>
          {annualTotal > 0 && (
            <span className="text-xs text-text-mute">
              برآورد سالانه:{" "}
              <b className="text-loss tnum">{toman(annualTotal)} تومان</b>
            </span>
          )}
        </div>

        {!subscriptions.length ? (
          <Empty
            title="خرج تکرارشوندهٔ قابل‌قطعی پیدا نشد."
            hint="برای کشف الگو، دست‌کم سه پرداخت با فاصلهٔ منظم و مبلغ نزدیک لازم است."
          />
        ) : (
          <RecurringTable rows={subscriptions} tone="loss" />
        )}
      </section>

      {/* ---------------- تعهدهای ثابت ---------------- */}
      {commitments.length > 0 && (
        <section className="mb-6">
          <div className="mb-2 flex flex-wrap items-baseline justify-between gap-2">
            <div>
              <h2 className="text-sm font-semibold">تعهدهای ثابت</h2>
              <p className="mt-0.5 text-[11px] text-text-mute">
                اقساط وام و اجاره — اینها را نمی‌شود قطع کرد، پس هدررفت حساب نمی‌شوند.
              </p>
            </div>
            <span className="text-xs text-text-mute">
              برآورد سالانه: <b className="tnum">{toman(commitmentTotal)} تومان</b>
            </span>
          </div>
          <RecurringTable rows={commitments} tone="mute" />
        </section>
      )}

      {/* ---------------- خردخرجی ---------------- */}
      <section className="mb-6">
        <h2 className="mb-2 text-sm font-semibold">خردخرجی‌ها</h2>
        {!micro.data ? (
          <Loading />
        ) : (
          <div className="card card-pad">
            <p className="text-sm">
              <b className="tnum">{faDigits(micro.data.count)}</b> تراکنش زیر{" "}
              <b className="tnum">{toman(micro.data.threshold_rial)}</b> تومان، روی هم{" "}
              <b className="tnum text-loss">{toman(micro.data.total_rial)}</b> تومان —
              یعنی <b>{percent(micro.data.share_of_expense)}</b> کل هزینه‌ات.
            </p>
            <p className="mt-1 text-xs text-text-mute">
              هرکدام به‌تنهایی ناچیزند؛ جمعشان است که دیده نمی‌شود. آستانه در
              «تنظیمات» قابل تغییر است.
            </p>
            <div className="mt-4 space-y-2.5">
              {micro.data.by_category.map((c) => (
                <div key={c.name}>
                  <div className="mb-1 flex items-center justify-between text-xs">
                    <span className="flex items-center gap-1.5">
                      <span
                        className="size-2.5 rounded-full"
                        style={{ background: c.color }}
                      />
                      {c.name}
                      <span className="text-text-mute">
                        ({faDigits(c.count)} بار)
                      </span>
                    </span>
                    <span className="tnum">{toman(c.total_rial)} تومان</span>
                  </div>
                  <Bar
                    ratio={c.total_rial / (micro.data!.by_category[0]?.total_rial || 1)}
                    color={c.color}
                  />
                </div>
              ))}
            </div>
          </div>
        )}
      </section>

      {/* ---------------- ماه‌به‌ماه ---------------- */}
      <section>
        <h2 className="mb-2 text-sm font-semibold">
          مقایسهٔ ماه‌به‌ماه
          {mom.data?.current_period && (
            <span className="ms-2 font-normal text-text-mute">
              {mom.data.current_period.label} در برابر میانگین{" "}
              {faDigits(mom.data.lookback_months)} ماه قبل
            </span>
          )}
        </h2>

        {spikes.length > 0 && (
          <div className="mb-3 rounded-lg border border-warn/30 bg-warn-soft px-3.5 py-2.5 text-sm text-warn">
            {spikes.length === 1 ? "یک دسته" : `${faDigits(spikes.length)} دسته`} نسبت به
            روال همیشگی جهش داشته:{" "}
            <b>{spikes.map((s) => s.name).join("، ")}</b>
          </div>
        )}

        {!mom.data?.categories.length ? (
          <Empty title="برای مقایسه، داده‌های چند ماه لازم است." />
        ) : (
          <div className="card scroll-x">
            <table className="w-full min-w-[40rem]">
              <thead className="border-b border-border bg-surface-raised">
                <tr>
                  <th className="th">دسته</th>
                  <th className="th">این ماه</th>
                  <th className="th">میانگین قبل</th>
                  <th className="th">تغییر</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {mom.data.categories.map((c) => (
                  <tr key={c.name} className={c.is_spike ? "bg-warn-soft/60" : ""}>
                    <td className="td">
                      <span className="flex items-center gap-1.5">
                        <span
                          className="size-2.5 rounded-full"
                          style={{ background: c.color }}
                        />
                        {c.name}
                      </span>
                    </td>
                    <td className="td tnum">{toman(c.current_rial)}</td>
                    <td className="td tnum text-text-mute">{toman(c.baseline_rial)}</td>
                    <td className="td">
                      {c.ratio === null ? (
                        <span className="text-text-mute">—</span>
                      ) : (
                        <span
                          className={`tnum ${
                            c.delta_rial > 0 ? "text-loss" : "text-gain"
                          }`}
                        >
                          {c.delta_rial > 0 ? "+" : "−"}
                          {toman(Math.abs(c.delta_rial))}
                          <span className="ms-1 text-[11px] text-text-mute">
                            ({faDigits(Math.round(c.ratio * 10) / 10)}×)
                          </span>
                        </span>
                      )}
                      {c.is_spike && (
                        <span className="ms-2">
                          <Pill tone="amber">جهش</Pill>
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </>
  );
}
