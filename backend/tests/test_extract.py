from app.services.extract import clean_amount, extract


def test_pos_terminal():
    e = extract("خرید کالا و خدمات از پایانه فروش 07329842 به پرداخت ملت ش م 357198789431")
    assert e.terminal_id == "07329842"
    assert e.terminal_kind == "pos_terminal"
    assert ("pos_terminal", "07329842") in e.identifier_pairs()


def test_internet_terminal():
    e = extract("خرید کالا و خدمات از اینترنت 06044267 به پرداخت ملت ش م 357056816973")
    assert e.terminal_id == "06044267"
    assert e.terminal_kind == "internet_terminal"


def test_card_transfer_name_and_bank():
    e = extract(
        "انتقال به کارت شماره: 6280231111111111 بنام: رضا محمدی "
        "از درگاه اینترنتی 10000005 بانک سامان - ش م: 178827552928"
    )
    assert e.counterparty_card == "6280231111111111"
    assert e.counterparty_name == "رضا محمدی"
    assert e.counterparty_bank == "سامان"


def test_paya_name_not_polluted_by_bank_word():
    """«بانک پاسارگاد بنام: X» نباید «پاسارگاد بنام» را نام بانک بگیرد."""
    e = extract(
        "انتقال پایا از شماره شبا: IR530570000000000000000123 بانک پاسارگاد "
        "بنام: شرکت نمونه - شماره پیگیری تراکنش: 14050609057242629161"
    )
    assert e.counterparty_iban == "IR530570000000000000000123"
    assert e.counterparty_name == "شرکت نمونه"
    assert e.counterparty_bank == "پاسارگاد"


def test_pol_transfer_without_colon_after_benam():
    e = extract(
        "انتقال پل به شماره شبا: IR640600000000000000000456 بانک مهر ایران "
        "بنام علی رضایی - کد پیگیری تراکنش: 140506032044000750"
    )
    assert e.counterparty_name == "علی رضایی"
    assert e.counterparty_bank == "مهر ایران"


def test_deposit_and_phone_and_loan_and_biller():
    assert extract("انتقال به سپرده بلو - شماره سپرده: 611828000000000009 بنام: سارا کریمی").deposit_no == "611828000000000009"
    assert extract("خرید بستهٔ اینترنتی - شماره تلفن 09120000000 ش م: 1487011002").phone_number == "09120000000"
    assert extract("پرداخت قسط تسهیلات شماره:  LN_0000123456  - متعلق به علی رضایی").loan_ref == "LN_0000123456"
    assert extract("پرداخت قبض از  94000015 به پرداخت ملت ش م 806633430248").biller_id == "94000015"


def test_clean_amount_handles_scientific_notation():
    """اعداد بزرگ در فایل به شکل «1.1E8» می‌آیند."""
    assert clean_amount(1.1e8) == 110_000_000
    assert clean_amount("1.1E8") == 110_000_000
    assert clean_amount("4,461,092") == 4_461_092
    assert clean_amount("۱۲۳٬۴۵۶") == 123_456
    assert clean_amount(None) == 0
    assert clean_amount("") == 0
