from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    enterprise_id: Mapped[int] = mapped_column(ForeignKey("enterprises.id"), nullable=False)

    profile_photo: Mapped[str | None] = mapped_column(Text, nullable=True)

    name: Mapped[str] = mapped_column(String(120), nullable=False, default="", server_default="")

    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)

    hashed_password: Mapped[str] = mapped_column(String, nullable=False)

    role: Mapped[str] = mapped_column(String(50), nullable=False, default="employee")

    is_active: Mapped[bool] = mapped_column(default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    reset_requested_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    enterprise = relationship("Enterprise", back_populates="users")

    @property
    def enterprise_name(self) -> str:
        return self.enterprise.name
