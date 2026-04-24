# create table leodev901.m365_user_toekn (
#   app_name character varying not null,
#   user_id character varying not null,
#   access_token text null,
#   refresh_token text null,
#   expires_at timestamp with time zone null,
#   created_at timestamp with time zone not null default now(),
#   updated_at timestamp with time zone null default now(),
#   constraint m365_user_toekn_pkey primary key (app_name, user_id)
# ) TABLESPACE pg_default;

from cmn.db.models.base import Base, AuditMixin
from sqlalchemy import String, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime


class M365UserToken(Base, AuditMixin):
    __tablename__ = "m365_user_toekn"

    app_name: Mapped[str] = mapped_column(String, primary_key=True, comment="앱 이름")
    user_id: Mapped[str] = mapped_column(String, primary_key=True, comment="사용자 ID")
    access_token: Mapped[str ] = mapped_column(Text, nullable=False, comment="액세스 토큰")
    refresh_token: Mapped[str | None] = mapped_column(Text, nullable=True, comment="리프레시 토큰")
    expires_at: Mapped[datetime ] = mapped_column(DateTime(timezone=True), nullable=False, comment="만료 일시")

