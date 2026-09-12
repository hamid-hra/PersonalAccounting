import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { Empty, Loading, PageHeader, Pill } from "../components/ui";
import { api } from "../lib/api";
import { faDigits, jalaliDate, jalaliTime, latinDigits, toman } from "../lib/format";
import type { Category, Transaction, TxPage } from "../lib/types";

const EMPTY_FILTERS = {
  q: "",
  category_id: "",
  direction: "",
  from_jalali: "",
  to_jalali: "",
  bank_tx_type: "",
  needs_review: "",
  include_self: "true",
};

export default function Transactions() {
  const qc = useQueryClient();
  const [filters, setFilters] = useState({ ...EMPTY_FILTERS });
  const [page, setPage] = useState(1);
  const [editing, setEditing] = useState<number | null>(null);

  const set = (key: keyof typeof EMPTY_FILTERS, value: string) => {
    setFilters((f) => ({ ...f, [key]: value }));
    setPage(1);
  };

  const { data, isLoading } = useQuery({
    queryKey: ["transactions", filters, page],
    queryFn: () =>
      api.get<TxPage>("/api/transactions", {
        ...filters,
        from_jalali: latinDigits(filters.from_jalali),
        to_jalali: latinDigits(filters.to_jalali),
        page,
        page_size: 50,
      }),
  });

  const categories = useQuery({
    queryKey: ["categories"],
    queryFn: () => api.get<Category[]>("/api/categories"),
  });
  const types = useQuery({
    queryKey: ["bank-types"],
    queryFn: () => api.get<{ type: string; count: number }[]>("/api/transactions/bank-types"),
  });

  const patch = useMutation({
    mutationFn: ({ id, body }: { id: number; body: Record<string, unknown> }) =>
      api.patch<Transaction>(`/api/transactions/${id}`, body),
    onSuccess: () => {
      setEditing(null);
      qc.invalidateQueries();
    },
  });

  const pages = data ? Math.ceil(data.total / data.page_size) : 1;

  return (
    <>
      <PageHeader
        title="تراکنش‌ها"
        subtitle={
          data
            ? `${faDigits(data.total)} تراکنش — ورودی ${toman(data.sum_in_rial)} / خروجی ${toman(data.sum_out_rial)} تومان`
            : undefined
        }
      />

      <div className="card card-pad mb-4">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <div>
            <label className="label">جست‌وجو در شرح</label>
            <input
              className="input"
              value={filters.q}
              onChange={(e) => set("q", e.target.value)}
              placeholder="نام، شمارهٔ پایانه، متن سند…"
            />
          </div>
          <div>
            <label className="label">دسته</label>
            <select
              className="input"
              value={filters.category_id}
              onChange={(e) => set("category_id", e.target.value)}
            >
              <option value="">همه</option>
              {(categories.data ?? []).map((c) => (
                <option key={c.id} value={c.id}>
                  {c.parent_id ? "└ " : ""}
                  {c.name_fa}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="label">نوع تراکنش بانک</label>
            <select
              className="input"
              value={filters.bank_tx_type}
              onChange={(e) => set("bank_tx_type", e.target.value)}
            >
              <option value="">همه</option>
              {(types.data ?? []).map((t) => (
                <option key={t.type} value={t.type}>
                  {t.type} ({faDigits(t.count)})
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="label">جهت</label>
            <select
              className="input"
              value={filters.direction}
              onChange={(e) => set("direction", e.target.value)}
            >
              <option value="">همه</option>
              <option value="out">برداشت</option>
              <option value="in">واریز</option>
            </select>
          </div>
          <div>
            <label className="label">از تاریخ</label>
            <input
              className="input tnum"
              value={filters.from_jalali}
              onChange={(e) => set("from_jalali", e.target.value)}
              placeholder="۱۴۰۵/۰۱/۰۱"
              dir="ltr"
            />
          </div>
          <div>
            <label className="label">تا تاریخ</label>
            <input
              className="input tnum"
              value={filters.to_jalali}
              onChange={(e) => set("to_jalali", e.target.value)}
              placeholder="۱۴۰۵/۰۶/۳۱"
              dir="ltr"
            />
          </div>
          <div>
            <label className="label">وضعیت</label>
            <select
              className="input"
              value={filters.needs_review}
              onChange={(e) => set("needs_review", e.target.value)}
            >
              <option value="">همه</option>
              <option value="true">بدون دسته</option>
              <option value="false">دسته‌بندی‌شده</option>
            </select>
          </div>
          <div>
            <label className="label">انتقال بین حساب‌های خودم</label>
            <select
              className="input"
              value={filters.include_self}
              onChange={(e) => set("include_self", e.target.value)}
            >
              <option value="true">نمایش داده شود</option>
              <option value="false">پنهان شود</option>
            </select>
          </div>
        </div>
        <button
          className="btn-ghost mt-3 text-xs"
          onClick={() => {
            setFilters({ ...EMPTY_FILTERS });
            setPage(1);
          }}
        >
          پاک کردن فیلترها
        </button>
      </div>

      {isLoading ? (
        <Loading />
      ) : !data?.items.length ? (
        <Empty title="تراکنشی با این فیلترها پیدا نشد." />
      ) : (
        <>
          <div className="card scroll-x">
            <table className="w-full min-w-[60rem]">
              <thead className="border-b border-border bg-surface-raised">
                <tr>
                  <th className="th">تاریخ</th>
                  <th className="th">شرح</th>
                  <th className="th">دسته</th>
                  <th className="th">مبلغ (تومان)</th>
                  <th className="th">مانده</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {data.items.map((t) => (
                  <tr key={t.id} className={t.is_self_transfer ? "bg-surface-raised/70" : ""}>
                    <td className="td whitespace-nowrap tnum text-xs">
                      {jalaliDate(t.jalali_datetime)}
                      <div className="text-text-mute">{jalaliTime(t.jalali_datetime)}</div>
                    </td>
                    <td className="td max-w-[26rem]">
                      <div className="flex flex-wrap items-center gap-1.5">
                        <span className="font-medium">
                          {t.contact_name ?? t.counterparty_name ?? t.bank_tx_type}
                        </span>
                        {t.is_self_transfer && <Pill tone="slate">انتقال به خودم</Pill>}
                        {t.needs_review && <Pill tone="amber">بدون دسته</Pill>}
                      </div>
                      <div className="mt-0.5 line-clamp-2 text-[11px] text-text-mute">
                        {t.description_raw}
                      </div>
                    </td>
                    <td className="td">
                      {editing === t.id ? (
                        <select
                          className="input !py-1 text-xs"
                          autoFocus
                          defaultValue={t.category_id ?? ""}
                          onBlur={() => setEditing(null)}
                          onChange={(e) =>
                            patch.mutate({
                              id: t.id,
                              body: { category_id: Number(e.target.value) },
                            })
                          }
                        >
                          {(categories.data ?? []).map((c) => (
                            <option key={c.id} value={c.id}>
                              {c.parent_id ? "└ " : ""}
                              {c.name_fa}
                            </option>
                          ))}
                        </select>
                      ) : (
                        <button
                          className="chip hover:ring-1 hover:ring-border-strong"
                          style={{
                            background: `${t.category_color ?? "#9ca3af"}1a`,
                            color: t.category_color ?? "#6b7280",
                          }}
                          onClick={() => setEditing(t.id)}
                        >
                          {t.category_name ?? "بدون دسته"}
                        </button>
                      )}
                    </td>
                    <td
                      className={`td whitespace-nowrap font-semibold tnum ${
                        t.direction === "in" ? "text-gain" : "text-loss"
                      }`}
                    >
                      {t.direction === "in" ? "+" : "−"}
                      {toman(Math.abs(t.amount_rial))}
                    </td>
                    <td className="td whitespace-nowrap text-xs tnum text-text-mute">
                      {t.balance_after_rial !== null ? toman(t.balance_after_rial) : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {pages > 1 && (
            <div className="mt-4 flex items-center justify-center gap-2">
              <button
                className="btn-ghost"
                disabled={page <= 1}
                onClick={() => setPage((p) => p - 1)}
              >
                قبلی
              </button>
              <span className="text-sm tnum text-text-mute">
                صفحهٔ {faDigits(page)} از {faDigits(pages)}
              </span>
              <button
                className="btn-ghost"
                disabled={page >= pages}
                onClick={() => setPage((p) => p + 1)}
              >
                بعدی
              </button>
            </div>
          )}
        </>
      )}
    </>
  );
}
