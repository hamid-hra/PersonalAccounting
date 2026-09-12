import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRef, useState } from "react";

import { Empty, ErrorBox, PageHeader, Pill } from "../components/ui";
import { api } from "../lib/api";
import { faDigits, jalaliDate, num, toman } from "../lib/format";
import type { ImportPreview, ImportResult } from "../lib/types";

function CheckRow({
  check,
}: {
  check: { name: string; status: string; expected?: number; actual?: number; detail?: string };
}) {
  const tone =
    check.status === "ok" ? "green" : check.status === "warn" ? "amber" : "red";
  const label =
    check.status === "ok"
      ? "درست"
      : check.status === "warn"
        ? "هشدار"
        : check.status === "skipped"
          ? "در فایل نبود"
          : "ناهمخوان";
  return (
    <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border py-2 last:border-0">
      <div className="flex items-center gap-2">
        <Pill tone={check.status === "skipped" ? "slate" : (tone as never)}>{label}</Pill>
        <span className="text-sm">{check.name}</span>
      </div>
      {typeof check.expected === "number" && (
        <div className="text-xs text-text-mute tnum">
          انتظار {num(check.expected)} / واقعی {num(check.actual ?? 0)}
        </div>
      )}
      {check.detail && <div className="text-[11px] text-text-mute">{check.detail}</div>}
    </div>
  );
}

export default function ImportPage() {
  const qc = useQueryClient();
  const inputRef = useRef<HTMLInputElement>(null);
  const [drag, setDrag] = useState(false);
  const [result, setResult] = useState<ImportResult | null>(null);
  const [preview, setPreview] = useState<ImportPreview | null>(null);
  const [pendingFile, setPendingFile] = useState<File | null>(null);
  const [error, setError] = useState("");

  const { data: history } = useQuery({
    queryKey: ["imports"],
    queryFn: () => api.get<any[]>("/api/imports"),
  });

  // مرحلهٔ اول: فقط می‌خوانیم و گزارش می‌دهیم — هیچ چیزی نوشته نمی‌شود.
  const inspect = useMutation({
    mutationFn: (file: File) => {
      const form = new FormData();
      form.append("file", file);
      return api.upload<ImportPreview>("/api/imports/preview", form);
    },
    onSuccess: (data) => {
      setPreview(data);
      setResult(null);
      setError("");
    },
    onError: (err: Error) => {
      setError(err.message);
      setPreview(null);
      setPendingFile(null);
    },
  });

  // مرحلهٔ دوم: بعد از دیدن گزارش، ثبت نهایی
  const upload = useMutation({
    mutationFn: (file: File) => {
      const form = new FormData();
      form.append("file", file);
      return api.upload<ImportResult>("/api/imports", form);
    },
    onSuccess: (data) => {
      setResult(data);
      setPreview(null);
      setPendingFile(null);
      setError("");
      qc.invalidateQueries();
    },
    onError: (err: Error) => {
      setError(err.message);
      setResult(null);
    },
  });

  const handle = (files: FileList | null) => {
    const file = files?.[0];
    if (!file) return;
    setPendingFile(file);
    inspect.mutate(file);
  };

  const reset = () => {
    setPreview(null);
    setPendingFile(null);
    setError("");
  };

  return (
    <>
      <PageHeader
        title="ورود صورتحساب اکسل"
        subtitle="فایل خروجی بانک را بکش و رها کن. تراکنش‌های تکراری خودکار کنار گذاشته می‌شوند."
      />

      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDrag(true);
        }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDrag(false);
          handle(e.dataTransfer.files);
        }}
        onClick={() => inputRef.current?.click()}
        className={`card grid cursor-pointer place-items-center border-2 border-dashed px-6 py-12 text-center transition ${
          drag ? "border-brand bg-brand-soft" : "border-border-strong hover:border-brand"
        }`}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".xlsx,.xlsm,.xls"
          hidden
          onChange={(e) => handle(e.target.files)}
        />
        <div className="text-3xl text-text-mute">↥</div>
        <div className="mt-2 text-sm font-medium">
          {inspect.isPending
            ? "در حال خواندن فایل…"
            : upload.isPending
              ? "در حال ثبت…"
              : "فایل اکسل صورتحساب را اینجا رها کن"}
        </div>
        <div className="mt-1 text-xs text-text-mute">
          بانک سامان (xlsx) و بانک ملی/بام (xls) — فرمت خودکار تشخیص داده می‌شود
        </div>
      </div>

      {error && (
        <div className="mt-4">
          <ErrorBox message={error} />
        </div>
      )}

      {preview && (
        <div className="card card-pad mt-4">
          <h2 className="text-sm font-semibold">
            پیش‌نمایش — هنوز چیزی ثبت نشده
          </h2>
          <p className="mt-1 text-xs text-text-mute">
            {preview.bank_label}
            {preview.owner_name && ` · ${preview.owner_name}`}
            {preview.period_from_jalali &&
              ` · ${jalaliDate(preview.period_from_jalali)} تا ${jalaliDate(preview.period_to_jalali)}`}
          </p>

          <div className="mt-3 grid grid-cols-3 gap-3">
            <div className="rounded-lg bg-surface-raised p-3">
              <div className="text-[11px] text-text-mute">کل سطرها</div>
              <div className="text-lg font-bold tnum">{faDigits(preview.rows_total)}</div>
            </div>
            <div className="rounded-lg bg-gain-soft p-3">
              <div className="text-[11px] text-gain">تازه</div>
              <div className="text-lg font-bold tnum text-gain">
                {faDigits(preview.rows_new)}
              </div>
            </div>
            <div className="rounded-lg bg-surface-raised p-3">
              <div className="text-[11px] text-text-mute">تکراری (وارد نمی‌شود)</div>
              <div className="text-lg font-bold tnum text-text-mute">
                {faDigits(preview.rows_duplicate)}
              </div>
            </div>
          </div>

          {preview.account_title && (
            <p className="mt-3 text-xs text-text-mute">
              به حساب <b className="text-text">{preview.account_title}</b> اضافه می‌شود.
            </p>
          )}

          {preview.warnings.map((w, i) => (
            <div
              key={i}
              className={`mt-3 rounded-lg px-3.5 py-2.5 text-xs ${
                w.level === "warn"
                  ? "border border-warn/30 bg-warn-soft text-warn"
                  : "bg-surface-raised text-text-soft"
              }`}
            >
              {w.text}
            </div>
          ))}

          <div className="mt-4 flex flex-wrap gap-2">
            <button
              className="btn-primary"
              disabled={upload.isPending || preview.rows_new === 0}
              onClick={() => pendingFile && upload.mutate(pendingFile)}
            >
              {preview.rows_new === 0
                ? "چیزی برای افزودن نیست"
                : `ثبت ${faDigits(preview.rows_new)} تراکنش تازه`}
            </button>
            <button className="btn-ghost" onClick={reset}>
              انصراف
            </button>
          </div>
        </div>
      )}

      {result && (
        <div className="card card-pad mt-4">
          <div className="flex flex-wrap items-center gap-4">
            <div>
              <div className="text-xs text-text-mute">تراکنش جدید</div>
              <div className="text-2xl font-bold text-gain tnum">
                {faDigits(result.rows_inserted)}
              </div>
            </div>
            <div>
              <div className="text-xs text-text-mute">تکراری (نادیده گرفته شد)</div>
              <div className="text-2xl font-bold text-text-mute tnum">
                {faDigits(result.rows_duplicate)}
              </div>
            </div>
            <div>
              <div className="text-xs text-text-mute">کل سطرهای فایل</div>
              <div className="text-2xl font-bold tnum">{faDigits(result.rows_total)}</div>
            </div>
          </div>

          <h3 className="mt-5 text-sm font-semibold">
            اعتبارسنجی — اعداد محاسبه‌شده با سرصفحهٔ خودِ فایل مقایسه شد
          </h3>
          <div className="mt-1">
            {result.validation.checks.map((c) => (
              <CheckRow key={c.name} check={c} />
            ))}
          </div>
        </div>
      )}

      <h2 className="mb-3 mt-8 text-sm font-semibold text-text-soft">فایل‌های واردشده</h2>
      {!history?.length ? (
        <Empty title="هنوز فایلی وارد نشده است." />
      ) : (
        <div className="card scroll-x">
          <table className="w-full min-w-[52rem]">
            <thead className="border-b border-border bg-surface-raised">
              <tr>
                <th className="th">فایل</th>
                <th className="th">دوره</th>
                <th className="th">جدید</th>
                <th className="th">تکراری</th>
                <th className="th">وضعیت</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {history.map((h) => (
                <tr key={h.id}>
                  <td className="td max-w-[16rem] truncate">{h.original_name}</td>
                  <td className="td text-xs tnum text-text-mute">
                    {jalaliDate(h.period_from_jalali)} تا {jalaliDate(h.period_to_jalali)}
                  </td>
                  <td className="td tnum">{faDigits(h.rows_inserted)}</td>
                  <td className="td tnum text-text-mute">{faDigits(h.rows_duplicate)}</td>
                  <td className="td">
                    <Pill tone={h.validation?.ok ? "green" : "amber"}>
                      {h.validation?.ok ? "سالم" : "با هشدار"}
                    </Pill>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
