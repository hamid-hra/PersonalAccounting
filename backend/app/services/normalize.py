"""
نرمال‌سازی متن فارسی.

فایل‌های بانکی یک اسم را با دو کدگذاری متفاوت می‌نویسند — در نمونهٔ واقعی
«سعیده قادری» و «ﺳﻌﯾدﻩ ﻗﺎدرﯼ» (Arabic presentation forms) کنار هم بودند و
بدون نرمال‌سازی دو شخص جدا شمرده می‌شدند.

دو تابع جدا داریم چون دو کار متفاوت‌اند:
  normalize() — امن برای نمایش؛ فقط چیزهایی را یکسان می‌کند که غلط املایی‌اند.
  fold()      — کلید تطبیق؛ آ/ا و ه/ة را هم یکی می‌کند و برای نمایش مناسب نیست.
"""

import re
import unicodedata

# اصلاح‌های امن برای نمایش: حروف عربی که در فارسی غلط‌اند
_DISPLAY_MAP = {
    "ي": "ی",  # YEH عربی
    "ى": "ی",  # ALEF MAKSURA
    "ك": "ک",  # KAF عربی
    "ڪ": "ک",
}

# فولدینگ تهاجمی — فقط برای تطبیق
_FOLD_MAP = {
    "آ": "ا",
    "أ": "ا",
    "إ": "ا",
    "ٱ": "ا",
    "ة": "ه",
    "ۀ": "ه",
    "ؤ": "و",
    "ئ": "ی",
}

# ارقام فارسی و عربی → لاتین
_DIGIT_MAP = {chr(0x06F0 + i): str(i) for i in range(10)} | {
    chr(0x0660 + i): str(i) for i in range(10)
}

# اعراب، تطویل، و نویسه‌های نامرئی/جهت‌دهنده
_STRIP_RE = re.compile("[ً-ْٰـ​-‏‪-‮﻿­]")
_ZWNJ = "‌"
_SPACE_RE = re.compile(r"\s+")

_TRANS_DISPLAY = str.maketrans(_DISPLAY_MAP | _DIGIT_MAP)
_TRANS_FOLD = str.maketrans(_FOLD_MAP)
_TRANS_DIGITS = str.maketrans(_DIGIT_MAP)


def fa_digits(text: str | None) -> str:
    """فقط ارقام فارسی/عربی را به لاتین تبدیل می‌کند، بدون دست‌زدن به حروف."""
    if not text:
        return ""
    return text.translate(_TRANS_DIGITS)


def normalize(text: str | None) -> str:
    """
    متن را تمیز و یکدست می‌کند بدون آنکه برای نمایش خراب شود:
    NFKC (باز کردن presentation forms) → ی/ک فارسی → ارقام لاتین
    → حذف اعراب و نویسه‌های نامرئی → یکسان‌سازی فاصله.
    """
    if not text:
        return ""
    out = unicodedata.normalize("NFKC", text)
    out = out.translate(_TRANS_DISPLAY)
    out = out.replace(_ZWNJ, " ")
    out = _STRIP_RE.sub("", out)
    return _SPACE_RE.sub(" ", out).strip()


def fold(text: str | None) -> str:
    """کلید تطبیق: normalize + یکسان‌سازی آ/ا، ه/ة، ئ/ی. برای نمایش استفاده نشود."""
    return normalize(text).translate(_TRANS_FOLD).lower()


def fold_name(name: str | None) -> str:
    """کلید تطبیق نام اشخاص — پیشوندهای احترام حذف می‌شوند."""
    out = fold(name)
    out = re.sub(r"^(?:اقای|خانم|جناب|سرکار|شرکت)\s+", "", out)
    return out.strip()


def fold_name_key(name: str | None) -> str:
    """
    کلید تطبیق نام، بی‌اعتنا به ترتیب کلمه‌ها.

    بانک‌ها یک نفر را به دو ترتیب می‌نویسند: بانک سامان «علی رضایی» و
    بانک ملی «رضایی علی». روی دادهٔ واقعی این ۱۵ تراکنش (۹٬۳۵۰٬۰۰۰ تومان)
    از پولِ خودِ کاربر را «درآمد» نشان می‌داد. توکن‌ها مرتب می‌شوند تا هر دو
    ترتیب به یک کلید برسند.
    """
    tokens = [t for t in fold_name(name).split() if t]
    return " ".join(sorted(tokens))


def digits_only(text: str | None) -> str:
    """فقط رقم‌ها را نگه می‌دارد — برای شماره کارت/سپرده/تلفن."""
    return re.sub(r"\D", "", fa_digits(text or ""))
