/*
  تبدیل تقویم جلالی ↔ میلادی.

  الگوریتم استاندارد خیام–بیرشک (همان که jalaali-js پیاده می‌کند) مستقیم
  اینجا نوشته شده تا وابستگی تازه‌ای اضافه نشود؛ حدود ۵۰ خط حساب صحیح است
  و برای بازهٔ ۱۱۷۸ تا ۱۶۳۳ جلالی دقیق است.

  چرا Intl استفاده نشد: `Intl` تبدیل میلادی→جلالی را می‌دهد ولی مسیر
  برعکس (که برای انتخاب روز از تقویم لازم است) را نه.
*/

const BREAKS = [
  -61, 9, 38, 199, 426, 686, 756, 818, 1111, 1181, 1210,
  1635, 2060, 2097, 2192, 2262, 2324, 2394, 2456, 3178,
];

const div = (a: number, b: number) => Math.trunc(a / b);
const mod = (a: number, b: number) => a - Math.trunc(a / b) * b;

function jalCal(jy: number) {
  const bl = BREAKS.length;
  const gy = jy + 621;
  let leapJ = -14;
  let jp = BREAKS[0];
  let jm = 0;
  let jump = 0;

  if (jy < jp || jy >= BREAKS[bl - 1]) throw new Error(`سال جلالی نامعتبر: ${jy}`);

  for (let i = 1; i < bl; i += 1) {
    jm = BREAKS[i];
    jump = jm - jp;
    if (jy < jm) break;
    leapJ = leapJ + div(jump, 33) * 8 + div(mod(jump, 33), 4);
    jp = jm;
  }
  let n = jy - jp;

  leapJ = leapJ + div(n, 33) * 8 + div(mod(n, 33) + 3, 4);
  if (mod(jump, 33) === 4 && jump - n === 4) leapJ += 1;

  const leapG = div(gy, 4) - div((div(gy, 100) + 1) * 3, 4) - 150;
  const march = 20 + leapJ - leapG;

  if (jump - n < 6) n = n - jump + div(jump + 4, 33) * 33;
  let leap = mod(mod(n + 1, 33) - 1, 4);
  if (leap === -1) leap = 4;

  return { leap, gy, march };
}

function g2d(gy: number, gm: number, gd: number): number {
  let d =
    div((gy + div(gm - 8, 6) + 100100) * 1461, 4) +
    div(153 * mod(gm + 9, 12) + 2, 5) +
    gd -
    34840408;
  d = d - div(div(gy + 100100 + div(gm - 8, 6), 100) * 3, 4) + 752;
  return d;
}

function d2g(jdn: number) {
  let j = 4 * jdn + 139361631;
  j = j + div(div(4 * jdn + 183187720, 146097) * 3, 4) * 4 - 3908;
  const i = div(mod(j, 1461), 4) * 5 + 308;
  const gd = div(mod(i, 153), 5) + 1;
  const gm = mod(div(i, 153), 12) + 1;
  const gy = div(j, 1461) - 100100 + div(8 - gm, 6);
  return { gy, gm, gd };
}

export function toGregorian(jy: number, jm: number, jd: number) {
  const r = jalCal(jy);
  const jdn = g2d(r.gy, 3, r.march) + (jm - 1) * 31 - div(jm, 7) * (jm - 7) + jd - 1;
  return d2g(jdn);
}

export function toJalali(gy: number, gm: number, gd: number) {
  const jdn = g2d(gy, gm, gd);
  let jy = d2g(jdn).gy - 621;
  const r = jalCal(jy);
  const jdn1f = g2d(r.gy, 3, r.march);
  let k = jdn - jdn1f;

  if (k >= 0) {
    if (k <= 185) return { jy, jm: 1 + div(k, 31), jd: mod(k, 31) + 1 };
    k -= 186;
  } else {
    jy -= 1;
    k += 179;
    if (r.leap === 1) k += 1;
  }
  return { jy, jm: 7 + div(k, 30), jd: mod(k, 30) + 1 };
}

export function isLeapJalali(jy: number): boolean {
  return jalCal(jy).leap === 0;
}

/** تعداد روزهای یک ماه جلالی — اسفند در سال کبیسه ۳۰ روز است. */
export function monthLength(jy: number, jm: number): number {
  if (jm <= 6) return 31;
  if (jm <= 11) return 30;
  return isLeapJalali(jy) ? 30 : 29;
}

/** روز هفتهٔ اول ماه، ۰ = شنبه … ۶ = جمعه */
export function firstWeekday(jy: number, jm: number): number {
  const g = toGregorian(jy, jm, 1);
  const dow = new Date(g.gy, g.gm - 1, g.gd).getDay(); // ۰ = یکشنبه
  return (dow + 1) % 7;
}

export function todayJalali() {
  const now = new Date();
  return toJalali(now.getFullYear(), now.getMonth() + 1, now.getDate());
}

export const MONTHS_FA = [
  "فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
  "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند",
];

export const WEEKDAYS_FA = ["ش", "ی", "د", "س", "چ", "پ", "ج"];

/** «1405/06/13» → {jy,jm,jd} — ارقام فارسی و جداکنندهٔ «-» هم پذیرفته می‌شود. */
export function parseJalali(text: string): { jy: number; jm: number; jd: number } | null {
  const latin = (text || "").replace(/[۰-۹]/g, (d) => String("۰۱۲۳۴۵۶۷۸۹".indexOf(d)));
  const m = latin.match(/^\s*(1[34]\d{2})[/\-.](\d{1,2})[/\-.](\d{1,2})\s*$/);
  if (!m) return null;
  const [jy, jm, jd] = [Number(m[1]), Number(m[2]), Number(m[3])];
  if (jm < 1 || jm > 12 || jd < 1 || jd > monthLength(jy, jm)) return null;
  return { jy, jm, jd };
}

export const formatJalali = (jy: number, jm: number, jd: number) =>
  `${jy}/${String(jm).padStart(2, "0")}/${String(jd).padStart(2, "0")}`;
