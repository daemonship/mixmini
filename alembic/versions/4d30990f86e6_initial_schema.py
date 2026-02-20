"""initial schema

Revision ID: 4d30990f86e6
Revises:
Create Date: 2026-02-20 03:44:24.936135

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '4d30990f86e6'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('paints',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('brand', sa.String(length=64), nullable=False),
    sa.Column('range', sa.String(length=64), nullable=False),
    sa.Column('name', sa.String(length=128), nullable=False),
    sa.Column('hex', sa.String(length=7), nullable=False),
    sa.Column('paint_type', sa.String(length=32), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('brand', 'range', 'name', name='uq_paint_brand_range_name')
    )
    op.create_index(op.f('ix_paints_brand'), 'paints', ['brand'], unique=False)
    op.create_index(op.f('ix_paints_id'), 'paints', ['id'], unique=False)
    op.create_index(op.f('ix_paints_range'), 'paints', ['range'], unique=False)
    op.create_table('users',
    sa.Column('id', sa.CHAR(length=36), nullable=False),
    sa.Column('email', sa.String(length=320), nullable=False),
    sa.Column('hashed_password', sa.String(length=1024), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('is_superuser', sa.Boolean(), nullable=False),
    sa.Column('is_verified', sa.Boolean(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
    op.create_table('recipes',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.CHAR(length=36), nullable=False),
    sa.Column('name', sa.String(length=128), nullable=False),
    sa.Column('note', sa.Text(), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_recipes_id'), 'recipes', ['id'], unique=False)
    op.create_table('user_paints',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.CHAR(length=36), nullable=False),
    sa.Column('paint_id', sa.Integer(), nullable=False),
    sa.Column('status', sa.Enum('full', 'low', 'empty', name='paintstatus'), nullable=False),
    sa.ForeignKeyConstraint(['paint_id'], ['paints.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id', 'paint_id', name='uq_user_paint')
    )
    op.create_index(op.f('ix_user_paints_id'), 'user_paints', ['id'], unique=False)
    op.create_table('recipe_components',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('recipe_id', sa.Integer(), nullable=False),
    sa.Column('paint_id', sa.Integer(), nullable=False),
    sa.Column('ratio', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['paint_id'], ['paints.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['recipe_id'], ['recipes.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_recipe_components_id'), 'recipe_components', ['id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_recipe_components_id'), table_name='recipe_components')
    op.drop_table('recipe_components')
    op.drop_index(op.f('ix_user_paints_id'), table_name='user_paints')
    op.drop_table('user_paints')
    op.drop_index(op.f('ix_recipes_id'), table_name='recipes')
    op.drop_table('recipes')
    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_table('users')
    op.drop_index(op.f('ix_paints_range'), table_name='paints')
    op.drop_index(op.f('ix_paints_id'), table_name='paints')
    op.drop_index(op.f('ix_paints_brand'), table_name='paints')
    op.drop_table('paints')
