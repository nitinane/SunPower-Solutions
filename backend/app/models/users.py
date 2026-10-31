"""Employee accounts for all application roles."""

from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, Index, Numeric, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, TimestampMixin
from app.models.enums import UserRole, sql_in


class User(IdMixin, TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(sql_in("role", UserRole), name="role_allowed"),
        CheckConstraint("hourly_rate IS NULL OR hourly_rate >= 0", name="hourly_rate_nonnegative"),
        CheckConstraint("length(btrim(full_name)) > 0", name="full_name_not_blank"),
        CheckConstraint("email = lower(btrim(email))", name="email_normalized"),
        CheckConstraint(
            "phone IS NULL OR phone ~ '^\\+[1-9][0-9]{7,14}$'",
            name="phone_e164",
        ),
        Index("uq_users_email_lower", text("lower(email)"), unique=True),
        Index("ix_users_phone", "phone", postgresql_where=text("phone IS NOT NULL")),
        Index("ix_users_role_active", "role", "is_active"),
    )

    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(16))
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(String(30), nullable=False)
    hourly_rate: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
