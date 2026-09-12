import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowDownLeft, ArrowUpRight, Plus, Trash2 } from "lucide-react";
import { useState } from "react";

import JalaliDate from "../components/JalaliDate";
import { Bar, Empty, ErrorBox, Loading, PageHeader, Pill } from "../components/ui";
import { api } from "../lib/api";
import { faDigits, jalaliDate, latinDigits, parseTomanInput, percent, toman } from "../lib/format";
import type { Account, Debt, DebtSuggestion, DebtSummary } from "../lib/types";

const EMPTY = {
  person_name: "",
  direction: "i_borrowed",
  principal: "",
  opened_jalali: "",
  due_jalali: "",
  source: "cash",   // «cash» یا شناسهٔ حساب
  note: "",
};

export default function Debts() {
  const qc = useQueryClient();
  const [form, setForm] = useState({ ...EMPTY });
  const [showForm, setShowForm] = useState(false);
  const [error, setError] = useState("");
  const [openId, setOpenId] = useState<number | null>(null);
  const [repay, setRepay] = useState("");

  const debts = useQuery({ queryKey: ["debts"], queryFn: () => api.get<Debt[]>("/api/debts") });
  const summary = useQuery({
    queryKey: ["debt-summary"],
    queryFn: () => api.get<DebtSummary>("/api/debts/summary"),
  });
  const accounts = useQuery({
    queryKey: ["accounts"],
    queryFn: () => api.get<Account[]>("/api/accounts"),
  });
  const suggestions = useQuery({
    queryKey: ["debt-suggest", openId],
    queryFn: () => api.get<DebtSuggestion[]>(`/api/debts/${openId}/suggest-transactions`),
    enabled: openId !== null,
  });
  const detail = useQuery({
    queryKey: ["debt", openId],
    queryFn: () => api.get<Debt>(`/api/debts/${openId}`),
    enabled: openId !== null,
  });

  const create = useMutation({
    mutationFn: (body: unknown) => api.post("/api/debts", body),
    onSuccess: () => {
      setForm({ ...EMPTY });
      setShowForm(false);
      setError("");
      qc.invalidateQueries();
    },
    onError: (e: Error) => setError(e.message),
  });
  const addEntry = useMutation({
    mutationFn: ({ id, amount }: { id: number; amount: number }) =>
      api.post(`/api/debts/${id}/entries`, { amount_rial: amount }),
    onSuccess: () => {
      setRepay("");
      qc.invalidateQueries();
    },
    onError: (e: Error) => setError(e.message),
  });
  const linkTx = useMutation({
    mutationFn: ({ id, tx, amount }: { id: number; tx: number; amount: number }) =>
      api.post(`/api/debts/${id}/entries`, {
        amount_rial: amount,
        transaction_id: tx,
        kind: "principal",
      }),
    onSuccess: () => qc.invalidateQueries(),
    onError: (e: Error) => setError(e.message),
  });
  const remove = useMutation({
    mutationFn: (id: number) => api.del(`/api/debts/${id}`),
    onSuccess: () => {
      setOpenId(null);
      qc.invalidateQueries();
    },
  });

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    const principal = parseTomanInput(form.principal);
    const opened = latinDigits(form.opened_jalali).replace(/-/g, "/");
    if (!form.person_name.trim() || !principal || !/^\d{4}\/\d{1,2}\/\d{1,2}$/.test(opened)) {
      setError("نام، مبلغ و تاریخ (مثل ۱۴۰۵/۰۱/۱۰) لازم است.");
      return;
    }
    const isCash = form.source === "cash";
    create.mutate({
      person_name: form.person_name.trim(),
      direction: form.direction,
      principal_rial: principal,
      opened_jalali: opened,
      due_jalali: latinDigits(form.due_jalali).replace(/-/g, "/") || null,
      is_cash: isCash,
      account_id: isCash ? null : Number(form.source),
      note: form.note || null,
    });
  };

  const s = summary.data;

  return (
    <>
      <PageHeader
        title="قرض‌ها"
        subtitle="پولی که به کسی داده‌ای یا از کسی گرفته‌ای — جدا از وام بانکی"
        action={
          <button className="btn-primary" onClick={() => setShowForm((v) => !v)}>
            <Plus size={15} aria-hidden />
            {showForm ? "بستن" : "ثبت قرض"}
          </button>
        }
      />

      {s && (
        <div className="mb-4 grid grid-cols-1 gap-3 sm:grid-cols-3">
          <div className="card card-pad">
            <div className="flex items-center gap-2 text-xs text-text-mute">
              <ArrowDownLeft size={14} className="text-gain" aria-hidden />
              طلبکارم
            </div>
            <div className="mt-1.5 text-xl font-bold tnum text-gain">
              {toman(s.i_am_owed_rial)}
              <span className="ms-1 text-xs font-normal text-text-mute">تومان</span>
            </div>
            <div className="mt-1 text-[11px] text-text-mute">
              {faDigits(s.lent_count)} مورد باز
            </div>
          </div>
          <div className="card card-pad">
            <div className="flex items-center gap-2 text-xs text-text-mute">
              <ArrowUpRight size={14} className="text-loss" aria-hidden />
              بدهکارم
            </div>
            <div className="mt-1.5 text-xl font-bold tnum text-loss">
              {toman(s.i_owe_rial)}
              <span className="ms-1 text-xs font-normal text-text-mute">تومان</span>
            </div>
            <div className="mt-1 text-[11px] text-text-mute">
              {faDigits(s.borrowed_count)} مورد باز
            </div>
          </div>
          <div className="card card-pad">
            <div className="text-xs text-text-mute">خالص</div>
            <div
              className={`mt-1.5 text-xl font-bold tnum ${s.net_rial >= 0 ? "text-gain" : "text-loss"}`}
            >
              {s.net_rial >= 0 ? "+" : "−"}
              {toman(Math.abs(s.net_rial))}
              <span className="ms-1 text-xs font-normal text-text-mute">تومان</span>
            </div>
          </div>
        </div>
      )}

      {showForm && (
        <form onSubmit={submit} className="card card-pad mb-4">
          <div className="flex flex-wrap gap-3">
            <div className="min-w-[10rem]">
              <label className="label" htmlFor="dir">
                جهت
              </label>
              <select
                id="dir"
                className="input"
                value={form.direction}
                onChange={(e) => setForm((f) => ({ ...f, direction: e.target.value }))}
              >
                <option value="i_borrowed">از کسی قرض گرفتم</option>
                <option value="i_lent">به کسی قرض دادم</option>
              </select>
            </div>
            {[
              ["person_name", "طرف حساب", "نام شخص", false],
              ["principal", "مبلغ (تومان)", "۵۰۰۰۰۰۰", true],
            ].map(([key, label, ph, ltr]) => (
              <div className="min-w-[11rem] flex-1" key={key as string}>
                <label className="label" htmlFor={key as string}>
                  {label as string}
                </label>
                <input
                  id={key as string}
                  className={`input ${ltr ? "tnum" : ""}`}
                  dir={ltr ? "ltr" : undefined}
                  placeholder={ph as string}
                  value={form[key as keyof typeof form]}
                  onChange={(e) => setForm((f) => ({ ...f, [key as string]: e.target.value }))}
                />
              </div>
            ))}
            <div className="min-w-[11rem] flex-1">
              <label className="label" htmlFor="opened_jalali">
                تاریخ
              </label>
              <JalaliDate
                id="opened_jalali"
                value={form.opened_jalali}
                onChange={(v) => setForm((f) => ({ ...f, opened_jalali: v }))}
              />
            </div>
            <div className="min-w-[11rem] flex-1">
              <label className="label" htmlFor="due_jalali">
                سررسید (اختیاری)
              </label>
              <JalaliDate
                id="due_jalali"
                value={form.due_jalali}
                onChange={(v) => setForm((f) => ({ ...f, due_jalali: v }))}
              />
            </div>
            <div className="min-w-[12rem] flex-1">
              <label className="label" htmlFor="src">
                پول از کجا رد و بدل شد؟
              </label>
              <select
                id="src"
                className="input"
                value={form.source}
                onChange={(e) => setForm((f) => ({ ...f, source: e.target.value }))}
              >
                <option value="cash">نقدی</option>
                {(accounts.data ?? []).map((a) => (
                  <option key={a.id} value={String(a.id)}>
                    {a.title}
                  </option>
                ))}
              </select>
            </div>
          </div>
          {error && (
            <div className="mt-3">
              <ErrorBox message={error} />
            </div>
          )}
          <button className="btn-primary mt-3" disabled={create.isPending}>
            ثبت
          </button>
        </form>
      )}

      {debts.isLoading ? (
        <Loading />
      ) : !debts.data?.length ? (
        <Empty
          title="هنوز قرضی ثبت نشده."
          hint="از صفحهٔ تراکنش‌ها هم می‌توانی یک تراکنش را «قرض» علامت بزنی تا خودکار اینجا بیاید."
        />
      ) : (
        <div className="grid gap-3 lg:grid-cols-2">
          {debts.data.map((d) => (
            <div key={d.id} className="card card-pad">
              <div className="flex items-start justify-between gap-2">
                <div>
                  <div className="font-semibold">{d.person_name}</div>
                  <div className="mt-0.5 text-xs text-text-mute">
                    {jalaliDate(d.opened_jalali)}
                    {d.due_jalali && ` · سررسید ${jalaliDate(d.due_jalali)}`}
                  </div>
                </div>
                <Pill tone={d.direction === "i_lent" ? "green" : "amber"}>
                  {d.direction_label}
                </Pill>
              </div>

              <div className="mt-3">
                <div className="mb-1 flex justify-between text-xs">
                  <span className="text-text-mute">
                    {toman(d.repaid_rial)} از {toman(d.principal_rial)} تومان
                  </span>
                  <span className="tnum text-text-mute">{percent(d.progress)}</span>
                </div>
                <Bar ratio={d.progress} />
              </div>

              <div className="mt-3 flex items-center justify-between">
                <div>
                  <div className="text-[11px] text-text-mute">مانده</div>
                  <div
                    className={`font-bold tnum ${d.outstanding_rial > 0 ? "text-loss" : "text-gain"}`}
                  >
                    {toman(d.outstanding_rial)} تومان
                  </div>
                </div>
                <div className="flex gap-2">
                  <button
                    className="btn-ghost !py-1 text-xs"
                    onClick={() => setOpenId(openId === d.id ? null : d.id)}
                  >
                    {openId === d.id ? "بستن" : "جزئیات"}
                  </button>
                  <button
                    className="btn-icon text-loss"
                    aria-label={`حذف قرض ${d.person_name}`}
                    onClick={() => remove.mutate(d.id)}
                  >
                    <Trash2 size={15} aria-hidden />
                  </button>
                </div>
              </div>

              {openId === d.id && (
                <div className="mt-3 border-t border-border pt-3">
                  <form
                    className="flex flex-wrap items-end gap-2"
                    onSubmit={(e) => {
                      e.preventDefault();
                      const amount = parseTomanInput(repay);
                      if (amount) addEntry.mutate({ id: d.id, amount });
                    }}
                  >
                    <div className="min-w-[10rem] flex-1">
                      <label className="label" htmlFor={`r-${d.id}`}>
                        ثبت بازپرداخت (تومان)
                      </label>
                      <input
                        id={`r-${d.id}`}
                        className="input tnum"
                        dir="ltr"
                        value={repay}
                        onChange={(e) => setRepay(e.target.value)}
                      />
                    </div>
                    <button className="btn-primary" disabled={addEntry.isPending}>
                      ثبت
                    </button>
                  </form>

                  {!d.is_cash && (suggestions.data ?? []).length > 0 && (
                    <div className="mt-3">
                      <p className="mb-1.5 text-[11px] text-text-mute">
                        کدام تراکنش این قرض بود؟ وصل‌کردنش جلوی دوباره‌شمردن را می‌گیرد.
                      </p>
                      <div className="flex flex-wrap gap-1.5">
                        {(suggestions.data ?? []).slice(0, 6).map((s) => (
                          <button
                            key={s.id}
                            className="btn-ghost !py-1 text-[11px]"
                            title={s.description}
                            onClick={() =>
                              linkTx.mutate({ id: d.id, tx: s.id, amount: Math.abs(s.amount_rial) })
                            }
                          >
                            <span className="tnum">{toman(Math.abs(s.amount_rial))}</span>
                            <span className="text-text-mute">{s.jalali_datetime.slice(0, 10)}</span>
                            {s.exact_match && <span className="text-gain">✓</span>}
                          </button>
                        ))}
                      </div>
                    </div>
                  )}

                  <div className="mt-3 space-y-1">
                    {(detail.data?.entries ?? []).map((e) => (
                      <div key={e.id} className="flex justify-between text-xs">
                        <span className="text-text-mute">
                          {e.kind_label} · {jalaliDate(e.entry_jalali)}
                        </span>
                        <span className="tnum">{toman(e.amount_rial)} تومان</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </>
  );
}
