import { useState } from "react";

import { api } from "../lib/api";
import { ErrorBox } from "../components/ui";

export default function Login({ onSuccess }: { onSuccess: () => void }) {
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
      setError(err instanceof Error ? err.message : "ورود ناموفق بود.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="grid min-h-screen place-items-center bg-surface-raised p-4">
      <form onSubmit={submit} className="card card-pad w-full max-w-sm">
        <h1 className="text-lg font-bold">حسابداری شخصی</h1>
        <p className="mt-1 text-sm text-text-mute">
          برای دیدن اطلاعات مالی، رمز عبور را وارد کن.
        </p>

        <label className="label mt-5">رمز عبور</label>
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="input"
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
          این برنامه فقط روی همین رایانه اجرا می‌شود و داده‌ها جایی ارسال نمی‌شوند.
          بعد از ورود می‌توانی رمز را از صفحهٔ تنظیمات عوض کنی.
        </p>
      </form>
    </div>
  );
}
