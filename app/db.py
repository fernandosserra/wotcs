# app/db.py
import os
from typing import Generator
from sqlmodel import create_engine, SQLModel, Session
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

# Apenas sqlite usa connect_args
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

# 🔥 Engine global exportado corretamente
engine = create_engine(DATABASE_URL, echo=False, connect_args=connect_args)


def get_engine():
    """Compatibilidade com scripts externos."""
    return engine


def get_session() -> Generator:
    """Para dependências FastAPI."""
    with Session(engine) as session:
        yield session


def init_db() -> None:
    """
    Importa modelos e registra no metadata.
    Criar tabelas se não existirem.
    """
    # 🔥 Importa modelos sem importar nada que dependa de 'app.main'
    from app.models import (
        User,
        Player,
        GarageTank,
    )

    SQLModel.metadata.create_all(engine)