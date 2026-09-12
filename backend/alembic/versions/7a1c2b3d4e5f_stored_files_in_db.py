"""stored files live in the database

Revision ID: 7a1c2b3d4e5f
Revises: 4ee7c13db44c
Create Date: 2026-09-12 12:00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '7a1c2b3d4e5f'
down_revision: Union[str, None] = '4ee7c13db44c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'stored_file',
        sa.Column('name', sa.String(length=160), nullable=False),
        sa.Column('kind', sa.String(length=20), nullable=False),
        sa.Column('mime_type', sa.String(length=80), nullable=False),
        sa.Column('size_bytes', sa.Integer(), nullable=False),
        sa.Column('content', sa.LargeBinary(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('name'),
    )
    op.create_index(op.f('ix_stored_file_kind'), 'stored_file', ['kind'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_stored_file_kind'), table_name='stored_file')
    op.drop_table('stored_file')
