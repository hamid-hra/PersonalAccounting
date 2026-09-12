import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { api } from "../lib/api";
import { ErrorBox } from "../components/ui";

const MIN_LENGTH = 8;

/**
 * دروازهٔ ورود.
 *
 * اولین بار که برنامه بالا می‌آید هیچ رمزی وجود ندارد → «ساخت حساب».
 * بعد از آن سرور ساخت حساب دوباره را رد می‌کند و فقط «ورود» نشان داده می‌شود.
 */
export default function Login({ onSuccess }: { onSuccess: () => void }) {
  const status = useQuery({
    queryKey: ["auth-status"],
    queryFn: () => api.get<{ setup_required: boolean }>("/api/auth/status"),
    retry: false,
  });

  if (status.isLoading) {
    return (
      <div className="grid min-h-screen place-items-center bg-surface-raised text-text-mute">
        در حال بارگذاری…
      </div>
    );
  }

  const setup = status.data?.setup_required === true;
  return setup ? (
    <SetupForm onSuccess={onSuccess} />
  ) : (
    <LoginForm onSuccess={onSuccess} onNeedsSetup={() => status.refetch()} />
  );
}

function Frame({ title, intro, children }: { title: string; intro: string; children: React.ReactNode }) {
  return (
    <div className="grid min-h-screen place-items-center bg-surface-raised p-4">
      <div className="card card-pad w-full max-w-sm">
        <h1 className="text-lg font-bold">{title}</h1>
        <p className="mt-1 text-sm text-text-mute">{intro}</p>
        {children}
      </div>
    </div>
  );
}

function SetupForm({ onSuccess }: { onSuccess: () => void }) {
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const tooShort = password.length > 0 && password.length < MIN_LENGTH;
  const mismatch = confirm.length > 0 && confirm !== password;
  const canSubmit = password.length >= MIN_LENGTH && confirm === password && !busy;

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!canSubmit) return;
    setBusy(true);
    setError("");
    try {
      await api.post("/api/auth/setup", { password });
      onSuccess();
    } catch (err) {
      setError(err instanceof Error ? err.message : "ساخت حساب ناموفق بود.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Frame
      title="ساخت حساب مالک"
      intro="این اولین اجرای برنامه است. رمزی بگذار که از این پس فقط با آن بشود وارد شد."
    >
      <form onSubmit={submit}>
        <label className="label mt-5" htmlFor="setup-pw">
          رمز عبور
        </label>
        <input
          id="setup-pw"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="input"
          autoComplete="new-password"
          autoFocus
          dir="ltr"
        />
        {tooShort && (
          <p className="mt-1 text-[11px] text-loss">دست‌کم {MIN_LENGTH} نویسه.</p>
        )}

        <label className="label mt-3" htmlFor="setup-pw2">
          تکرار رمز عبور
        </label>
        <input
          id="setup-pw2"
          type="password"
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
          className="input"
          autoComplete="new-password"
          dir="ltr"
        />
        {mismatch && <p className="mt-1 text-[11px] text-loss">دو رمز یکی نیستند.</p>}

        {error && (
          <div className="mt-3">
            <ErrorBox message={error} />
          </div>
        )}

        <button type="submit" disabled={!canSubmit} className="btn-primary mt-4 w-full">
          {busy ? "در حال ساخت…" : "ساخت حساب و ورود"}
        </button>
        <p className="mt-4 text-[11px] leading-5 text-text-mute">
          این صفحه فقط یک بار نشان داده می‌شود. رمز به‌صورت هش‌شده ذخیره می‌شود و راه
          بازیابی ندارد؛ جایی امن نگهش دار. (اگر فراموش شد، از خط فرمان سرور:
          <code dir="ltr" className="mx-1">python -m app.reset_password</code>)
        </p>
      </form>
    </Frame>
  );
}

function LoginForm({ onSuccess, onNeedsSetup }: { onSuccess: () => void; onNeedsSetup: () => void }) {
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api.post("/api/auth/login", { password });
      onSuccess();
    } catch (err) {
      // ۴۰۹ یعنی هنوز حسابی ساخته نشده (مثلاً بعد از reset_password)
      if (err && typeof err === "object" && "status" in err && err.status === 409) {
        onNeedsSetup();
        return;
      }
      setError(err instanceof Error ? err.message : "ورود ناموفق بود.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Frame title="حسابداری شخصی" intro="برای دیدن اطلاعات مالی، رمز عبور را وارد کن.">
      <form onSubmit={submit}>
        <label className="label mt-5" htmlFor="login-pw">
          رمز عبور
        </label>
        <input
          id="login-pw"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="input"
          autoComplete="current-password"
          autoFocus
          dir="ltr"
        />

        {error && (
          <div className="mt-3">
            <ErrorBox message={error} />
          </div>
        )}

        <button type="submit" disabled={busy || !password} className="btn-primary mt-4 w-full">
          {busy ? "در حال بررسی…" : "ورود"}
        </button>
        <p className="mt-4 text-[11px] leading-5 text-text-mute">
          بعد از چند تلاش ناموفق، ورود موقتاً قفل می‌شود. رمز را از صفحهٔ تنظیمات می‌توانی
          عوض کنی.
        </p>
      </form>
    </Frame>
  );
}
