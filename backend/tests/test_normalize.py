from app.services.normalize import digits_only, fa_digits, fold, fold_name, normalize


def test_presentation_forms_resolve_to_same_name():
    """
    در فایل واقعی، یک نفر با دو کدگذاری نوشته شده بود و بدون این تبدیل
    دو ردیف جدا با نصف مبلغ نشان داده می‌شد.
    """
    assert normalize("ﺳﻌﯾدﻩ ﻗﺎدرﯼ") == "سعیده قادری"
    assert fold_name("ﺳﻌﯾدﻩ ﻗﺎدرﯼ") == fold_name("سعیده قادری")


def test_arabic_letters_normalized():
    assert normalize("على رضايى") == "علی رضایی"
    assert fold_name("على رضايى") == fold_name("علی رضایی")


def test_normalize_keeps_alef_madda_for_display():
    """آ نباید در نمایش به ا تبدیل شود، ولی در کلید تطبیق یکی می‌شوند."""
    assert normalize("آرش شکری") == "آرش شکری"
    assert fold("آرش شکری") == fold("ارش شكرى")


def test_digits():
    assert fa_digits("۰۹۱۲۰۰۰۰۰۰۰") == "09120000000"
    assert digits_only("شماره: ۱۲۳-۴۵۶") == "123456"


def test_honorific_stripped():
    assert fold_name("آقای محمد رضایی") == fold_name("محمد رضایی")


def test_empty_input():
    assert normalize(None) == ""
    assert fold("") == ""


def test_name_key_ignores_word_order():
    """
    بانک سامان «علی رضایی» می‌نویسد و بانک ملی «رضایی علی».
    بدون این، ۱۵ تراکنش از پولِ خود کاربر «درآمد» شمرده می‌شد.
    """
    from app.services.normalize import fold_name_key

    assert fold_name_key("علی رضایی") == fold_name_key("رضایی علی")
    assert fold_name_key("رضایی علی") == fold_name_key("على رضايى")
    # آدم دیگری با نام مشابه نباید یکی شود
    assert fold_name_key("محمدعلی رضایی") != fold_name_key("علی رضایی")
