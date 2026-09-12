import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { api } from "../lib/api";
import type { Category } from "../lib/types";

const KINDS = [
  { value: "expense", label: "هزینه" },
  { value: "income", label: "درآمد" },
  { value: "fee", label: "کارمزد" },
  { value: "loan", label: "وام و قسط" },
  { value: "transfer", label: "انتقال" },
  { value: "adjustment", label: "تعدیل" },
];

const PALETTE = [
  "#ef4444", "#f97316", "#eab308", "#84cc16", "#22c55e",
  "#14b8a6", "#0ea5e9", "#6366f1", "#a855f7", "#ec4899",
  "#78716c", "#64748b",
];

const INCOME_KINDS = ["income", "transfer", "adjustment"];

/**
 * انتخاب دسته با امکان ساختن دستهٔ تازه در همان‌جا.
 *
 * قبلاً برای ساختن یک دسته باید صفحه را عوض می‌کردی و برمی‌گشتی؛ حالا
 * گزینهٔ «+ ساختن دستهٔ تازه» همان‌جا فرم کوچکی باز می‌کند و دستهٔ
 * ساخته‌شده بلافاصله انتخاب می‌شود.
 */
export default function CategorySelect({
  value,
  onChange,
  side = "expense",
  id,
  label,
  allowEmpty = true,
}: {
  value: number | null;
  onChange: (v: number | null) => void;
  /** «expense» فقط دسته‌های خرج، «income» درآمد و انتقال، «all» همه */
  side?: "expense" | "income" | "all";
  id?: string;
  label?: string;
  allowEmpty?: boolean;
}) {
  const qc = useQueryClient();
  const [creating, setCreating] = useState(false);
  const [draft, setDraft] = useState({
    name_fa: "",
    kind: side === "income" ? "income" : "expense",
    parent_id: "",
    color: PALETTE[7],
  });
  const [error, setError] = useState("");

  const categories = useQuery({
    queryKey: ["categories"],
    queryFn: () => api.get<Category[]>("/api/categories"),
  });

  const create = useMutation({
    mutationFn: (body: unknown) => api.post<Category>("/api/categories", body),
    onSuccess: (cat) => {
      setCreating(false);
      setDraft({ ...draft, name_fa: "" });
      setError("");
      qc.invalidateQueries({ queryKey: ["categories"] });
      onChange(cat.id);
    },
    onError: (e: Error) => setError(e.message),
  });

  const all = categories.data ?? [];
  const visible =
    side === "all"
      ? all
      : side === "income"
        ? all.filter((c) => INCOME_KINDS.includes(c.kind))
        : all.filter((c) => !INCOME_KINDS.includes(c.kind));

  return (
    <div>
      {label && (
        <label className="label" htmlFor={id}>
          {label}
        </label>
      )}
      <select
        id={id}
        className="input"
        value={creating ? "__new__" : (value ?? "")}
        onChange={(e) => {
          if (e.target.value === "__new__") {
            setCreating(true);
            return;
          }
          setCreating(false);
          onChange(e.target.value ? Number(e.target.value) : null);
        }}
      >
        {allowEmpty && <option value="">—</option>}
        {visible.map((c) => (
          <option key={c.id} value={c.id}>
            {c.parent_id ? "└ " : ""}
            {c.name_fa}
          </option>
        ))}
        <option value="__new__">+ ساختن دستهٔ تازه…</option>
      </select>

      {creating && (
        <div className="mt-2 rounded-lg border border-border bg-surface-raised p-3">
          <div className="flex flex-wrap gap-2">
            <input
              className="input min-w-[9rem] flex-1"
              placeholder="نام دسته"
              autoFocus
              value={draft.name_fa}
              onChange={(e) => setDraft((d) => ({ ...d, name_fa: e.target.value }))}
            />
            <select
              className="input min-w-[7rem]"
              aria-label="نوع دسته"
              value={draft.kind}
              onChange={(e) => setDraft((d) => ({ ...d, kind: e.target.value }))}
            >
              {KINDS.map((k) => (
                <option key={k.value} value={k.value}>
                  {k.label}
                </option>
              ))}
            </select>
            <select
              className="input min-w-[8rem]"
              aria-label="زیرمجموعهٔ"
              value={draft.parent_id}
              onChange={(e) => setDraft((d) => ({ ...d, parent_id: e.target.value }))}
            >
              <option value="">دستهٔ اصلی</option>
              {all
                .filter((c) => !c.parent_id)
                .map((c) => (
                  <option key={c.id} value={c.id}>
                    زیرمجموعهٔ {c.name_fa}
                  </option>
                ))}
            </select>
          </div>

          <div className="mt-2 flex flex-wrap items-center gap-1.5">
            {PALETTE.map((c) => (
              <button
                key={c}
                type="button"
                aria-label={`رنگ ${c}`}
                onClick={() => setDraft((d) => ({ ...d, color: c }))}
                className={`size-6 rounded-full transition ${
                  draft.color === c ? "ring-2 ring-brand ring-offset-2" : ""
                }`}
                style={{ background: c, ["--tw-ring-offset-color" as string]: "rgb(var(--surface-raised))" }}
              />
            ))}
          </div>

          {error && <p className="mt-2 text-xs text-loss">{error}</p>}

          <div className="mt-2 flex gap-2">
            <button
              type="button"
              className="btn-primary !py-1 text-xs"
              disabled={!draft.name_fa.trim() || create.isPending}
              onClick={() =>
                create.mutate({
                  name_fa: draft.name_fa.trim(),
                  kind: draft.kind,
                  color: draft.color,
                  parent_id: draft.parent_id ? Number(draft.parent_id) : null,
                })
              }
            >
              ساختن و انتخاب
            </button>
            <button
              type="button"
              className="btn-ghost !py-1 text-xs"
              onClick={() => {
                setCreating(false);
                setError("");
              }}
            >
              انصراف
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
