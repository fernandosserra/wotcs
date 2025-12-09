# app/db.py
import os
from sqlmodel import create_engine, SQLModel
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL não está definida no ambiente!")

# SQLite usa connect_args — Postgres NÃO
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

# Cria o engine
engine = create_engine(
    DATABASE_URL,
    echo=False,
    connect_args=connect_args
)

def get_session():
    from sqlmodel import Session
    with Session(engine) as session:
        yield session

def init_db():
    """
    Registra modelos e cria tabelas apenas se forem novas.
    Importante: Para Postgres, *não recria tabelas existentes*.
    """
    # Importa os modelos para registrar no metadata
    import app.models.models