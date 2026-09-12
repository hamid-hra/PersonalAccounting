from app.models import Loan
from app.services.jalali import parse_jalali_date
from app.services.loans import build_schedule


def test_schedule_length_and_amounts():
    loan = Loan(
        title="وام", installment_count=12, installment_amount_rial=27_790_352,
        first_due_jalali="1404/07/06",
    )
    schedule = build_schedule(loan)
    assert len(schedule) == 12
    assert schedule[0].due_jalali == "1404/07/06"
    assert schedule[-1].due_jalali == "1405/06/06"
    assert all(i.amount_rial == 27_790_352 for i in schedule)
    assert [i.seq for i in schedule] == list(range(1, 13))


def test_schedule_clamps_day_to_short_months():
    """سررسید ۳۱ام در ماه‌های ۳۰ روزه باید به آخر ماه بچسبد، نه ماه بعد."""
    loan = Loan(
        title="وام", installment_count=3, installment_amount_rial=1_000_000,
        first_due_jalali="1404/06/31",
    )
    dues = [i.due_jalali for i in build_schedule(loan)]
    assert dues == ["1404/06/31", "1404/07/30", "1404/08/30"]


def test_due_dates_are_converted_to_gregorian():
    loan = Loan(
        title="وام", installment_count=2, installment_amount_rial=1_000,
        first_due_jalali="1404/07/06",
    )
    schedule = build_schedule(loan)
    assert schedule[0].due_date == parse_jalali_date("1404/07/06")
    assert schedule[1].due_date > schedule[0].due_date


def test_reschedule_preserves_paid_installments(db):
    """
    مهم‌ترین قید ویرایش وام: اگر مبلغ یا تعداد قسط عوض شود، قسط‌هایی که
    واقعاً پرداخت شده‌اند نباید از بین بروند — تاریخچهٔ پرداخت واقعی است.
    """
    from datetime import date as _date

    from app.enums import InstallmentStatus
    from app.services.loans import build_schedule, reschedule

    loan = Loan(
        title="وام تست",
        installment_count=12,
        installment_amount_rial=27_790_352,
        first_due_jalali="1404/07/06",
    )
    db.add(loan)
    db.flush()
    for inst in build_schedule(loan):
        db.add(inst)
    db.flush()

    # سه قسط اول پرداخت شده‌اند
    for inst in loan.installments[:3]:
        inst.status = InstallmentStatus.PAID
        inst.paid_amount_rial = inst.amount_rial
        inst.paid_date = _date(2025, 10, 1)
    db.flush()

    loan.installment_amount_rial = 30_000_000
    loan.installment_count = 18
    result = reschedule(db, loan)
    db.refresh(loan)

    assert result["kept_paid"] == 3
    assert len(loan.installments) == 18

    paid = [i for i in loan.installments if i.status == InstallmentStatus.PAID]
    assert len(paid) == 3
    # مبلغ قسط‌های پرداخت‌شده نباید با مبلغ تازه بازنویسی شود
    assert all(i.amount_rial == 27_790_352 for i in paid)
    # قسط‌های تازه مبلغ تازه را دارند
    pending = [i for i in loan.installments if i.status != InstallmentStatus.PAID]
    assert all(i.amount_rial == 30_000_000 for i in pending)
    # شماره‌ها بدون تکرار و کامل‌اند
    assert sorted(i.seq for i in loan.installments) == list(range(1, 19))


def test_reschedule_shrink_keeps_paid(db):
    """اگر تعداد اقساط کمتر از پرداخت‌شده‌ها شود، پرداخت‌شده‌ها می‌مانند."""
    from datetime import date as _date

    from app.enums import InstallmentStatus
    from app.services.loans import build_schedule, reschedule

    loan = Loan(
        title="وام کوچک",
        installment_count=6,
        installment_amount_rial=1_000_000,
        first_due_jalali="1404/07/06",
    )
    db.add(loan)
    db.flush()
    for inst in build_schedule(loan):
        db.add(inst)
    db.flush()
    for inst in loan.installments[:4]:
        inst.status = InstallmentStatus.PAID
        inst.paid_date = _date(2025, 10, 1)
    db.flush()

    loan.installment_count = 2
    reschedule(db, loan)
    db.refresh(loan)

    paid = [i for i in loan.installments if i.status == InstallmentStatus.PAID]
    assert len(paid) == 4  # هیچ پرداختی حذف نشد
