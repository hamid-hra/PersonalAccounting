/**
 * قالب‌بندی عدد و تاریخ.
 *
 * در دیتابیس همه‌چیز ریالِ صحیح ذخیره می‌شود تا خطای اعشار نداشته باشیم؛
 * اینجا به تومان تبدیل و با ارقام فارسی نمایش داده می‌شود.
 */

const FA = new Intl.NumberFormat("fa-IR", { maximumFractionDigits: 0 });
const FA_SIGNED = new Intl.NumberFormat("fa-IR", {
  maximumFractionDigits: 0,
  signDisplay: "never",
});

/** ریال → تومان */
export const toToman = (rial: number) => Math.round(rial / 10);

/** «۱٬۲۳۴٬۵۶۷» */
export const toman = (rial: number) => FA.format(toToman(rial));

/** «۱٬۲۳۴٬۵۶۷ تومان» */
export const tomanUnit = (rial: number) => `${toman(rial)} تومان`;

/** بدون علامت منفی — وقتی جهت با رنگ نشان داده می‌شود */
export const tomanAbs = (rial: number) => FA_SIGNED.format(toToman(Math.abs(rial)));

/** خلاصهٔ مبالغ بزرگ برای نمودار و کارت: «۱۲٫۴ م» */
export function tomanShort(rial: number): string {
  const t = Math.abs(toToman(rial));
  const sign = rial < 0 ? "−" : "";
  if (t >= 1_000_000_000) return `${sign}${FA.format(Math.round(t / 100_000_000) / 10)} میلیارد`;
  if (t >= 1_000_000) return `${sign}${FA.format(Math.round(t / 100_000) / 10)} م`;
  if (t >= 1_000) return `${sign}${FA.format(Math.round(t / 1_000))} هزار`;
  return `${sign}${FA.format(t)}`;
}

export const num = (n: number) => FA.format(n);
export const percent = (ratio: number) => `${FA.format(Math.round(ratio * 100))}٪`;

/** ارقام فارسی/عربی ورودی کاربر → لاتین، برای ارسال به سرور */
export function latinDigits(input: string): string {
  return input
    .replace(/[۰-۹]/g, (d) => String(d.charCodeAt(0) - 0x06f0))
    .replace(/[٠-٩]/g, (d) => String(d.charCodeAt(0) - 0x0660));
}

/** رشتهٔ مبلغِ تومانِ کاربر → ریالِ صحیح */
export function parseTomanInput(input: string): number | null {
  const clean = latinDigits(input).replace(/[,٬\s]/g, "");
  if (!clean || !/^\d+$/.test(clean)) return null;
  return Number(clean) * 10;
}

/** «1405/06/10 18:42:09» → «۱۴۰۵/۰۶/۱۰» */
export function jalaliDate(value?: string | null): string {
  if (!value) return "—";
  const date = value.split(" ")[0];
  return date.replace(/\d/g, (d) => "۰۱۲۳۴۵۶۷۸۹"[Number(d)]);
}

/** «1405/06/10 18:42:09» → «۱۸:۴۲» */
export function jalaliTime(value?: string | null): string {
  if (!value) return "";
  const time = value.split(" ")[1];
  if (!time) return "";
  return time.slice(0, 5).replace(/\d/g, (d) => "۰۱۲۳۴۵۶۷۸۹"[Number(d)]);
}

export const faDigits = (s: string | number) =>
  String(s).replace(/\d/g, (d) => "۰۱۲۳۴۵۶۷۸۹"[Number(d)]);

export const MONTHS_FA = [
  "فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
  "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند",
];
