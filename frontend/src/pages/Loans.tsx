import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";

import JalaliDate from "../components/JalaliDate";
import { Bar, Empty, ErrorBox, Loading, PageHeader, Pill } from "../components/ui";
import { api } from "../lib/api";
import { faDigits, jalaliDate, latinDigits, parseTomanInput, percent, toman } from "../lib/format";
import type { Loan } from "../lib/types";

export default function Loans() {
  const qc = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [error, setError] = useState("");
  const [form, setForm] = useState({
    title: "",
    lender: "",
    loan_ref: "",
    installment_count: "",
    installment_amount: "",
    first_due_jalali: "",
    principal: "",
  });

  const loans = useQuery({
    queryKey: ["loans"],
    queryFn: () => api.get<Loan[]>("/api/loans"),
  });

  const create = useMutation({
    mutationFn: (body: unknown) => api.post<Loan>("/api/loans", body),
    onSuccess: () => {
      setShowForm(false);
      setForm({
        title: "", lender: "", loan_ref: "", installment_count: "",
        installment_amount: "", first_due_jalali: "", principal: "",
      });
      setError("");
      qc.invalidateQueries();
    },
    onError: (e: Error) => setError(e.message),
  });

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    const amount = parseTomanInput(form.installment_amount);
    const count = Number(latinDigits(form.installment_count));
    const due = latinDigits(form.first_due_jalali).replace(/-/g, "/");
    if (!form.title.trim() || !amount || !count || !/^\d{4}\/\d{1,2}\/\d{1,2}$/.test(due)) {
      setError("عنوان، تعداد اقساط، مبلغ قسط و تاریخ اولین سررسید (مثل ۱۴۰۴/۰۷/۰۶) لازم است.");
      return;
    }
    create.mutate({
      title: form.title.trim(),
      lender: form.lender.trim() || null,
      loan_ref: form.loan_ref.trim() || null,
      installment_count: count,
      installment_amount_rial: amount,
      first_due_jalali: due,
      principal_rial: parseTomanInput(form.principal),
    });
  };

  const field = (key: keyof typeof form, label: string, placeholder = "", ltr = false) => (
    <div className="min-w-[11rem] flex-1">
      <label className="label">{label}</label>
      <input
        className={`input ${ltr ? "tnum" : ""}`}
        dir={ltr ? "ltr" : undefined}
        value={form[key]}
        placeholder={placeholder}
        onChange={(e) => setForm((f) => ({ ...f, [key]: e.target.value }))}
      />
    </div>
  );

  return (
    <>
      <PageHeader
        title="وام‌ها"
        subtitle="جدول اقساط، ثبت پرداخت و بایگانی رسیدها"
        action={
          <button className="btn-primary" onClick={() => setShowForm((s) => !s)}>
            {showForm ? "بستن" : "ثبت وام جدید"}
          </button>
        }
      />

      {showForm && (
        <form onSubmit={submit} className="card card-pad mb-4">
          <div className="flex flex-wrap gap-3">
            {field("title", "عنوان وام", "وام مسکن")}
            {field("lender", "وام‌دهنده", "بانک سامان")}
            {field("loan_ref", "شمارهٔ تسهیلات", "LN_0000123456", true)}
            {field("installment_count", "تعداد اقساط", "۱۲", true)}
            {field("installment_amount", "مبلغ هر قسط (تومان)", "۲۷۷۹۰۳۵", true)}
            <div className="min-w-[11rem] flex-1">
              <label className="label" htmlFor="first_due_jalali">
                اولین سررسید
              </label>
              <JalaliDate
                id="first_due_jalali"
                value={form.first_due_jalali}
                onChange={(v) => setForm((f) => ({ ...f, first_due_jalali: v }))}
              />
            </div>
            {field("principal", "اصل وام (تومان، اختیاری)", "۳۰۰۰۰۰۰۰۰", true)}
          </div>
          {error && (
            <div className="mt-3">
              <ErrorBox message={error} />
            </div>
          )}
          <button className="btn-primary mt-3" disabled={create.isPending}>
            {create.isPending ? "…" : "ساخت وام و جدول اقساط"}
          </button>
          <p className="mt-2 text-[11px] text-text-mute">
            جدول اقساط خودکار ساخته می‌شود. اگر روز سررسید در ماهی کوتاه‌تر نباشد،
            به آخرین روز همان ماه منتقل می‌شود.
          </p>
        </form>
      )}

      {loans.isLoading ? (
        <Loading />
      ) : !loans.data?.length ? (
        <Empty
          title="هنوز وامی ثبت نشده."
          hint="با ثبت مبلغ قسط، تعداد اقساط و اولین سررسید، جدول کامل ساخته می‌شود."
        />
      ) : (
        <div className="grid gap-3 lg:grid-cols-2">
          {loans.data.map((l) => (
            <Link
              key={l.id}
              to={`/loans/${l.id}`}
              className="card card-pad transition hover:border-brand"
            >
              <div className="flex items-start justify-between gap-2">
                <div>
                  <div className="font-semibold">{l.title}</div>
                  <div className="mt-0.5 text-xs text-text-mute">
                    {l.lender ?? "—"}
                    {l.loan_ref && <span className="font-mono"> · {l.loan_ref}</span>}
                  </div>
                </div>
                {l.status === "settled" ? (
                  <Pill tone="green">تسویه شده</Pill>
                ) : l.overdue_count > 0 ? (
                  <Pill tone="red">{faDigits(l.overdue_count)} قسط معوق</Pill>
                ) : (
                  <Pill tone="brand">جاری</Pill>
                )}
              </div>

              <div className="mt-3">
                <div className="mb-1 flex justify-between text-xs">
                  <span>
                    {faDigits(l.paid_count)} از {faDigits(l.installment_count)} قسط
                  </span>
                  <span className="tnum text-text-mute">{percent(l.progress)}</span>
                </div>
                <Bar ratio={l.progress} />
              </div>

              <div className="mt-3 grid grid-cols-3 gap-2 text-xs">
                <div>
                  <div className="text-text-mute">قسط</div>
                  <div className="font-semibold tnum">
                    {toman(l.installment_amount_rial)}
                  </div>
                </div>
                <div>
                  <div className="text-text-mute">مانده</div>
                  <div className="font-semibold tnum">{toman(l.remaining_rial)}</div>
                </div>
                <div>
                  <div className="text-text-mute">سررسید بعدی</div>
                  <div className="font-semibold tnum">
                    {l.next_due_jalali ? jalaliDate(l.next_due_jalali) : "—"}
                  </div>
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}
    </>
  );
}
