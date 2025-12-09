#!/usr/bin/env python3
# scripts/deploy/create_table_from_models.py
import os
import sys
import logging
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("create_tables")

def ensure_project_root_in_syspath():
    # Este script está em scripts/deploy/ ; subir duas pastas para achar a raiz do projeto
    this_file = os.path.abspath(__file__)
    project_root = os.path.abspath(os.path.join(os.path.dirname(this_file), "..", ".."))
    logger.info("Detectado project_root: %s", project_root)
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
        logger.info("Adicionado project_root em sys.path")

    # sanity: checar se existe package 'app'
    app_init = os.path.join(project_root, "app", "__init__.py")
    if not os.path.exists(app_init):
        logger.warning("app/__init__.py não encontrado em %s — verifique que 'app' é um package", app_init)
    return project_root

def main():
    logger.info("DATABASE_URL: %s", os.getenv("DATABASE_URL"))
    if not os.getenv("DATABASE_URL"):
        logger.error("DATABASE_URL não definida. Ex: export DATABASE_URL='postgresql+psycopg2://user:pass@host:5432/db'")
        sys.exit(2)

    ensure_project_root_in_syspath()

    try:
        # importe a factory do engine conforme seu app/db.py
        # se seu app/db expõe 'engine' em vez de 'get_engine', ajuste abaixo
        from app.db import get_engine
    except Exception as e:
        logger.exception("Falha ao importar app.db: %s", e)
        raise

    try:
        # importar explicitamente o módulo que define os modelos
        # ajuste se seus modelos estiverem em outro arquivo
        import app.models.models as _models_module  # noqa: F401
    except ModuleNotFoundError:
        try:
            import app.models as _models_module
        except Exception as e:
            logger.exception("Falha ao importar app.models: %s", e)
            raise

    from sqlmodel import SQLModel
    engine = get_engine()

    logger.info("Criando tabelas (SQLModel.metadata.create_all)...")
    try:
        SQLModel.metadata.create_all(engine)
    except Exception as e:
        logger.exception("Erro ao criar tabelas: %s", e)
        raise

    # listar tabelas no schema public (Postgres) ou sqlite master, dependendo do dialect
    try:
        with engine.connect() as conn:
            dialect_name = engine.dialect.name
            logger.info("Dialect detectado: %s", dialect_name)
            if dialect_name.startswith("postgres"):
                res = conn.exec("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' ORDER BY table_name")
                tables = [r[0] for r in res.fetchall()]
            else:
                # sqlite fallback
                res = conn.exec("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
                tables = [r[0] for r in res.fetchall()]
            logger.info("Tabelas visíveis: %s", tables)
    except Exception as e:
        logger.exception("Falha ao listar tabelas: %s", e)

    logger.info("Concluído com sucesso.")

if __name__ == "__main__":
    main()
