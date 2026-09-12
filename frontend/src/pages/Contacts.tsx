import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Star, Trash2 } from "lucide-react";
import { useState } from "react";

import CategorySelect from "../components/CategorySelect";
import { Empty, ErrorBox, Item, Loading, PageHeader, Pill, Stagger } from "../components/ui";
import { api } from "../lib/api";
import { faDigits, toman } from "../lib/format";
import type { Category, Contact } from "../lib/types";

/**
 * مخاطبین مالی.
 *
 * هر مخاطب با شناسه‌هایش (کارت، شبا، سپرده، پایانه) شناخته می‌شود.
 * نکتهٔ کلیدی: دستهٔ پیش‌فرض برای هر جهت جداست — «اگر از این مخاطب پول
 * آمد حقوق است» ولی وقتی به او پول می‌دهم می‌تواند چیز دیگری باشد.
 */
export default function Contacts() {
  const qc = useQueryClient();
  const [tab, setTab] = useState<"contacts" | "categories">("contacts");
  const [error, setError] = useState("");

  const contacts = useQuery({
    queryKey: ["contacts"],
    queryFn: () => api.get<Contact[]>("/api/contacts"),
  });
  const categories = useQuery({
    queryKey: ["categories"],
    queryFn: () => api.get<Category[]>("/api/categories"),
  });

  const patch = useMutation({
    mutationFn: ({ id, body }: { id: number; body: Record<string, unknown> }) =>
      api.patch(`/api/contacts/${id}`, body),
    onSuccess: () => qc.invalidateQueries(),
    onError: (e: Error) => setError(e.message),
  });
  const remove = useMutation({
    mutationFn: (id: number) => api.del(`/api/contacts/${id}`),
    onSuccess: () => qc.invalidateQueries(),
  });

  const cats = categories.data ?? [];

  return (
    <>
      <PageHeader
        title="مخاطبین"
        subtitle="هر مخاطب با شماره کارت، شبا یا پایانه‌اش شناخته می‌شود — یک‌بار ثبت، همیشه خودکار"
      />

      <div className="mb-4 flex gap-2">
        <button
          className={tab === "contacts" ? "btn-primary" : "btn-ghost"}
          onClick={() => setTab("contacts")}
        >
          مخاطبین
        </button>
        <button
          className={tab === "categories" ? "btn-primary" : "btn-ghost"}
          onClick={() => setTab("categories")}
        >
          دسته‌ها
        </button>
      </div>

      {error && (
        <div className="mb-3">
          <ErrorBox message={error} />
        </div>
      )}

      {tab === "contacts" ? (
        contacts.isLoading ? (
          <Loading />
        ) : !contacts.data?.length ? (
          <Empty
            title="هنوز مخاطبی ثبت نشده."
            hint="از صفحهٔ تراکنش‌ها یا صف بررسی، دکمهٔ «افزودن به مخاطبین» را بزن تا شماره کارت یا شبای طرف مقابل ذخیره شود."
          />
        ) : (
          <div className="card scroll-x">
            <table className="w-full min-w-[62rem]">
              <thead className="border-b border-border bg-surface-raised">
                <tr>
                  <th className="th">مخاطب</th>
                  <th className="th">وقتی پول می‌دهم</th>
                  <th className="th">وقتی پول می‌گیرم</th>
                  <th className="th">شناسه‌ها</th>
                  <th className="th">تراکنش</th>
                  <th className="th">جمع (تومان)</th>
                  <th className="th"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {contacts.data.map((m) => (
                  <tr key={m.id}>
                    <td className="td">
                      <div className="flex items-center gap-2">
                        <button
                          className="btn-icon !min-h-0 !min-w-0 p-1"
                          aria-label={m.is_favorite ? "حذف از دلخواه" : "افزودن به دلخواه"}
                          onClick={() =>
                            patch.mutate({ id: m.id, body: { is_favorite: !m.is_favorite } })
                          }
                        >
                          <Star
                            size={14}
                            className={m.is_favorite ? "fill-warn text-warn" : ""}
                            aria-hidden
                          />
                        </button>
                        <div>
                          <div className="font-medium">{m.name_fa}</div>
                          <div className="text-[11px] text-text-mute">{m.kind_label}</div>
                        </div>
                      </div>
                    </td>
                    <td className="td">
                      <CategorySelect
                        side="expense"
                        value={m.category_id}
                        onChange={(v) => patch.mutate({ id: m.id, body: { category_id: v } })}
                      />
                    </td>
                    <td className="td">
                      <CategorySelect
                        side="income"
                        value={m.income_category_id}
                        onChange={(v) =>
                          patch.mutate({ id: m.id, body: { income_category_id: v } })
                        }
                      />
                    </td>
                    <td className="td">
                      <div className="flex flex-wrap gap-1">
                        {m.identifiers.map((i) => (
                          <span
                            key={i.id}
                            className="chip bg-surface-raised text-text-soft"
                            title={`${i.kind_label}: ${i.value}`}
                          >
                            <span className="font-mono text-[10px]" dir="ltr">
                              {i.value.length > 16 ? `…${i.value.slice(-8)}` : i.value}
                            </span>
                          </span>
                        ))}
                      </div>
                    </td>
                    <td className="td tnum">{faDigits(m.transaction_count)}</td>
                    <td className="td font-semibold tnum">{toman(m.total_rial)}</td>
                    <td className="td">
                      <button
                        className="btn-icon text-loss"
                        aria-label={`حذف ${m.name_fa}`}
                        onClick={() => remove.mutate(m.id)}
                      >
                        <Trash2 size={15} aria-hidden />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )
      ) : (
        <>
          <div className="card card-pad mb-4">
            <label className="label">ساختن دستهٔ تازه</label>
            <p className="mb-2 text-[11px] text-text-mute">
              نوع دسته تعیین می‌کند در گزارش‌ها کجا شمرده شود؛ رنگ در نمودارها دیده می‌شود.
            </p>
            <CategorySelect side="all" value={null} onChange={() => {}} allowEmpty />
          </div>

          <Stagger className="card scroll-x">
            <table className="w-full min-w-[36rem]">
              <thead className="border-b border-border bg-surface-raised">
                <tr>
                  <th className="th">دسته</th>
                  <th className="th">نوع</th>
                  <th className="th">تراکنش</th>
                  <th className="th"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {cats.map((c) => (
                  <tr key={c.id}>
                    <td className="td">
                      <span className="flex items-center gap-2">
                        <span
                          className="size-3 shrink-0 rounded-full"
                          style={{ background: c.color }}
                        />
                        {c.parent_id && <span className="text-text-mute">└</span>}
                        {c.name_fa}
                      </span>
                    </td>
                    <td className="td">
                      <Pill tone={c.kind === "income" ? "green" : "slate"}>
                        {
                          {
                            expense: "هزینه",
                            income: "درآمد",
                            transfer: "انتقال",
                            fee: "کارمزد",
                            loan: "وام",
                            adjustment: "تعدیل",
                          }[c.kind] ?? c.kind
                        }
                      </Pill>
                    </td>
                    <td className="td tnum">{faDigits(c.transaction_count)}</td>
                    <td className="td">
                      {!c.is_system && (
                        <button
                          className="btn-icon text-loss"
                          aria-label={`حذف ${c.name_fa}`}
                          onClick={() =>
                            api.del(`/api/categories/${c.id}`).then(() => qc.invalidateQueries())
                          }
                        >
                          <Trash2 size={15} aria-hidden />
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Stagger>
        </>
      )}
    </>
  );
}
