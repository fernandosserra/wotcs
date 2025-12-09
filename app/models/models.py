# app/models/models.py
from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime
from sqlalchemy import Boolean, JSON, Column, TIMESTAMP, String, Integer, DateTime

class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(index=True)
    password_hash: str
    role: str = "member"
    # novo campo:
    account_id: Optional[int] = Field(default=None, index=True)
    
class Player(SQLModel, table=True):
    account_id: int = Field(primary_key=True)
    nickname: str


class GarageTank(SQLModel, table=True):
    __tablename__ = "garagetank"   # força o nome exato da tabela no DB

    id: Optional[int] = Field(default=None, primary_key=True)
    account_id: int = Field(index=True)
    tank_id: int
    tank_name: Optional[str] = Field(default=None, sa_column=Column("tank_name", String(150)))
    tier: Optional[int] = Field(default=None)
    battles: Optional[int] = Field(default=0)
    wins: Optional[int] = Field(default=0)
    mark_of_mastery: Optional[int] = Field(default=None)
    is_premium: Optional[bool] = Field(default=False, sa_column=Column("is_premium", Boolean))
    nation: Optional[str] = Field(default=None, sa_column=Column("nation", String(50)))
    type: Optional[str] = Field(default=None, sa_column=Column("type", String(50)))
    image_url: Optional[str] = Field(default=None, sa_column=Column("image_url", String(255)))
    raw_json: Optional[dict] = Field(default=None, sa_column=Column("raw_json", JSON))
    last_updated: Optional[datetime] = Field(
    default=None,
    sa_column=Column(DateTime(timezone=True), nullable=True)
    )