import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Database, Download, KeyRound, Trash2 } from "lucide-react";
import { useState } from "react";

import { Empty, ErrorBox, Loading, PageHeader, Pill } from "../components/ui";
import { api } from "../lib/api";
import { PALETTES, useTheme } from "../lib/theme";
import { faDigits, jalaliDate, latinDigits, parseTomanInput, toman } from "../lib/format";
import type { Account, MarketSettings } from "../lib/types";

const ALIAS_KINDS = [
  { value: "name", label: "نام" },
  { value: "card", label: "شماره کارت" },
  { value: "iban", label: "شماره شبا" },
  { value: "deposit_no", label: "شماره سپرده" },
];

interface BackupEntry {
  name: string;
  created_at: string;
  created_jalali: string;
  size_bytes: number;
  files: string[];
}

export default function Settings() {
  const qc = useQueryClient();
  const { palette, setPalette, mode, setMode } = useTheme();
  const [pw, setPw] = useState({ current: "", next: "", confirm: "" });
  const [pwError, setPwError] = useState("");
  const [pwDone, setPwDone] = useState(false);
  const [apiKey, setApiKey] = useState("");

  const market = useQuery({
    queryKey: ["market-settings"],
    queryFn: () => api.get<MarketSettings>("/api/settings/market"),
  });
  const keyIsSet =
    market.data?.market_provider === "navasan"
      ? market.data?.navasan_key_set
      : market.data?.brsapi_key_set;
  const keyHint =
    market.data?.market_provider === "navasan"
      ? market.data?.navasan_key_hint
      : market.data?.brsapi_key_hint;

  const changePassword = useMutation({
    mutationFn: (body: { current_password: string; new_password: string }) =>
      api.post("/api/auth/password", body),
    onSuccess: () => {
      setPw({ current: "", next: "", confirm: "" });
      setPwError("");
      setPwDone(true);
    },
    onError: (e: Error) => {
      setPwError(e.message);
      setPwDone(false);
    },
  });

  const saveMarket = useMutation({
    mutationFn: (body: Record<string, string>) => api.put("/api/settings/market", body),
    onSuccess: () => {
      setApiKey("");
      qc.invalidateQueries();
    },
    onError: (e: Error) => setError(e.message),
  });
  const backups = useQuery({
    queryKey: ["backups"],
    queryFn: () => api.get<BackupEntry[]>("/api/settings/backups"),
  });
  const makeBackup = useMutation({
    mutationFn: () => api.post("/api/settings/backups"),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["backups"] }),
  });
  const removeBackup = useMutation({
    mutationFn: (name: string) => api.del(`/api/settings/backups/${name}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["backups"] }),
  });
  const [error, setError] = useState("");
  const [flash, setFlash] = useState("");
  const [kind, setKind] = useState("name");
  const [value, setValue] = useState("");
  const [threshold, setThreshold] = useState("");

  const accounts = useQuery({
    queryKey: ["accounts"],
    queryFn: () => api.get<Account[]>("/api/accounts"),
  });
  const aliases = useQuery({
    queryKey: ["aliases"],
    queryFn: () =>
      api.get<{ id: number; kind: string; value: string; note: string | null }[]>(
        "/api/settings/owner-aliases",
      ),
  });
  const settings = useQuery({
    queryKey: ["settings"],
    queryFn: () => api.get<Record<string, string>>("/api/settings"),
  });

  const addAlias = useMutation({
    mutationFn: (body: { kind: string; value: string }) =>
      api.post<{ recategorized: number }>("/api/settings/owner-aliases", body),
    onSuccess: (res) => {
      setValue("");
      setError("");
      setFlash(`ثبت شد و ${faDigits(res.recategorized)} تراکنش دوباره دسته‌بندی شد.`);
      qc.invalidateQueries();
    },
    onError: (e: Error) => setError(e.message),
  });

  const delAlias = useMutation({
    mutationFn: (id: number) => api.del(`/api/settings/owner-aliases/${id}`),
    onSuccess: () => qc.invalidateQueries(),
  });

  const saveSettings = useMutation({
    mutationFn: (values: Record<string, string>) => api.patch("/api/settings", { values }),
    onSuccess: () => {
      setFlash("تنظیمات ذخیره شد.");
      qc.invalidateQueries();
    },
  });

  const recategorize = useMutation({
    mutationFn: () => api.post<{ updated: number }>("/api/settings/recategorize"),
    onSuccess: (res) => {
      setFlash(`${faDigits(res.updated)} تراکنش دوباره دسته‌بندی شد.`);
      qc.invalidateQueries();
    },
  });

  return (
    <>
      <PageHeader title="تنظیمات" />

      {flash && (
        <div className="mb-3 rounded-lg border border-gain/30 bg-gain-soft px-3.5 py-2.5 text-sm text-gain">
          {flash}
        </div>
      )}
      {error && (
        <div className="mb-3">
          <ErrorBox message={error} />
        </div>
      )}

      {/* --------- حساب‌های من --------- */}
      <section className="mb-6">
        <h2 className="mb-2 text-sm font-semibold">حساب‌های بانکی</h2>
        {accounts.isLoading ? (
          <Loading />
        ) : !accounts.data?.length ? (
          <Empty title="هنوز حسابی ثبت نشده." hint="با ورود اولین فایل اکسل ساخته می‌شود." />
        ) : (
          <div className="card scroll-x">
            <table className="w-full min-w-[40rem]">
              <thead className="border-b border-border bg-surface-raised">
                <tr>
                  <th className="th">حساب</th>
                  <th className="th">شبا</th>
                  <th className="th">صاحب حساب</th>
                  <th className="th">تراکنش</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {accounts.data.map((a) => (
                  <tr key={a.id}>
                    <td className="td">
                      <div className="font-medium">{a.bank_label}</div>
                      <div className="text-[11px] tnum text-text-mute">
                        {a.account_number}
                      </div>
                    </td>
                    <td className="td font-mono text-xs" dir="ltr">
                      {a.iban}
                    </td>
                    <td className="td">{a.owner_name ?? "—"}</td>
                    <td className="td tnum">{faDigits(a.transaction_count)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* --------- خودم --------- */}
      <section className="mb-6">
        <h2 className="mb-1 text-sm font-semibold">حساب‌ها و نام‌های «خودم»</h2>
        <p className="mb-2 text-xs text-text-mute">
          هر انتقالی که طرف مقابلش یکی از این‌ها باشد، هزینه شمرده نمی‌شود. این
          مهم‌ترین تنظیم برنامه است — بدون آن، جابه‌جایی پول بین حساب‌های خودت
          مثل خرج دیده می‌شود.
        </p>

        <form
          className="card card-pad mb-3 flex flex-wrap items-end gap-3"
          onSubmit={(e) => {
            e.preventDefault();
            if (value.trim()) addAlias.mutate({ kind, value: value.trim() });
          }}
        >
          <div className="min-w-[9rem]">
            <label className="label">نوع</label>
            <select className="input" value={kind} onChange={(e) => setKind(e.target.value)}>
              {ALIAS_KINDS.map((k) => (
                <option key={k.value} value={k.value}>
                  {k.label}
                </option>
              ))}
            </select>
          </div>
          <div className="min-w-[14rem] flex-1">
            <label className="label">مقدار</label>
            <input
              className="input"
              value={value}
              onChange={(e) => setValue(e.target.value)}
              placeholder={kind === "name" ? "نام و نام خانوادگی" : "شماره"}
              dir={kind === "name" ? undefined : "ltr"}
            />
          </div>
          <button className="btn-primary" disabled={addAlias.isPending}>
            افزودن
          </button>
        </form>

        <div className="flex flex-wrap gap-2">
          {(aliases.data ?? []).map((a) => (
            <span
              key={a.id}
              className="chip bg-surface-raised py-1 text-text-soft"
              title={a.note ?? ""}
            >
              <span className="text-[10px] text-text-mute">
                {ALIAS_KINDS.find((k) => k.value === a.kind)?.label}
              </span>
              <span className={a.kind === "name" ? "" : "font-mono text-[11px]"} dir={a.kind === "name" ? undefined : "ltr"}>
                {a.value}
              </span>
              <button
                className="text-loss hover:text-loss"
                onClick={() => delAlias.mutate(a.id)}
              >
                ×
              </button>
            </span>
          ))}
        </div>
      </section>

      {/* --------- آستانه --------- */}
      <section className="mb-6">
        <h2 className="mb-2 text-sm font-semibold">آستانهٔ خردخرجی</h2>
        <form
          className="card card-pad flex flex-wrap items-end gap-3"
          onSubmit={(e) => {
            e.preventDefault();
            const rial = parseTomanInput(threshold);
            if (rial)
              saveSettings.mutate({ micro_spend_threshold_rial: String(rial) });
          }}
        >
          <div className="min-w-[12rem] flex-1">
            <label className="label">
              تراکنش‌های کوچک‌تر از این مبلغ «خردخرجی» شمرده می‌شوند (تومان)
            </label>
            <input
              className="input tnum"
              dir="ltr"
              value={threshold}
              onChange={(e) => setThreshold(e.target.value)}
              placeholder={
                settings.data
                  ? toman(Number(settings.data.micro_spend_threshold_rial ?? 0))
                  : "۱۰۰۰۰۰"
              }
            />
          </div>
          <button className="btn-primary">ذخیره</button>
        </form>
      </section>




      {/* --------- رمز ورود --------- */}
      <section>
        <h2 className="mb-2 text-sm font-semibold">رمز ورود</h2>
        <form
          className="card card-pad"
          onSubmit={(e) => {
            e.preventDefault();
            if (pw.next !== pw.confirm) {
              setPwError("رمز تازه و تکرارش یکی نیستند.");
              return;
            }
            setPwError("");
            changePassword.mutate({ current_password: pw.current, new_password: pw.next });
          }}
        >
          <div className="flex flex-wrap gap-3">
            {(
              [
                ["current", "رمز فعلی"],
                ["next", "رمز تازه"],
                ["confirm", "تکرار رمز تازه"],
              ] as const
            ).map(([key, label]) => (
              <div className="min-w-[11rem] flex-1" key={key}>
                <label className="label" htmlFor={`pw-${key}`}>
                  {label}
                </label>
                <input
                  id={`pw-${key}`}
                  type="password"
                  className="input"
                  autoComplete={key === "current" ? "current-password" : "new-password"}
                  value={pw[key]}
                  onChange={(e) => setPw((v) => ({ ...v, [key]: e.target.value }))}
                />
              </div>
            ))}
          </div>
          {pwError && (
            <div className="mt-3">
              <ErrorBox message={pwError} />
            </div>
          )}
          {pwDone && (
            <p className="mt-3 text-xs text-gain">رمز عوض شد. دفعهٔ بعد با رمز تازه وارد شو.</p>
          )}
          <button
            className="btn-primary mt-3"
            disabled={changePassword.isPending || !pw.current || !pw.next}
          >
            <KeyRound size={15} aria-hidden />
            تغییر رمز
          </button>
          <p className="mt-2 text-[11px] text-text-mute">
            رمز دست‌کم ۸ نویسه. به‌صورت هش‌شده ذخیره می‌شود و هیچ‌جا به شکل خام نگه
            داشته نمی‌شود.
          </p>
        </form>
      </section>

      {/* --------- سرویس قیمت --------- */}
      <section>
        <h2 className="mb-2 text-sm font-semibold">سرویس قیمت طلا و ارز</h2>
        <div className="card card-pad">
          <p className="mb-3 text-xs text-text-mute">
            BrsApi رایگان است و روزی ۱۵۰۰ درخواست می‌دهد. کلید رایگانش را از{" "}
            <span className="font-mono" dir="ltr">
              api.brsapi.ir
            </span>{" "}
            بگیر و همین‌جا واردش کن — نیازی به دست‌زدن به فایل یا بالا و پایین کردن
            برنامه نیست.
          </p>

          <div className="flex flex-wrap items-end gap-3">
            <div className="min-w-[11rem]">
              <label className="label" htmlFor="mkt-provider">
                سرویس
              </label>
              <select
                id="mkt-provider"
                className="input"
                value={market.data?.market_provider ?? "brsapi"}
                onChange={(e) => saveMarket.mutate({ provider: e.target.value })}
              >
                {(market.data?.providers ?? []).map((p) => (
                  <option key={p.name} value={p.name}>
                    {p.label_fa}
                  </option>
                ))}
              </select>
            </div>

            <div className="min-w-[14rem] flex-1">
              <label className="label" htmlFor="mkt-key">
                کلید {market.data?.market_provider === "navasan" ? "نوسان" : "BrsApi"}
                {keyIsSet && (
                  <span className="ms-2 font-normal text-gain">
                    ثبت شده ({keyHint})
                  </span>
                )}
              </label>
              <input
                id="mkt-key"
                className="input font-mono"
                dir="ltr"
                placeholder={keyIsSet ? "برای تغییر، کلید تازه را بنویس" : "کلید را اینجا بچسبان"}
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
              />
            </div>

            <button
              className="btn-primary"
              disabled={saveMarket.isPending || !apiKey.trim()}
              onClick={() =>
                saveMarket.mutate(
                  market.data?.market_provider === "navasan"
                    ? { navasan_key: apiKey.trim() }
                    : { brsapi_key: apiKey.trim() },
                )
              }
            >
              ذخیرهٔ کلید
            </button>

            {keyIsSet && (
              <button
                className="btn-ghost"
                onClick={() =>
                  saveMarket.mutate(
                    market.data?.market_provider === "navasan"
                      ? { navasan_key: "" }
                      : { brsapi_key: "" },
                  )
                }
              >
                حذف کلید
              </button>
            )}
          </div>
        </div>
      </section>

      {/* --------- تم رنگی --------- */}
      <section>
        <h2 className="mb-2 text-sm font-semibold">تم رنگی</h2>
        <div className="card card-pad">
          <p className="mb-3 text-xs text-text-mute">
            هر تم در حالت روشن و تیره کار می‌کند. سبز برای درآمد و قرمز برای هزینه در
            همهٔ تم‌ها ثابت می‌ماند، چون معنا دارند نه سلیقه.
          </p>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            {PALETTES.map((p) => (
              <button
                key={p.id}
                onClick={() => setPalette(p.id)}
                aria-pressed={palette === p.id}
                className={`flex items-center gap-2.5 rounded-lg border px-3 py-2.5 text-right text-sm transition ${
                  palette === p.id
                    ? "border-brand bg-brand-soft font-semibold text-brand-text"
                    : "border-border hover:border-border-strong"
                }`}
              >
                <span
                  className="size-5 shrink-0 rounded-full border border-black/10"
                  style={{ background: p.swatch }}
                  aria-hidden
                />
                <span className="truncate">{p.label}</span>
              </button>
            ))}
          </div>

          <div className="mt-4 border-t border-border pt-3">
            <div className="label">حالت نمایش</div>
            <div className="flex gap-2">
              {(
                [
                  ["light", "روشن"],
                  ["dark", "تیره"],
                  ["system", "مثل سیستم"],
                ] as const
              ).map(([value, label]) => (
                <button
                  key={value}
                  onClick={() => setMode(value)}
                  aria-pressed={mode === value}
                  className={mode === value ? "btn-primary !py-1 text-xs" : "btn-ghost !py-1 text-xs"}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* --------- پشتیبان‌گیری --------- */}
      <section>
        <h2 className="mb-2 text-sm font-semibold">پشتیبان‌گیری</h2>
        <div className="card card-pad">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="max-w-xl text-xs text-text-mute">
              هر پشتیبان شامل کل دیتابیس و فایل‌های خام است — صورتحساب‌های اکسل و
              اسکرین‌شات رسیدها. بدون فایل‌ها بازیابی ناقص می‌شود.
              ده پشتیبان آخر نگه داشته می‌شود.
            </p>
            <button
              className="btn-primary"
              onClick={() => makeBackup.mutate()}
              disabled={makeBackup.isPending}
            >
              <Database size={15} aria-hidden />
              {makeBackup.isPending ? "در حال ساخت…" : "پشتیبان بگیر"}
            </button>
          </div>

          {backups.data?.length ? (
            <div className="mt-3 divide-y divide-border border-t border-border">
              {backups.data.map((b) => (
                <div key={b.name} className="flex flex-wrap items-center gap-3 py-2.5">
                  <div className="min-w-[9rem] flex-1">
                    <div className="text-sm font-medium tnum">{jalaliDate(b.created_jalali)}</div>
                    <div className="text-[11px] tnum text-text-mute">
                      {b.name} · {faDigits((b.size_bytes / 1048576).toFixed(1))} مگابایت
                    </div>
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {b.files.map((f) => (
                      <a
                        key={f}
                        className="btn-ghost !py-1 text-[11px]"
                        href={`/api/settings/backups/${b.name}/${f}`}
                      >
                        <Download size={13} aria-hidden />
                        {f.startsWith("database") ? "دیتابیس" : "فایل‌ها"}
                      </a>
                    ))}
                    <button
                      className="btn-icon text-loss"
                      aria-label={`حذف پشتیبان ${b.name}`}
                      onClick={() => removeBackup.mutate(b.name)}
                    >
                      <Trash2 size={15} aria-hidden />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="mt-3 border-t border-border pt-3 text-xs text-text-mute">
              هنوز پشتیبانی گرفته نشده.
            </p>
          )}
        </div>
      </section>

      {/* --------- ابزار --------- */}
      <section>
        <h2 className="mb-2 text-sm font-semibold">ابزارها</h2>
        <div className="card card-pad">
          <button
            className="btn-ghost"
            onClick={() => recategorize.mutate()}
            disabled={recategorize.isPending}
          >
            {recategorize.isPending ? "…" : "دسته‌بندی دوبارهٔ همهٔ تراکنش‌ها"}
          </button>
          <p className="mt-2 text-[11px] text-text-mute">
            بعد از تغییر قوانین یا فروشنده‌ها، این را بزن تا گذشته هم به‌روز شود.
            برچسب‌های دستی دست‌نخورده می‌مانند.
          </p>
        </div>
      </section>
    </>
  );
}
