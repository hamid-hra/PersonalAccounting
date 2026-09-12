import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Fragment, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { Check, CheckCheck, X } from "lucide-react";

import { Empty, ErrorBox, Loading, PageHeader, Pill, SuccessBox } from "../components/ui";
import { api } from "../lib/api";
import { faDigits, jalaliDate, toman } from "../lib/format";
import type { Category, IncomeGroup, ReviewGroup } from "../lib/types";

/**
 * صف بررسی.
 *
 * فایل بانک نام فروشگاه را نمی‌دهد — فقط شمارهٔ پایانه. اما پول بسیار
 * نامتوازن پخش شده، پس گروه‌ها بر اساس جمع مبلغ مرتب می‌شوند تا با
 * برچسب‌زدن چند مورد اولِ فهرست، بیشترِ پول دسته‌بندی شود.
 */
export default function Review() {
  const qc = useQueryClient();
  const [params, setParams] = useSearchParams();
  const tab = params.get("tab") === "income" ? "income" : "category";
  const [confirmDismiss, setConfirmDismiss] = useState(false);
  const [open, setOpen] = useState<string | null>(null);
  // پرخرج‌ترین اول، ولی برای رسیدگی به تراکنش‌های تازه ترتیب تاریخ هم لازم است
  const [sort, setSort] = useState<"amount" | "date" | "count">("amount");
  const [order, setOrder] = useState<"asc" | "desc">("desc");
  const [name, setName] = useState("");
  const [categoryId, setCategoryId] = useState<string>("");
  const [error, setError] = useState("");
  const [flash, setFlash] = useState("");

  const groups = useQuery({
    queryKey: ["review-groups", sort, order],
    queryFn: () => api.get<{
      groups: ReviewGroup[];
      pending_transactions: number;
      pending_rial: number;
    }>("/api/review/groups", { limit: 80, sort, order }),
  });

  const categories = useQuery({
    queryKey: ["categories"],
    queryFn: () => api.get<Category[]>("/api/categories"),
  });

  const income = useQuery({
    queryKey: ["income-queue"],
    queryFn: () =>
      api.get<{ groups: IncomeGroup[]; pending_count: number; pending_rial: number }>(
        "/api/review/income",
      ),
  });

  const dismissAll = useMutation({
    mutationFn: () => api.post<{ dismissed: number }>("/api/review/dismiss-all"),
    onSuccess: (res) => {
      setFlash(`${faDigits(res.dismissed)} تراکنش «خوانده» شد. از این به بعد فقط تازه‌ها می‌آیند.`);
      setConfirmDismiss(false);
      qc.invalidateQueries();
    },
    onError: (err: Error) => setError(err.message),
  });

  const decideIncome = useMutation({
    mutationFn: (payload: { is_income: boolean; kind?: string; value?: string }) =>
      api.post<{ updated: number }>("/api/review/income/decide", payload),
    onSuccess: (res) => {
      setFlash(`${faDigits(res.updated)} تراکنش تعیین‌تکلیف شد.`);
      qc.invalidateQueries();
    },
    onError: (err: Error) => setError(err.message),
  });

  const label = useMutation({
    mutationFn: (payload: {
      kind: string;
      value: string;
      contact_name: string;
      category_id: number | null;
    }) => api.post<{ contact_name: string; transactions_updated: number }>(
      "/api/review/label",
      payload,
    ),
    onSuccess: (res) => {
      setFlash(
        `«${res.contact_name}» ثبت شد و ${faDigits(res.transactions_updated)} تراکنش خودکار دسته‌بندی شد.`,
      );
      setOpen(null);
      setName("");
      setCategoryId("");
      setError("");
      qc.invalidateQueries();
    },
    onError: (err: Error) => setError(err.message),
  });

  if (groups.isLoading) return <Loading />;
  const data = groups.data;

  const Tabs = () => (
    <div className="mb-4 flex flex-wrap items-center gap-2">
      <button
        className={tab === "category" ? "btn-primary" : "btn-ghost"}
        onClick={() => setParams({})}
      >
        بدون دسته
        {!!data?.pending_transactions && (
          <span className="chip bg-black/10 text-inherit">{faDigits(data.pending_transactions)}</span>
        )}
      </button>
      <button
        className={tab === "income" ? "btn-primary" : "btn-ghost"}
        onClick={() => setParams({ tab: "income" })}
      >
        درآمد؟
        {!!income.data?.pending_count && (
          <span className="chip bg-black/10 text-inherit">
            {faDigits(income.data.pending_count)}
          </span>
        )}
      </button>
    </div>
  );

  const IncomeTab = () => {
    if (income.isLoading) return <Loading />;
    const q = income.data;
    if (!q || q.groups.length === 0)
      return (
        <Empty
          title="همهٔ واریزی‌ها تعیین‌تکلیف شده‌اند."
          hint="با ورود فایل تازه، واریزی‌های جدید اینجا می‌آیند."
        />
      );
    return (
      <>
        <p className="mb-3 text-sm text-text-mute">
          {faDigits(q.pending_count)} واریزی، جمعاً {toman(q.pending_rial)} تومان.
          هر واریزی درآمد نیست — وام، پس‌گرفتن قرض و پول دیگران هم واریز می‌شوند.
          تا تصمیم نگیری، در هیچ آماری شمرده نمی‌شوند.
        </p>
        <div className="space-y-2">
          {q.groups.map((g) => (
            <div key={`${g.kind}-${g.value}`} className="card card-pad">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="truncate font-medium">{g.label}</div>
                  <div className="mt-0.5 text-xs text-text-mute">
                    {faDigits(g.count)} واریزی · {jalaliDate(g.first_jalali)} تا{" "}
                    {jalaliDate(g.last_jalali)}
                    {g.bank_tx_type && ` · ${g.bank_tx_type}`}
                  </div>
                  {g.sample_note && (
                    <div className="mt-1 text-xs text-brand-text">
                      یادداشت بانکی: «{g.sample_note}»
                    </div>
                  )}
                </div>
                <div className="text-left">
                  <div className="font-bold tnum text-gain">{toman(g.total_rial)}</div>
                  <div className="text-[11px] text-text-mute">تومان</div>
                </div>
              </div>
              <div className="mt-3 flex flex-wrap gap-2">
                <button
                  className="btn-primary !py-1 text-xs"
                  disabled={decideIncome.isPending}
                  onClick={() =>
                    decideIncome.mutate({ is_income: true, kind: g.kind, value: g.value })
                  }
                >
                  <Check size={14} aria-hidden />
                  درآمد است
                </button>
                <button
                  className="btn-ghost !py-1 text-xs"
                  disabled={decideIncome.isPending}
                  onClick={() =>
                    decideIncome.mutate({ is_income: false, kind: g.kind, value: g.value })
                  }
                >
                  <X size={14} aria-hidden />
                  درآمد نیست
                </button>
              </div>
            </div>
          ))}
        </div>
      </>
    );
  };


  if (tab === "income") {
    return (
      <>
        <PageHeader
          title="صف بررسی"
          subtitle="واریزی‌هایی که باید خودت مشخص کنی درآمد هستند یا نه"
        />
        <Tabs />
        {flash && <div className="mb-3"><SuccessBox message={flash} /></div>}
        {error && <div className="mb-3"><ErrorBox message={error} /></div>}
        <IncomeTab />
      </>
    );
  }

  if (!data || data.groups.length === 0) {
    return (
      <>
        <PageHeader title="صف بررسی" />
        <Tabs />
        <Empty
          title="همه‌چیز دسته‌بندی شده است."
          hint="تراکنش بدون دسته‌ای باقی نمانده. با ورود فایل جدید، موارد تازه اینجا می‌آیند."
        />
      </>
    );
  }

  const expenseCats = (categories.data ?? []).filter(
    (c) => c.kind === "expense" || c.kind === "fee" || c.kind === "loan",
  );
  const incomeCats = (categories.data ?? []).filter((c) => c.kind !== "expense" && c.kind !== "fee" && c.kind !== "loan");

  return (
    <>
      <PageHeader
        title="صف بررسی"
        subtitle={`${faDigits(data.pending_transactions)} تراکنش بدون دسته، جمعاً ${toman(data.pending_rial)} تومان — پرخرج‌ترین‌ها اول`}
        action={
          confirmDismiss ? (
            <div className="flex items-center gap-2">
              <span className="text-xs text-text-mute">مطمئنی؟</span>
              <button
                className="btn-danger !py-1 text-xs"
                disabled={dismissAll.isPending}
                onClick={() => dismissAll.mutate()}
              >
                بله، همه را خوانده کن
              </button>
              <button className="btn-ghost !py-1 text-xs" onClick={() => setConfirmDismiss(false)}>
                انصراف
              </button>
            </div>
          ) : (
            <button className="btn-ghost" onClick={() => setConfirmDismiss(true)}>
              <CheckCheck size={15} aria-hidden />
              خواندن همه
            </button>
          )
        }
      />
      <Tabs />
      {confirmDismiss && (
        <div className="mb-3 rounded-lg border border-warn/30 bg-warn-soft px-3.5 py-2.5 text-xs text-warn">
          هر {faDigits(data.pending_transactions)} تراکنش از صف بیرون می‌رود. چیزی حذف
          نمی‌شود — دسته‌شان «بدون دسته» می‌ماند و از صفحهٔ تراکنش‌ها همچنان پیدایشان
          می‌کنی. از این به بعد فقط تراکنش‌های فایل‌های تازه در صف می‌آیند.
        </div>
      )}

      {flash && (
        <div className="mb-3 rounded-lg border border-gain/30 bg-gain-soft px-3.5 py-2.5 text-sm text-gain">
          {flash}
        </div>
      )}

      <div className="card scroll-x">
        <table className="w-full min-w-[56rem]">
          <thead className="border-b border-border bg-surface-raised">
            <tr>
              <th className="th">شناسه</th>
              <th className="th">نام حدسی / نوع</th>
              <th className="th">تعداد</th>
              <th className="th">جمع (تومان)</th>
              <th className="th">بازه</th>
              <th className="th"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {data.groups.map((g) => {
              const key = `${g.kind}:${g.value}`;
              const isOpen = open === key;
              return (
                <Fragment key={key}>
                  <tr className={isOpen ? "bg-brand-soft/40" : ""}>
                    <td className="td">
                      <div className="text-[11px] text-text-mute">{g.kind_label}</div>
                      <div className="font-mono text-xs" dir="ltr">
                        {g.value}
                      </div>
                    </td>
                    <td className="td max-w-[18rem]">
                      <div className="truncate text-sm">
                        {g.suggested_name || (
                          <span className="text-text-mute">{g.bank_tx_type}</span>
                        )}
                      </div>
                      <div className="mt-0.5 truncate text-[11px] text-text-mute">
                        {g.sample}
                      </div>
                    </td>
                    <td className="td tnum">{faDigits(g.count)}</td>
                    <td className="td font-semibold tnum">{toman(g.total_rial)}</td>
                    <td className="td whitespace-nowrap text-[11px] tnum text-text-mute">
                      {jalaliDate(g.first_seen)}
                      <br />
                      {jalaliDate(g.last_seen)}
                    </td>
                    <td className="td">
                      {g.labelable ? (
                        <button
                          className="btn-ghost !py-1 text-xs"
                          onClick={() => {
                            setOpen(isOpen ? null : key);
                            setName(g.suggested_name ?? "");
                            setCategoryId("");
                            setError("");
                          }}
                        >
                          {isOpen ? "بستن" : "برچسب بزن"}
                        </button>
                      ) : (
                        <Pill tone="slate">بدون شناسه</Pill>
                      )}
                    </td>
                  </tr>

                  {isOpen && (
                    <tr className="bg-brand-soft/40">
                      <td className="td" colSpan={6}>
                        <form
                          className="flex flex-wrap items-end gap-3"
                          onSubmit={(e) => {
                            e.preventDefault();
                            label.mutate({
                              kind: g.kind,
                              value: g.value,
                              contact_name: name.trim(),
                              category_id: categoryId ? Number(categoryId) : null,
                            });
                          }}
                        >
                          <div className="min-w-[14rem] flex-1">
                            <label className="label">این پرداخت به کیست؟</label>
                            <input
                              className="input"
                              value={name}
                              onChange={(e) => setName(e.target.value)}
                              placeholder="مثلاً: دیجی‌کالا، تاکسی اسنپ، سوپرمارکت محله"
                              autoFocus
                            />
                          </div>
                          <div className="min-w-[12rem] flex-1">
                            <label className="label">دسته</label>
                            <select
                              className="input"
                              value={categoryId}
                              onChange={(e) => setCategoryId(e.target.value)}
                            >
                              <option value="">— انتخاب کن —</option>
                              <optgroup label="هزینه">
                                {expenseCats.map((c) => (
                                  <option key={c.id} value={c.id}>
                                    {c.parent_id ? "└ " : ""}
                                    {c.name_fa}
                                  </option>
                                ))}
                              </optgroup>
                              <optgroup label="درآمد و انتقال">
                                {incomeCats.map((c) => (
                                  <option key={c.id} value={c.id}>
                                    {c.name_fa}
                                  </option>
                                ))}
                              </optgroup>
                            </select>
                          </div>
                          <button
                            type="submit"
                            className="btn-primary"
                            disabled={!name.trim() || label.isPending}
                          >
                            {label.isPending ? "…" : "ذخیره و اعمال بر همه"}
                          </button>
                        </form>
                        <p className="mt-2 text-[11px] text-text-mute">
                          با ذخیره، هر {faDigits(g.count)} تراکنش این شناسه — و هر
                          تراکنش آیندهٔ آن — خودکار همین دسته را می‌گیرد.
                        </p>
                        <div className="mb-3 flex flex-wrap items-center gap-2">
        <span className="text-xs text-text-mute">مرتب‌سازی:</span>
        {(
          [
            ["amount", "مبلغ"],
            ["date", "تاریخ"],
            ["count", "تعداد"],
          ] as const
        ).map(([key, label]) => (
          <button
            key={key}
            onClick={() => setSort(key)}
            aria-pressed={sort === key}
            className={`rounded-md px-2.5 py-1 text-xs transition-colors ${
              sort === key
                ? "bg-brand text-brand-fg"
                : "bg-surface-raised text-text-soft hover:text-text"
            }`}
          >
            {label}
          </button>
        ))}
        <button
          onClick={() => setOrder((o) => (o === "desc" ? "asc" : "desc"))}
          className="btn-ghost !py-1 text-xs"
          aria-label="تغییر جهت مرتب‌سازی"
        >
          {order === "desc" ? "نزولی ↓" : "صعودی ↑"}
        </button>
      </div>

      {error && (
                          <div className="mt-2">
                            <ErrorBox message={error} />
                          </div>
                        )}
                      </td>
                    </tr>
                  )}
                </Fragment>
              );
            })}
          </tbody>
        </table>
      </div>
    </>
  );
}
