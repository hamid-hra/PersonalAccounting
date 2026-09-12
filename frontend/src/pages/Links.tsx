import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Check, RefreshCw, X } from "lucide-react";
import { useState } from "react";

import { Empty, ErrorBox, Loading, PageHeader, Pill, SuccessBox } from "../components/ui";
import { api } from "../lib/api";
import { faDigits, jalaliDate, toman } from "../lib/format";
import type { TxLink, LinkSummary } from "../lib/types";

const KINDS = [
  { key: "cross_account", label: "انتقال بین حساب‌های خودم" },
  { key: "reversal", label: "حوالهٔ برگشتی" },
  { key: "fee", label: "کارمزد" },
] as const;

/**
 * پیوند تراکنش‌ها.
 *
 * اینجا جایی است که «یک جابه‌جایی که دو بار شمرده می‌شد» و «حواله‌ای که
 * برگشت خورد ولی هم درآمد هم هزینه حساب می‌شد» درست می‌شوند.
 */
function TxSide({ tx }: { tx: TxLink["primary"] }) {
  const amount = tx?.amount_rial ?? 0;
  return (
    <div className="rounded-lg bg-surface-raised p-2.5">
      <div className="flex items-center justify-between gap-2 text-xs">
        <span className="truncate font-medium">{tx?.account_title}</span>
        <span
          className={`shrink-0 tnum font-semibold ${amount > 0 ? "text-gain" : "text-loss"}`}
        >
          {amount > 0 ? "+" : "−"}
          {toman(Math.abs(amount))}
        </span>
      </div>
      <div className="mt-1 text-[11px] tnum text-text-mute">
        {jalaliDate(tx?.jalali_datetime)} · {tx?.bank_tx_type}
      </div>
    </div>
  );
}

export default function Links() {
  const qc = useQueryClient();
  const [kind, setKind] = useState<string>("cross_account");
  const [onlyUnconfirmed, setOnlyUnconfirmed] = useState(false);
  const [flash, setFlash] = useState("");
  const [error, setError] = useState("");

  const summary = useQuery({
    queryKey: ["link-summary"],
    queryFn: () => api.get<LinkSummary>("/api/links/summary"),
  });
  const links = useQuery({
    queryKey: ["links", kind, onlyUnconfirmed],
    queryFn: () =>
      api.get<TxLink[]>("/api/links", { kind, only_unconfirmed: onlyUnconfirmed, limit: 200 }),
  });

  const detect = useMutation({
    mutationFn: () => api.post<{ created: Record<string, number> }>("/api/links/detect"),
    onSuccess: (r) => {
      const total = Object.values(r.created).reduce((a, b) => a + b, 0);
      setFlash(
        total ? `${faDigits(total)} پیوند تازه پیدا شد.` : "پیوند تازه‌ای پیدا نشد.",
      );
      qc.invalidateQueries();
    },
    onError: (e: Error) => setError(e.message),
  });

  const act = useMutation({
    mutationFn: ({ id, what }: { id: number; what: "confirm" | "reject" }) =>
      api.post(`/api/links/${id}/${what}`),
    onSuccess: () => qc.invalidateQueries(),
    onError: (e: Error) => setError(e.message),
  });

  return (
    <>
      <PageHeader
        title="انتقال بین‌بانکی و برگشتی"
        subtitle="تراکنش‌هایی که دو بار شمرده می‌شدند — اینجا یک‌بار حساب می‌شوند"
        action={
          <button
            className="btn-primary"
            onClick={() => detect.mutate()}
            disabled={detect.isPending}
          >
            <RefreshCw size={15} className={detect.isPending ? "animate-spin" : ""} aria-hidden />
            کشف دوباره
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

      <div className="mb-4 grid grid-cols-1 gap-3 sm:grid-cols-3">
        {KINDS.map(({ key, label }) => {
          const s = summary.data?.[key];
          return (
            <button
              key={key}
              onClick={() => setKind(key)}
              className={`card card-pad text-right transition ${
                kind === key ? "ring-2 ring-brand" : "hover:border-border-strong"
              }`}
            >
              <div className="text-xs text-text-mute">{label}</div>
              <div className="mt-1 text-lg font-bold tnum">
                {faDigits(s?.count ?? 0)}
                <span className="ms-1 text-xs font-normal text-text-mute">جفت</span>
              </div>
              <div className="mt-0.5 text-[11px] tnum text-text-mute">
                {toman(s?.total_rial ?? 0)} تومان
              </div>
            </button>
          );
        })}
      </div>

      <label className="mb-3 flex items-center gap-2 text-xs text-text-soft">
        <input
          type="checkbox"
          checked={onlyUnconfirmed}
          onChange={(e) => setOnlyUnconfirmed(e.target.checked)}
        />
        فقط تأییدنشده‌ها
      </label>

      {links.isLoading ? (
        <Loading />
      ) : !links.data?.length ? (
        <Empty title="پیوندی در این دسته نیست." />
      ) : (
        <div className="space-y-2">
          {links.data.map((l) => (
            <div key={l.id} className="card card-pad">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <span className="text-base font-bold tnum">{toman(l.amount_rial)}</span>
                  <span className="text-xs text-text-mute">تومان</span>
                  <Pill tone={l.confidence >= 0.9 ? "green" : l.confidence >= 0.7 ? "brand" : "amber"}>
                    اطمینان {faDigits(Math.round(l.confidence * 100))}٪
                  </Pill>
                  {l.confidence < 0.7 && !l.is_confirmed && (
                    <Pill tone="amber">اعمال نشده</Pill>
                  )}
                  {l.is_confirmed && <Pill tone="green">تأییدشده</Pill>}
                </div>
                <div className="flex gap-1">
                  {!l.is_confirmed && (
                    <button
                      className="btn-ghost !py-1 text-xs"
                      onClick={() => act.mutate({ id: l.id, what: "confirm" })}
                    >
                      <Check size={14} aria-hidden />
                      درست است
                    </button>
                  )}
                  <button
                    className="btn-danger !py-1 text-xs"
                    onClick={() => act.mutate({ id: l.id, what: "reject" })}
                  >
                    <X size={14} aria-hidden />
                    ربطی ندارند
                  </button>
                </div>
              </div>

              <div className="mt-2 text-[11px] text-text-mute">
                {l.matched_by} · فاصله {faDigits(l.seconds_apart)} ثانیه
              </div>

              <div className="mt-2 grid gap-2 sm:grid-cols-[1fr_auto_1fr] sm:items-center">
                <TxSide tx={l.primary} />
                <ArrowLeft
                  size={16}
                  className="mx-auto hidden shrink-0 text-text-mute sm:block"
                  aria-hidden
                />
                <TxSide tx={l.secondary} />
              </div>
            </div>
          ))}
        </div>
      )}
    </>
  );
}
