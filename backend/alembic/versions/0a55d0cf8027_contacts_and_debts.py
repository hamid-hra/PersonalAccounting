"""contacts and debts

Revision ID: 0a55d0cf8027
Revises: 4434d11c5116
Create Date: 2026-09-02 06:03:38.026739
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '0a55d0cf8027'
down_revision: Union[str, None] = '4434d11c5116'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    تغییر نام مفهومی «فروشنده» به «مخاطب» + دفتر قرض.

    ترتیب عمداً دستی است: alembic جدول تازه را قبل از حذف قدیمی می‌ساخت و
    نام قید uq_identifier_kind_value تصادم می‌کرد؛ و merchant تا وقتی
    کلیدهای خارجیِ transaction و rule به آن اشاره کنند حذف نمی‌شود.

    اگر روی دیتابیسی اجرا شود که مخاطب ثبت‌شده دارد، عمداً متوقف می‌شود
    تا داده بی‌صدا از بین نرود.
    """
    conn = op.get_bind()
    rows = conn.execute(sa.text("SELECT count(*) FROM merchant")).scalar()
    if rows:
        raise RuntimeError(
            f"جدول merchant {rows} رکورد دارد و این مهاجرت حذفش می‌کند. "
            "اول پشتیبان بگیر و مهاجرت را به RENAME تغییر بده."
        )

    # ۱) ارجاع‌ها به merchant برداشته شوند
    op.drop_constraint("transaction_merchant_id_fkey", "transaction", type_="foreignkey")
    op.drop_index("ix_transaction_merchant_id", table_name="transaction")
    op.drop_column("transaction", "merchant_id")

    op.drop_constraint("rule_set_merchant_id_fkey", "rule", type_="foreignkey")
    op.drop_column("rule", "set_merchant_id")

    # ۲) جدول‌های قدیمی
    op.drop_index("ix_merchant_identifier_merchant_id", table_name="merchant_identifier")
    op.drop_table("merchant_identifier")
    op.drop_index("ix_merchant_category_id", table_name="merchant")
    op.drop_index("ix_merchant_name_norm", table_name="merchant")
    op.drop_table("merchant")

    # ۳) جدول‌های تازه
    op.create_table('contact',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name_fa', sa.String(length=200), nullable=False),
    sa.Column('name_norm', sa.String(length=200), nullable=False),
    sa.Column('name_key', sa.String(length=200), nullable=True),
    sa.Column('kind', sa.String(length=16), nullable=False),
    sa.Column('category_id', sa.Integer(), nullable=True),
    sa.Column('income_category_id', sa.Integer(), nullable=True),
    sa.Column('phone', sa.String(length=20), nullable=True),
    sa.Column('is_favorite', sa.Boolean(), nullable=False),
    sa.Column('note', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['category_id'], ['category.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['income_category_id'], ['category.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_contact_category_id'), 'contact', ['category_id'], unique=False)
    op.create_index(op.f('ix_contact_name_key'), 'contact', ['name_key'], unique=False)
    op.create_index(op.f('ix_contact_name_norm'), 'contact', ['name_norm'], unique=False)
    op.create_table('contact_identifier',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('contact_id', sa.Integer(), nullable=False),
    sa.Column('kind', sa.String(length=24), nullable=False),
    sa.Column('value', sa.String(length=64), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['contact_id'], ['contact.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('kind', 'value', name='uq_identifier_kind_value')
    )
    op.create_index(op.f('ix_contact_identifier_contact_id'), 'contact_identifier', ['contact_id'], unique=False)
    op.create_table('debt',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('contact_id', sa.Integer(), nullable=True),
    sa.Column('person_name', sa.String(length=200), nullable=False),
    sa.Column('direction', sa.String(length=16), nullable=False),
    sa.Column('principal_rial', sa.BigInteger(), nullable=False),
    sa.Column('opened_jalali', sa.String(length=12), nullable=False),
    sa.Column('opened_date', sa.Date(), nullable=False),
    sa.Column('due_jalali', sa.String(length=12), nullable=True),
    sa.Column('status', sa.String(length=12), nullable=False),
    sa.Column('note', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['contact_id'], ['contact.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_debt_contact_id'), 'debt', ['contact_id'], unique=False)
    op.create_index(op.f('ix_debt_direction'), 'debt', ['direction'], unique=False)
    op.create_index(op.f('ix_debt_opened_date'), 'debt', ['opened_date'], unique=False)
    op.create_index(op.f('ix_debt_status'), 'debt', ['status'], unique=False)
    op.create_table('debt_entry',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('debt_id', sa.Integer(), nullable=False),
    sa.Column('transaction_id', sa.Integer(), nullable=True),
    sa.Column('kind', sa.String(length=12), nullable=False),
    sa.Column('amount_rial', sa.BigInteger(), nullable=False),
    sa.Column('entry_jalali', sa.String(length=12), nullable=False),
    sa.Column('entry_date', sa.Date(), nullable=False),
    sa.Column('note', sa.Text(), nullable=True),
    sa.ForeignKeyConstraint(['debt_id'], ['debt.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['transaction_id'], ['transaction.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_debt_entry_debt_id'), 'debt_entry', ['debt_id'], unique=False)
    op.create_index(op.f('ix_debt_entry_transaction_id'), 'debt_entry', ['transaction_id'], unique=False)

    # ۴) ستون‌های تازه روی جدول‌های موجود
    op.add_column("rule", sa.Column("set_contact_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "rule_set_contact_id_fkey", "rule", "contact", ["set_contact_id"], ["id"],
        ondelete="SET NULL",
    )
    op.add_column("transaction", sa.Column("contact_id", sa.Integer(), nullable=True))
    op.create_index(
        op.f("ix_transaction_contact_id"), "transaction", ["contact_id"], unique=False
    )
    op.create_foreign_key(
        "transaction_contact_id_fkey", "transaction", "contact", ["contact_id"], ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('transaction', sa.Column('merchant_id', sa.INTEGER(), autoincrement=False, nullable=True))
    op.drop_constraint(None, 'transaction', type_='foreignkey')
    op.create_foreign_key('transaction_merchant_id_fkey', 'transaction', 'merchant', ['merchant_id'], ['id'], ondelete='SET NULL')
    op.drop_index(op.f('ix_transaction_contact_id'), table_name='transaction')
    op.create_index('ix_transaction_merchant_id', 'transaction', ['merchant_id'], unique=False)
    op.drop_column('transaction', 'contact_id')
    op.add_column('rule', sa.Column('set_merchant_id', sa.INTEGER(), autoincrement=False, nullable=True))
    op.drop_constraint(None, 'rule', type_='foreignkey')
    op.create_foreign_key('rule_set_merchant_id_fkey', 'rule', 'merchant', ['set_merchant_id'], ['id'], ondelete='SET NULL')
    op.drop_column('rule', 'set_contact_id')
    op.create_table('merchant',
    sa.Column('id', sa.INTEGER(), server_default=sa.text("nextval('merchant_id_seq'::regclass)"), autoincrement=True, nullable=False),
    sa.Column('name_fa', sa.VARCHAR(length=200), autoincrement=False, nullable=False),
    sa.Column('name_norm', sa.VARCHAR(length=200), autoincrement=False, nullable=False),
    sa.Column('category_id', sa.INTEGER(), autoincrement=False, nullable=True),
    sa.Column('note', sa.TEXT(), autoincrement=False, nullable=True),
    sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=False),
    sa.ForeignKeyConstraint(['category_id'], ['category.id'], name='merchant_category_id_fkey', ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id', name='merchant_pkey'),
    postgresql_ignore_search_path=False
    )
    op.create_index('ix_merchant_name_norm', 'merchant', ['name_norm'], unique=False)
    op.create_index('ix_merchant_category_id', 'merchant', ['category_id'], unique=False)
    op.create_table('merchant_identifier',
    sa.Column('id', sa.INTEGER(), autoincrement=True, nullable=False),
    sa.Column('merchant_id', sa.INTEGER(), autoincrement=False, nullable=False),
    sa.Column('kind', sa.VARCHAR(length=24), autoincrement=False, nullable=False),
    sa.Column('value', sa.VARCHAR(length=64), autoincrement=False, nullable=False),
    sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=False),
    sa.ForeignKeyConstraint(['merchant_id'], ['merchant.id'], name='merchant_identifier_merchant_id_fkey', ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name='merchant_identifier_pkey'),
    sa.UniqueConstraint('kind', 'value', name='uq_identifier_kind_value')
    )
    op.create_index('ix_merchant_identifier_merchant_id', 'merchant_identifier', ['merchant_id'], unique=False)
    op.drop_index(op.f('ix_debt_entry_transaction_id'), table_name='debt_entry')
    op.drop_index(op.f('ix_debt_entry_debt_id'), table_name='debt_entry')
    op.drop_table('debt_entry')
    op.drop_index(op.f('ix_debt_status'), table_name='debt')
    op.drop_index(op.f('ix_debt_opened_date'), table_name='debt')
    op.drop_index(op.f('ix_debt_direction'), table_name='debt')
    op.drop_index(op.f('ix_debt_contact_id'), table_name='debt')
    op.drop_table('debt')
    op.drop_index(op.f('ix_contact_identifier_contact_id'), table_name='contact_identifier')
    op.drop_table('contact_identifier')
    op.drop_index(op.f('ix_contact_name_norm'), table_name='contact')
    op.drop_index(op.f('ix_contact_name_key'), table_name='contact')
    op.drop_index(op.f('ix_contact_category_id'), table_name='contact')
    op.drop_table('contact')
    # ### end Alembic commands ###
