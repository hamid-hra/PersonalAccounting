import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Check,
  ExternalLink,
  ImagePlus,
  Plus,
  RotateCcw,
  Trash2,
  TriangleAlert,
} from "lucide-react";
import { useState } from "react";

import JalaliDate from "../components/JalaliDate";
import { Empty, ErrorBox, Loading, PageHeader, Pill } from "../components/ui";
import { api } from "../lib/api";
import { faDigits, parseTomanInput, toman } from "../lib/format";
import type { Category, WishItem, WishList, WishSuggestion } from "../lib/types";

const EMPTY = {
  title: "",
  estimated: "",
  priority: "nice",
  deadline_jalali: "",
  url: "",
  category_id: "",
  note: "",
};

const PRIORITY_TONE: Record<string, "red" | "amber" | "slate"> = {
  need: "red",
  nice: "amber",
  someday: "slate",
};

export default function Wishlist() {
  const qc = useQueryClient();
  const [form, setForm] = useState({ ...EMPTY });
  const [showForm, setShowForm] = useState(false);
  const [error, setError] = useState("");
  const [buyingId, setBuyingId] = useState<number | null>(null);

  const list = useQuery({
    queryKey: ["wishlist"],
    queryFn: () => api.get<WishList>("/api/wishlist"),
  });
  const categories = useQuery({
    queryKey: ["categories"],
    queryFn: () => api.get<Category[]>("/api/categories"),
  });
  const suggestions = useQuery({
    queryKey: ["wish-suggest", buyingId],
    queryFn: () => api.get<WishSuggestion[]>(`/api/wishlist/${buyingId}/suggest-transactions`),
    enabled: buyingId !== null,
  });

  const invalidate = () => qc.invalidateQueries();
  const create = useMutation({
    mutationFn: (body: unknown) => api.post("/api/wishlist", body),
    onSuccess: () => {
      setForm({ ...EMPTY });
      setShowForm(false);
      setError("");
      invalidate();
    },
    onError: (e: Error) => setError(e.message),
  });
  const buy = useMutation({
    mutationFn: ({ id, tx }: { id: number; tx: number | null }) =>
      api.post(`/api/wishlist/${id}/bought`, { transaction_id: tx }),
    onSuccess: () => {
      setBuyingId(null);
      invalidate();
    },
    onError: (e: Error) => setError(e.message),
  });
  const unbuy = useMutation({
    mutationFn: (id: number) => api.post(`/api/wishlist/${id}/unbought`),
    onSuccess: invalidate,
  });
  const remove = useMutation({
    mutationFn: (id: number) => api.del(`/api/wishlist/${id}`),
    onSuccess: invalidate,
  });
  const uploadImage = useMutation({
    mutationFn: ({ id, file }: { id: number; file: File }) => {
      const fd = new FormData();
      fd.append("file", file);
      return api.upload(`/api/wishlist/${id}/image`, fd);
    },
    onSuccess: invalidate,
    onError: (e: Error) => setError(e.message),
  });

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.title.trim()) {
      setError("عنوان لازم است.");
      return;
    }
    create.mutate({
      title: form.title.trim(),
      estimated_rial: parseTomanInput(form.estimated),
      priority: form.priority,
      deadline_jalali: form.deadline_jalali || null,
      url: form.url.trim() || null,
      category_id: form.category_id ? Number(form.category_id) : null,
      note: form.note.trim() || null,
    });
  };

  const data = list.data;
  const open = (data?.items ?? []).filter((i) => !i.is_bought);
  const bought = (data?.items ?? []).filter((i) => i.is_bought);

  return (
    <>
      <PageHeader
        title="لیست نیازها"
        subtitle="چیزهایی که لازم داری — با برآورد قیمت و ددلاین"
        action={
          <button className="btn-primary" onClick={() => setShowForm((v) => !v)}>
            <Plus size={15} aria-hidden />
            {showForm ? "بستن" : "افزودن مورد"}
          </button>
        }
      />

      {error && (
        <div className="mb-3">
          <ErrorBox message={error} />
        </div>
      )}

      {data && (
        <div className="mb-4 grid grid-cols-1 gap-3 sm:grid-cols-3">
          <div className="card card-pad">
            <div className="text-xs text-text-mute">موارد باز</div>
            <div className="mt-1.5 text-xl font-bold tnum">{faDigits(data.open_count)}</div>
          </div>
          <div className="card card-pad">
            <div className="text-xs text-text-mute">جمع برآورد</div>
            <div className="mt-1.5 text-xl font-bold tnum">
              {toman(data.open_total_rial)}
              <span className="ms-1 text-xs font-normal text-text-mute">تومان</span>
            </div>
          </div>
          <div className="card card-pad">
            <div className="text-xs text-text-mute">ددلاین گذشته</div>
            <div
              className={`mt-1.5 text-xl font-bold tnum ${data.overdue_count ? "text-loss" : ""}`}
            >
              {faDigits(data.overdue_count)}
            </div>
          </div>
        </div>
      )}

      {showForm && (
        <form onSubmit={submit} className="card card-pad mb-4">
          <div className="flex flex-wrap gap-3">
            <div className="min-w-[14rem] flex-[2]">
              <label className="label" htmlFor="w-title">
                چه چیزی لازم داری؟
              </label>
              <input
                id="w-title"
                className="input"
                placeholder="مثلاً کفش زمستانی"
                value={form.title}
                onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))}
              />
            </div>
            <div className="min-w-[10rem] flex-1">
              <label className="label" htmlFor="w-price">
                برآورد قیمت (تومان)
              </label>
              <input
                id="w-price"
                className="input tnum"
                dir="ltr"
                placeholder="۲۵۰۰۰۰۰"
                value={form.estimated}
                onChange={(e) => setForm((f) => ({ ...f, estimated: e.target.value }))}
              />
            </div>
            <div className="min-w-[9rem]">
              <label className="label" htmlFor="w-prio">
                اولویت
              </label>
              <select
                id="w-prio"
                className="input"
                value={form.priority}
                onChange={(e) => setForm((f) => ({ ...f, priority: e.target.value }))}
              >
                <option value="need">ضروری</option>
                <option value="nice">خوب است باشد</option>
                <option value="someday">روزی روزگاری</option>
              </select>
            </div>
            <div className="min-w-[11rem] flex-1">
              <label className="label" htmlFor="w-deadline">
                تا کِی؟ (اختیاری)
              </label>
              <JalaliDate
                id="w-deadline"
                value={form.deadline_jalali}
                onChange={(v) => setForm((f) => ({ ...f, deadline_jalali: v }))}
              />
            </div>
            <div className="min-w-[10rem]">
              <label className="label" htmlFor="w-cat">
                دسته (اختیاری)
              </label>
              <select
                id="w-cat"
                className="input"
                value={form.category_id}
                onChange={(e) => setForm((f) => ({ ...f, category_id: e.target.value }))}
              >
                <option value="">—</option>
                {(categories.data ?? [])
                  .filter((c) => ["expense", "fee", "loan"].includes(c.kind))
                  .map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.parent_id ? "└ " : ""}
                      {c.name_fa}
                    </option>
                  ))}
              </select>
            </div>
            <div className="min-w-[14rem] flex-1">
              <label className="label" htmlFor="w-url">
                لینک محصول (اختیاری)
              </label>
              <input
                id="w-url"
                className="input"
                dir="ltr"
                placeholder="https://…"
                value={form.url}
                onChange={(e) => setForm((f) => ({ ...f, url: e.target.value }))}
              />
            </div>
          </div>
          <button className="btn-primary mt-3" disabled={create.isPending}>
            ثبت
          </button>
        </form>
      )}

      {list.isLoading ? (
        <Loading />
      ) : !data?.items.length ? (
        <Empty
          title="هنوز چیزی در لیست نیست."
          hint="هرچه لازم داری اینجا بنویس — با قیمت تقریبی و ددلاین، تا موقع خرید غافلگیر نشوی."
        />
      ) : (
        <div className="space-y-4">
          {[
            ["هنوز نخریده‌ام", open],
            ["خریده‌شده", bought],
          ]
            .filter(([, items]) => (items as WishItem[]).length > 0)
            .map(([heading, items]) => (
              <section key={heading as string}>
                <h2 className="mb-2 text-sm font-semibold">{heading as string}</h2>
                <div className="grid gap-3 lg:grid-cols-2">
                  {(items as WishItem[]).map((w) => (
                    <div
                      key={w.id}
                      className={`card card-pad ${w.is_bought ? "opacity-70" : ""}`}
                    >
                      <div className="flex gap-3">
                        {w.image_url ? (
                          <img
                            src={w.image_url}
                            alt={w.title}
                            className="size-16 shrink-0 rounded-lg border border-border object-cover"
                          />
                        ) : (
                          <label className="grid size-16 shrink-0 cursor-pointer place-items-center rounded-lg border border-dashed border-border-strong text-text-mute hover:border-brand hover:text-brand">
                            <ImagePlus size={18} aria-hidden />
                            <span className="sr-only">افزودن عکس برای {w.title}</span>
                            <input
                              type="file"
                              accept="image/*"
                              className="hidden"
                              onChange={(e) => {
                                const file = e.target.files?.[0];
                                if (file) uploadImage.mutate({ id: w.id, file });
                              }}
                            />
                          </label>
                        )}

                        <div className="min-w-0 flex-1">
                          <div className="flex flex-wrap items-center gap-2">
                            <span
                              className={`font-semibold ${w.is_bought ? "line-through" : ""}`}
                            >
                              {w.title}
                            </span>
                            <Pill tone={PRIORITY_TONE[w.priority] ?? "slate"}>
                              {w.priority_label}
                            </Pill>
                            {w.category_name && <Pill>{w.category_name}</Pill>}
                            {w.is_overdue && (
                              <span className="chip bg-loss-soft text-loss">
                                <TriangleAlert size={12} aria-hidden />
                                ددلاین گذشته
                              </span>
                            )}
                            {w.is_soon && (
                              <span className="chip bg-warn-soft text-warn">
                                {faDigits(w.days_left ?? 0)} روز مانده
                              </span>
                            )}
                          </div>

                          <div className="mt-1 flex flex-wrap items-baseline gap-x-3 gap-y-1 text-xs text-text-mute">
                            {w.estimated_rial != null && (
                              <span className="tnum">برآورد {toman(w.estimated_rial)} تومان</span>
                            )}
                            {w.actual_rial != null && (
                              <span className="tnum">
                                واقعی <b className="text-text">{toman(w.actual_rial)}</b>
                              </span>
                            )}
                            {w.difference_rial != null && (
                              <span
                                className={`tnum font-medium ${
                                  w.difference_rial > 0 ? "text-loss" : "text-gain"
                                }`}
                              >
                                {w.difference_rial > 0 ? "+" : "−"}
                                {toman(Math.abs(w.difference_rial))}
                              </span>
                            )}
                            {w.deadline_jalali && <span className="tnum">تا {w.deadline_jalali}</span>}
                          </div>

                          {w.url && (
                            <a
                              href={w.url}
                              target="_blank"
                              rel="noreferrer noopener"
                              className="mt-1 inline-flex items-center gap-1 text-xs text-brand-text hover:underline"
                            >
                              <ExternalLink size={12} aria-hidden />
                              صفحهٔ محصول
                            </a>
                          )}
                        </div>

                        <div className="flex shrink-0 flex-col gap-1">
                          {w.is_bought ? (
                            <button
                              className="btn-icon"
                              aria-label="برگرداندن به لیست"
                              title="هنوز نخریده‌ام"
                              onClick={() => unbuy.mutate(w.id)}
                            >
                              <RotateCcw size={15} aria-hidden />
                            </button>
                          ) : (
                            <button
                              className="btn-icon text-gain"
                              aria-label={`${w.title} را خریدم`}
                              title="خریدم"
                              onClick={() => setBuyingId(buyingId === w.id ? null : w.id)}
                            >
                              <Check size={16} aria-hidden />
                            </button>
                          )}
                          <button
                            className="btn-icon text-loss"
                            aria-label={`حذف ${w.title}`}
                            onClick={() => remove.mutate(w.id)}
                          >
                            <Trash2 size={15} aria-hidden />
                          </button>
                        </div>
                      </div>

                      {buyingId === w.id && (
                        <div className="mt-3 border-t border-border pt-3">
                          <p className="mb-2 text-xs text-text-mute">
                            کدام تراکنش این خرید بود؟ (اختیاری — برای مقایسهٔ قیمت واقعی
                            با برآورد)
                          </p>
                          <div className="flex flex-wrap gap-2">
                            <button
                              className="btn-ghost !py-1 text-xs"
                              onClick={() => buy.mutate({ id: w.id, tx: null })}
                            >
                              بدون تراکنش
                            </button>
                            {(suggestions.data ?? []).map((s) => (
                              <button
                                key={s.id}
                                className="btn-ghost !py-1 text-xs"
                                onClick={() => buy.mutate({ id: w.id, tx: s.id })}
                              >
                                <span className="tnum">{toman(Math.abs(s.amount_rial))}</span>
                                <span className="text-text-mute">
                                  {s.jalali_datetime.slice(0, 10)}
                                </span>
                              </button>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </section>
            ))}
        </div>
      )}
    </>
  );
}
