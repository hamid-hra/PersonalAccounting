"""
فایل‌های آپلودشده در دیتابیس می‌مانند: محتوای تکراری یک بار ذخیره می‌شود،
حذف فقط وقتی هیچ ارجاعی نمانده، و فایل‌های قدیمی روی دیسک یک‌بار وارد می‌شوند.
"""

from app.models import Loan, LoanAttachment
from app.services import filestore
from app.services.loans import delete_receipt_file, save_receipt


def test_put_is_content_addressed_and_deduplicated(db):
    a = filestore.put(db, filestore.RECEIPT, b"same", ".png", "image/png")
    b = filestore.put(db, filestore.RECEIPT, b"same", ".png", "image/png")
    c = filestore.put(db, filestore.RECEIPT, b"other", ".png", "image/png")
    assert a == b != c
    assert a.endswith(".png") and len(a) == 68
    assert filestore.get(db, a).content == b"same"
    assert filestore.get(db, a).size_bytes == 4


def test_delete_and_missing(db):
    name = filestore.put(db, filestore.WISHLIST, b"img", ".jpg", "image/jpeg")
    assert filestore.exists(db, name)
    filestore.delete(db, name)
    assert not filestore.exists(db, name)
    filestore.delete(db, name)          # حذف دوباره خطا نمی‌دهد
    assert filestore.get(db, "nope") is None


def test_receipt_shared_by_two_attachments_survives_one_delete(db):
    loan = Loan(title="وام", installment_count=1, installment_amount_rial=1, first_due_jalali="1404/07/06")
    db.add(loan)
    db.flush()
    name, mime, size, digest = save_receipt(db, b"receipt", "r.png", "image/png")
    assert digest == name[:64]
    first = LoanAttachment(loan_id=loan.id, stored_name=name, original_name="r.png",
                           mime_type=mime, size_bytes=size, sha256=digest)
    second = LoanAttachment(loan_id=loan.id, stored_name=name, original_name="r.png",
                            mime_type=mime, size_bytes=size, sha256=digest)
    db.add_all([first, second])
    db.commit()

    db.delete(first)
    db.flush()
    delete_receipt_file(db, first)
    assert filestore.exists(db, name)   # هنوز دومی به آن اشاره می‌کند

    db.delete(second)
    db.flush()
    delete_receipt_file(db, second)
    assert not filestore.exists(db, name)


def test_legacy_files_on_disk_are_imported_once(db, tmp_path):
    (tmp_path / "abc.xlsx").write_bytes(b"xlsx")
    (tmp_path / ".gitkeep").write_bytes(b"")
    assert filestore.import_legacy_dir(db, tmp_path, filestore.STATEMENT) == 1
    assert filestore.import_legacy_dir(db, tmp_path, filestore.STATEMENT) == 0
    assert filestore.get(db, "abc.xlsx").kind == filestore.STATEMENT
    assert filestore.import_legacy_dir(db, tmp_path / "missing", filestore.STATEMENT) == 0
