import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { Bar, Empty, ErrorBox, Loading, PageHeader, Pill } from "../components/ui";
import { api } from "../lib/api";
import { faDigits, parseTomanInput, percent, toman } from "../lib/format";
import type { BudgetStatus, Category, Summary } from "../lib/types";

export default function Budgets() {
  const qc = useQueryClient();
  const [categoryId, setCategoryId] = useState("");
  const [amount, setAmount] = useState("");
  const [error, setError] = useState("");

  const summary = useQuery({
    queryKey: ["summary"],
    queryFn: () => api.get<Summary>("/api/analytics/summary"),
  });
  const status = useQuery({
    queryKey: ["budget-status"],
    queryFn: () => api.get<BudgetStatus[]>("/api/budgets/status"),
  });
  const categories = useQuery({
    queryKey: ["categories"],
    queryFn: () => api.get<Category[]>("/api/categories"),
  });

  const save = useMutation({
    mutationFn: (body: { category_id: number; amount_rial: number }) =>
      api.post("/api/budgets", body),
    onSuccess: () => {
      setAmount("");
      setCategoryId("");
      setError("");
      qc.invalidateQueries();
    },
    onError: (e: Error) => setError(e.message),
  });

  const remove = useMutation({
    mutationFn: (id: number) => api.del(`/api/budgets/${id}`),
    onSuccess: () => qc.invalidateQueries(),
  });

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    const rial = parseTomanInput(amount);
    if (!categoryId || rial === null) {
      setError("دسته و مبلغ را درست وارد کن.");
      return;
    }
    save.mutate({ category_id: Number(categoryId), amount_rial: rial });
  };

  const expenseCats = (categories.data ?? []).filter(
    (c) => c.kind === "expense" || c.kind === "fee" || c.kind === "loan",
  );

  return (
    <>
      <PageHeader
        title="بودجهٔ ماهانه"
        subtitle={`سقف خرج هر دسته — وضعیت ${summary.data?.label ?? ""}`}
      />

      <form onSubmit={submit} className="card card-pad mb-4">
        <div className="flex flex-wrap items-end gap-3">
          <div className="min-w-[13rem] flex-1">
            <label className="label">دسته</label>
            <select
              className="input"
              value={categoryId}
              onChange={(e) => setCategoryId(e.target.value)}
            >
              <option value="">— انتخاب کن —</option>
              {expenseCats.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.parent_id ? "└ " : ""}
                  {c.name_fa}
                </option>
              ))}
            </select>
          </div>
          <div className="min-w-[11rem] flex-1">
            <label className="label">سقف ماهانه (تومان)</label>
            <input
              className="input tnum"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              placeholder="۵۰۰۰۰۰۰"
              dir="ltr"
            />
          </div>
          <button className="btn-primary" disabled={save.isPending}>
            ثبت بودجه
          </button>
        </div>
        {error && (
          <div className="mt-3">
            <ErrorBox message={error} />
          </div>
        )}
        <p className="mt-2 text-[11px] text-text-mute">
          بودجه به‌صورت پیش‌فرض برای همهٔ ماه‌ها اعمال می‌شود.
        </p>
      </form>

      {status.isLoading ? (
        <Loading />
      ) : !status.data?.length ? (
        <Empty
          title="هنوز بودجه‌ای تعیین نشده."
          hint="با تعیین سقف برای دسته‌های پرخرج، تجاوز از بودجه در داشبورد هشدار داده می‌شود."
        />
      ) : (
        <div className="space-y-3">
          {status.data.map((b) => (
            <div key={b.budget_id} className="card card-pad">
              <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <span
                    className="size-3 rounded-full"
                    style={{ background: b.color }}
                  />
                  <span className="font-medium">{b.category_name}</span>
                  {b.is_over && <Pill tone="red">از بودجه گذشته</Pill>}
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-sm tnum">
                    <b className={b.is_over ? "text-loss" : ""}>{toman(b.spent_rial)}</b>
                    <span className="text-text-mute"> از {toman(b.amount_rial)} تومان</span>
                  </span>
                  <button
                    className="btn-danger !px-2 !py-1 text-xs"
                    onClick={() => remove.mutate(b.budget_id)}
                  >
                    حذف
                  </button>
                </div>
              </div>
              <Bar ratio={b.ratio} color={b.color} />
              <div className="mt-1.5 flex justify-between text-[11px] tnum text-text-mute">
                <span>{percent(b.ratio)} مصرف شده</span>
                <span>
                  {b.remaining_rial >= 0
                    ? `${toman(b.remaining_rial)} تومان باقی مانده`
                    : `${toman(-b.remaining_rial)} تومان بیشتر خرج شده`}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </>
  );
}
