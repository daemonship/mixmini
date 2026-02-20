import enum
import uuid

from fastapi_users.db import SQLAlchemyBaseUserTableUUID
from sqlalchemy import (
    Column,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.sqlite import CHAR
from sqlalchemy.orm import relationship
from sqlalchemy.types import TypeDecorator

from app.database import Base


# UUID stored as CHAR(36) for SQLite compatibility
class UUIDType(TypeDecorator):
    impl = CHAR(36)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return uuid.UUID(value)


class PaintStatus(str, enum.Enum):
    full = "full"
    low = "low"
    empty = "empty"


class User(SQLAlchemyBaseUserTableUUID, Base):
    __tablename__ = "users"

    paints = relationship("UserPaint", back_populates="user", cascade="all, delete-orphan")
    recipes = relationship("Recipe", back_populates="user", cascade="all, delete-orphan")


class Paint(Base):
    __tablename__ = "paints"

    id = Column(Integer, primary_key=True, index=True)
    brand = Column(String(64), nullable=False, index=True)
    range = Column(String(64), nullable=False, index=True)
    name = Column(String(128), nullable=False)
    hex = Column(String(7), nullable=False)
    paint_type = Column(String(32), nullable=False)

    user_paints = relationship("UserPaint", back_populates="paint")
    recipe_components = relationship("RecipeComponent", back_populates="paint")

    __table_args__ = (UniqueConstraint("brand", "range", "name", name="uq_paint_brand_range_name"),)


class UserPaint(Base):
    __tablename__ = "user_paints"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(UUIDType, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    paint_id = Column(Integer, ForeignKey("paints.id", ondelete="CASCADE"), nullable=False)
    status = Column(Enum(PaintStatus), nullable=False, default=PaintStatus.full)

    user = relationship("User", back_populates="paints")
    paint = relationship("Paint", back_populates="user_paints")

    __table_args__ = (UniqueConstraint("user_id", "paint_id", name="uq_user_paint"),)


class Recipe(Base):
    __tablename__ = "recipes"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(UUIDType, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(128), nullable=False)
    note = Column(Text, nullable=True)

    user = relationship("User", back_populates="recipes")
    components = relationship(
        "RecipeComponent", back_populates="recipe", cascade="all, delete-orphan"
    )


class RecipeComponent(Base):
    __tablename__ = "recipe_components"

    id = Column(Integer, primary_key=True, index=True)
    recipe_id = Column(Integer, ForeignKey("recipes.id", ondelete="CASCADE"), nullable=False)
    paint_id = Column(Integer, ForeignKey("paints.id", ondelete="CASCADE"), nullable=False)
    ratio = Column(Integer, nullable=False, default=1)

    recipe = relationship("Recipe", back_populates="components")
    paint = relationship("Paint", back_populates="recipe_components")
