import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Paperclip, Pencil } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import JalaliDate from "../components/JalaliDate";
import { Bar, ErrorBox, Loading, PageHeader, Pill } from "../components/ui";
import { api } from "../lib/api";
import { faDigits, jalaliDate, latinDigits, parseTomanInput, percent, toman } from "../lib/format";
import type { Attachment, Installment, Loan } from "../lib/types";

function StatusPill({ status }: { status: Installment["status"] }) {
  if (status === "paid") return <Pill tone="green">پرداخت‌شده</Pill>;
  if (status === "overdue") return <Pill tone="red">معوق</Pill>;
  return <Pill tone="slate">در انتظار</Pill>;
}

export default function LoanDetail() {
  const { id } = useParams();
  const qc = useQueryClient();
  const navigate = useNavigate();
  const [error, setError] = useState("");
  const [lightbox, setLightbox] = useState<Attachment | null>(null);
  const [uploadFor, setUploadFor] = useState<number | null>(null);
  const [editing, setEditing] = useState(false);
  const [edit, setEdit] = useState({
    title: "", lender: "", loan_ref: "",
    installment_count: "", installment_amount: "", first_due_jalali: "",
  });
  const fileRef = useRef<HTMLInputElement>(null);

  const loan = useQuery({
    queryKey: ["loan", id],
    queryFn: () => api.get<Loan>(`/api/loans/${id}`),
  });

  const pay = useMutation({
    mutationFn: (instId: number) => api.post(`/api/loans/installments/${instId}/pay`, {}),
    onSuccess: () => qc.invalidateQueries(),
    onError: (e: Error) => setError(e.message),
  });
  const unpay = useMutation({
    mutationFn: (instId: number) => api.post(`/api/loans/installments/${instId}/unpay`),
    onSuccess: () => qc.invalidateQueries(),
  });
  const upload = useMutation({
    mutationFn: ({ file, instId }: { file: File; instId: number | null }) => {
      const form = new FormData();
      form.append("file", file);
      if (instId !== null) form.append("installment_id", String(instId));
      return api.upload<Attachment>(`/api/loans/${id}/receipts`, form);
    },
    onSuccess: () => {
      setError("");
      qc.invalidateQueries();
    },
    onError: (e: Error) => setError(e.message),
  });
  const removeReceipt = useMutation({
    mutationFn: (attId: number) => api.del(`/api/loans/receipts/${attId}`),
    onSuccess: () => {
      setLightbox(null);
      qc.invalidateQueries();
    },
  });
  const update = useMutation({
    mutationFn: (body: unknown) => api.patch(`/api/loans/${id}`, body),
    onSuccess: () => {
      setEditing(false);
      setError("");
      qc.invalidateQueries();
    },
    onError: (e: Error) => setError(e.message),
  });
  const removeLoan = useMutation({
    mutationFn: () => api.del(`/api/loans/${id}`),
    onSuccess: () => navigate("/loans"),
  });

  if (loan.isLoading) return <Loading />;
  const l = loan.data;

  // فرم ویرایش با مقادیر فعلی وام پر می‌شود، نه خالی
  useEffect(() => {
    if (editing && l) {
      setEdit({
        title: l.title,
        lender: l.lender ?? "",
        loan_ref: l.loan_ref ?? "",
        installment_count: String(l.installment_count),
        installment_amount: String(Math.round(l.installment_amount_rial / 10)),
        first_due_jalali: l.first_due_jalali,
      });
    }
  }, [editing, l?.id]);
  if (!l) return <ErrorBox message="وام پیدا نشد." />;

  return (
    <>
      <PageHeader
        title={l.title}
        subtitle={`${l.lender ?? "—"}${l.loan_ref ? ` · ${l.loan_ref}` : ""}`}
        action={
          <div className="flex gap-2">
            <Link to="/loans" className="btn-ghost">
              بازگشت
            </Link>
            <button className="btn-ghost" onClick={() => setEditing((v) => !v)}>
              <Pencil size={15} aria-hidden />
              {editing ? "بستن ویرایش" : "ویرایش"}
            </button>
            <button
              className="btn-danger"
              onClick={() => {
                if (confirm("این وام و همهٔ اقساط و رسیدهایش حذف شود؟"))
                  removeLoan.mutate();
              }}
            >
              حذف وام
            </button>
          </div>
        }
      />

      {error && (
        <div className="mb-3">
          <ErrorBox message={error} />
        </div>
      )}

      <div className="card card-pad mb-4">
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {[
            ["مبلغ هر قسط", toman(l.installment_amount_rial)],
            ["جمع کل", toman(l.total_rial)],
            ["پرداخت‌شده", toman(l.paid_rial)],
            ["مانده", toman(l.remaining_rial)],
          ].map(([label, value]) => (
            <div key={label}>
              <div className="text-xs text-text-mute">{label}</div>
              <div className="text-lg font-bold tnum">{value}</div>
            </div>
          ))}
        </div>
        <div className="mt-4">
          <div className="mb-1 flex justify-between text-xs">
            <span>
              {faDigits(l.paid_count)} از {faDigits(l.installment_count)} قسط پرداخت شده
            </span>
            <span className="tnum text-text-mute">{percent(l.progress)}</span>
          </div>
          <Bar ratio={l.progress} />
        </div>
      </div>

      {editing && (
        <form
          className="card card-pad mb-4"
          onSubmit={(e) => {
            e.preventDefault();
            const body: Record<string, unknown> = {
              title: edit.title.trim(),
              lender: edit.lender.trim() || null,
              loan_ref: edit.loan_ref.trim() || null,
            };
            const count = Number(latinDigits(edit.installment_count));
            const amount = parseTomanInput(edit.installment_amount);
            if (count && count !== l.installment_count) body.installment_count = count;
            if (amount && amount !== l.installment_amount_rial)
              body.installment_amount_rial = amount;
            if (edit.first_due_jalali && edit.first_due_jalali !== l.first_due_jalali)
              body.first_due_jalali = edit.first_due_jalali;
            update.mutate(body);
          }}
        >
          <h2 className="mb-3 text-sm font-semibold">ویرایش وام</h2>
          <div className="flex flex-wrap gap-3">
            {(
              [
                ["title", "عنوان", false],
                ["lender", "وام‌دهنده", false],
                ["loan_ref", "شمارهٔ تسهیلات", true],
                ["installment_count", "تعداد اقساط", true],
                ["installment_amount", "مبلغ هر قسط (تومان)", true],
              ] as const
            ).map(([key, label, ltr]) => (
              <div className="min-w-[10rem] flex-1" key={key}>
                <label className="label" htmlFor={`e-${key}`}>
                  {label}
                </label>
                <input
                  id={`e-${key}`}
                  className={`input ${ltr ? "tnum" : ""}`}
                  dir={ltr ? "ltr" : undefined}
                  value={edit[key]}
                  onChange={(e) => setEdit((v) => ({ ...v, [key]: e.target.value }))}
                />
              </div>
            ))}
            <div className="min-w-[11rem] flex-1">
              <label className="label" htmlFor="e-due">
                اولین سررسید
              </label>
              <JalaliDate
                id="e-due"
                value={edit.first_due_jalali}
                onChange={(v) => setEdit((s) => ({ ...s, first_due_jalali: v }))}
              />
            </div>
          </div>
          <p className="mt-2 text-[11px] text-text-mute">
            اگر تعداد یا مبلغ قسط یا اولین سررسید را عوض کنی، جدول اقساط بازسازی
            می‌شود — ولی <b>قسط‌های پرداخت‌شده و رسیدهایشان دست‌نخورده می‌مانند</b>.
          </p>
          <button className="btn-primary mt-3" disabled={update.isPending}>
            ذخیرهٔ تغییرات
          </button>
        </form>
      )}

      {/* --------- اسناد کلی وام --------- */}
      <section className="card card-pad mb-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h2 className="text-sm font-semibold">اسناد وام</h2>
            <p className="mt-0.5 text-[11px] text-text-mute">
              قرارداد، دفترچهٔ اقساط، هر سندی که به کل وام مربوط است — نه به یک قسط.
            </p>
          </div>
          <button
            className="btn-ghost"
            onClick={() => {
              setUploadFor(null);
              fileRef.current?.click();
            }}
          >
            <Paperclip size={15} aria-hidden />
            افزودن سند
          </button>
        </div>
        {l.attachments?.length ? (
          <div className="mt-3 flex flex-wrap gap-2">
            {l.attachments.map((a) => (
              <button
                key={a.id}
                onClick={() => setLightbox(a)}
                className="flex items-center gap-2 rounded-lg border border-border bg-surface-raised px-2.5 py-1.5 text-xs hover:border-brand"
              >
                <Paperclip size={13} aria-hidden />
                <span className="max-w-[12rem] truncate">{a.original_name}</span>
              </button>
            ))}
          </div>
        ) : (
          <p className="mt-3 text-xs text-text-mute">هنوز سندی اضافه نشده.</p>
        )}
      </section>

      <input
        ref={fileRef}
        type="file"
        accept="image/png,image/jpeg,image/webp,application/pdf"
        hidden
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) upload.mutate({ file, instId: uploadFor });
          e.target.value = "";
        }}
      />

      <div className="card scroll-x">
        <table className="w-full min-w-[52rem]">
          <thead className="border-b border-border bg-surface-raised">
            <tr>
              <th className="th">قسط</th>
              <th className="th">سررسید</th>
              <th className="th">مبلغ (تومان)</th>
              <th className="th">وضعیت</th>
              <th className="th">رسیدها</th>
              <th className="th"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {(l.installments ?? []).map((i) => (
              <tr key={i.id} className={i.status === "overdue" ? "bg-loss-soft/40" : ""}>
                <td className="td tnum">{faDigits(i.seq)}</td>
                <td className="td whitespace-nowrap tnum">
                  {jalaliDate(i.due_jalali)}
                  {i.status !== "paid" && (
                    <div className="text-[11px] text-text-mute">
                      {i.days_left >= 0
                        ? `${faDigits(i.days_left)} روز مانده`
                        : `${faDigits(-i.days_left)} روز گذشته`}
                    </div>
                  )}
                  {i.paid_jalali && (
                    <div className="text-[11px] text-gain">
                      پرداخت {jalaliDate(i.paid_jalali)}
                    </div>
                  )}
                </td>
                <td className="td font-semibold tnum">{toman(i.amount_rial)}</td>
                <td className="td">
                  <StatusPill status={i.status} />
                </td>
                <td className="td">
                  <div className="flex flex-wrap items-center gap-1.5">
                    {i.attachments.map((a) => (
                      <button
                        key={a.id}
                        onClick={() => setLightbox(a)}
                        className="size-10 overflow-hidden rounded border border-border bg-surface-raised"
                        title={a.original_name}
                      >
                        {a.mime_type.startsWith("image/") ? (
                          <img
                            src={a.url}
                            alt={a.caption ?? a.original_name}
                            className="size-full object-cover"
                          />
                        ) : (
                          <span className="grid size-full place-items-center text-[10px]">
                            PDF
                          </span>
                        )}
                      </button>
                    ))}
                    <button
                      className="btn-ghost !px-2 !py-1 text-xs"
                      onClick={() => {
                        setUploadFor(i.id);
                        fileRef.current?.click();
                      }}
                    >
                      + رسید
                    </button>
                  </div>
                </td>
                <td className="td">
                  {i.status === "paid" ? (
                    <button
                      className="btn-ghost !py-1 text-xs"
                      onClick={() => unpay.mutate(i.id)}
                    >
                      لغو پرداخت
                    </button>
                  ) : (
                    <button
                      className="btn-primary !py-1 text-xs"
                      onClick={() => pay.mutate(i.id)}
                    >
                      ثبت پرداخت
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {lightbox && (
        <div
          className="fixed inset-0 z-50 grid place-items-center bg-black/70 p-4"
          onClick={() => setLightbox(null)}
        >
          <div
            className="card max-h-full w-full max-w-2xl overflow-auto p-3"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="mb-2 flex items-center justify-between gap-2">
              <span className="truncate text-sm font-medium">
                {lightbox.caption ?? lightbox.original_name}
              </span>
              <div className="flex gap-2">
                <button
                  className="btn-danger !px-2 !py-1 text-xs"
                  onClick={() => removeReceipt.mutate(lightbox.id)}
                >
                  حذف رسید
                </button>
                <button
                  className="btn-ghost !px-2 !py-1 text-xs"
                  onClick={() => setLightbox(null)}
                >
                  بستن
                </button>
              </div>
            </div>
            {lightbox.mime_type.startsWith("image/") ? (
              <img src={lightbox.url} alt="" className="w-full rounded" />
            ) : (
              <a href={lightbox.url} target="_blank" rel="noreferrer" className="btn-primary">
                باز کردن فایل PDF
              </a>
            )}
          </div>
        </div>
      )}
    </>
  );
}
