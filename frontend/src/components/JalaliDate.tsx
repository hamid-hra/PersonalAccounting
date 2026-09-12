import { CalendarDays, ChevronLeft, ChevronRight } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import {
  MONTHS_FA,
  WEEKDAYS_FA,
  firstWeekday,
  formatJalali,
  monthLength,
  parseJalali,
  todayJalali,
} from "../lib/jalali";
import { faDigits } from "../lib/format";

/*
  انتخابگر تاریخ جلالی.

  تایپ دستی («۱۴۰۵/۰۱/۱۰» یا 1405-1-10) همچنان کار می‌کند — چیزی که
  کاربر بلد بود نباید از کار بیفتد؛ تقویم فقط راه دوم است.

  مقدار بیرونی همیشه رشتهٔ «YYYY/MM/DD» است تا با بک‌اند یکی باشد.
*/

export default function JalaliDate({
  value,
  onChange,
  id,
  placeholder = "۱۴۰۵/۰۱/۱۰",
  disabled,
}: {
  value: string;
  onChange: (v: string) => void;
  id?: string;
  placeholder?: string;
  disabled?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState(value);
  const [shift, setShift] = useState(0);
  const boxRef = useRef<HTMLDivElement>(null);
  const popRef = useRef<HTMLDivElement>(null);

  useEffect(() => setDraft(value), [value]);

  // ماهی که تقویم نشان می‌دهد: ماه مقدار فعلی، وگرنه ماه جاری
  const parsed = useMemo(() => parseJalali(value), [value]);
  const today = useMemo(() => todayJalali(), []);
  const [view, setView] = useState(() => ({
    jy: parsed?.jy ?? today.jy,
    jm: parsed?.jm ?? today.jm,
  }));
  useEffect(() => {
    if (parsed) setView({ jy: parsed.jy, jm: parsed.jm });
  }, [parsed?.jy, parsed?.jm]);

  /*
    نگه‌داشتن تقویم داخل صفحه.

    در چیدمان راست‌به‌چپ، پاپ‌آور از لبهٔ راستِ فیلد به سمت چپ باز می‌شود؛
    اگر فیلد نزدیک لبهٔ چپ صفحه باشد بیرون می‌زند و کل صفحه را افقی می‌لغزاند.
    پس بعد از باز شدن اندازه‌اش را می‌سنجیم و فقط به‌اندازهٔ لازم جابه‌جا می‌کنیم.
  */
  useEffect(() => {
    if (!open) {
      setShift(0);
      return;
    }
    const el = popRef.current;
    if (!el) return;
    const margin = 8;
    const r = el.getBoundingClientRect();
    const base = r.left - shift; // موقعیت بدون جابه‌جایی قبلی
    let next = 0;
    if (base < margin) next = margin - base;
    else if (base + r.width > window.innerWidth - margin)
      next = window.innerWidth - margin - (base + r.width);
    if (next !== shift) setShift(next);
  }, [open, shift]);

  // بستن با کلیک بیرون و Esc
  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (boxRef.current && !boxRef.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const commitDraft = (text: string) => {
    setDraft(text);
    const p = parseJalali(text);
    if (p) onChange(formatJalali(p.jy, p.jm, p.jd));
    else if (text.trim() === "") onChange("");
  };

  const shiftMonth = (delta: number) => {
    setView((v) => {
      const total = v.jy * 12 + (v.jm - 1) + delta;
      return { jy: Math.floor(total / 12), jm: (total % 12) + 1 };
    });
  };

  const pick = (day: number) => {
    onChange(formatJalali(view.jy, view.jm, day));
    setOpen(false);
  };

  const days = monthLength(view.jy, view.jm);
  const lead = firstWeekday(view.jy, view.jm);
  const isSelected = (d: number) =>
    parsed && parsed.jy === view.jy && parsed.jm === view.jm && parsed.jd === d;
  const isToday = (d: number) =>
    today.jy === view.jy && today.jm === view.jm && today.jd === d;

  return (
    <div className="relative" ref={boxRef}>
      <div className="flex items-stretch gap-1">
        <input
          id={id}
          className="input tnum"
          dir="ltr"
          disabled={disabled}
          placeholder={placeholder}
          value={faDigits(draft)}
          onChange={(e) => commitDraft(e.target.value)}
          onFocus={() => setOpen(true)}
        />
        <button
          type="button"
          className="btn-icon shrink-0 border border-border-strong"
          disabled={disabled}
          aria-label="باز کردن تقویم"
          aria-expanded={open}
          onClick={() => setOpen((v) => !v)}
        >
          <CalendarDays size={16} aria-hidden />
        </button>
      </div>

      {open && (
        <div
          ref={popRef}
          role="dialog"
          aria-label="انتخاب تاریخ"
          style={{ transform: `translateX(${shift}px)`, width: "min(17.5rem, calc(100vw - 1.5rem))" }}
          className="absolute z-30 mt-1 rounded-xl border border-border bg-surface p-3 shadow-lg"
        >
          <div className="mb-2 flex items-center justify-between">
            <button
              type="button"
              className="btn-icon"
              aria-label="ماه بعد"
              onClick={() => shiftMonth(1)}
            >
              <ChevronLeft size={16} aria-hidden />
            </button>
            <div className="text-sm font-semibold tnum">
              {MONTHS_FA[view.jm - 1]} {faDigits(view.jy)}
            </div>
            <button
              type="button"
              className="btn-icon"
              aria-label="ماه قبل"
              onClick={() => shiftMonth(-1)}
            >
              <ChevronRight size={16} aria-hidden />
            </button>
          </div>

          <div className="mb-1 grid grid-cols-7 gap-0.5">
            {WEEKDAYS_FA.map((w, i) => (
              <div
                key={i}
                className="grid h-7 place-items-center text-[11px] font-medium text-text-mute"
              >
                {w}
              </div>
            ))}
          </div>

          <div className="grid grid-cols-7 gap-0.5">
            {Array.from({ length: lead }).map((_, i) => (
              <div key={`lead-${i}`} />
            ))}
            {Array.from({ length: days }).map((_, i) => {
              const d = i + 1;
              const selected = isSelected(d);
              return (
                <button
                  type="button"
                  key={d}
                  onClick={() => pick(d)}
                  aria-label={`${d} ${MONTHS_FA[view.jm - 1]} ${view.jy}`}
                  aria-current={selected ? "date" : undefined}
                  className={`grid h-8 place-items-center rounded-md text-xs tnum transition-colors ${
                    selected
                      ? "bg-brand font-bold text-brand-fg"
                      : isToday(d)
                        ? "bg-brand-soft font-semibold text-brand-text"
                        : "hover:bg-surface-raised"
                  }`}
                >
                  {faDigits(d)}
                </button>
              );
            })}
          </div>

          <div className="mt-2 flex justify-between border-t border-border pt-2">
            <button
              type="button"
              className="btn-ghost !py-1 text-xs"
              onClick={() => {
                onChange(formatJalali(today.jy, today.jm, today.jd));
                setOpen(false);
              }}
            >
              امروز
            </button>
            <button
              type="button"
              className="btn-ghost !py-1 text-xs"
              onClick={() => {
                onChange("");
                setDraft("");
                setOpen(false);
              }}
            >
              پاک کردن
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
