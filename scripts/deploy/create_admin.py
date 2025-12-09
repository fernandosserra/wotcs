#!/usr/bin/env python3
"""
scripts/deploy/create_admin.py

Uso:
    python3 scripts/deploy/create_admin.py <username> <password> [<account_id>] [<role>]

Exemplo:
    python3 scripts/deploy/create_admin.py Siegrfried hide2911 1002394327 commander

O script:
- insere o diretório do projeto no sys.path para permitir imports relativos (quando executado desde a raiz do projeto)
- importa engine / init_db de app.db e User do app.models
- cria um usuário novo (evita duplicatas)
- aplica pré-hash SHA256 -> base64-url antes de bcrypt (compatível com o restante do projeto)
- retorna exit code 0 se sucesso, !=0 em erro
"""

import sys
import os
import logging
import hashlib
import base64
import json
from typing import Optional

# --- garantir project root no sys.path (para permitir "from app.db import engine")
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("create_admin")

try:
    # imports do aplicativo
    from sqlmodel import Session, select
    from app.db import engine, init_db  # init_db é opcional mas útil
    from app.models import User
except Exception as exc:
    logger.exception("Falha ao importar módulos do app. Verifique se está executando a partir da raiz do projeto.")
    raise SystemExit(2) from exc

# passlib (bcrypt)
try:
    from passlib.context import CryptContext
except Exception as exc:
    logger.exception("passlib não disponível no venv. Instale passlib[bcrypt].")
    raise SystemExit(3) from exc

# Contexto bcrypt (utilizado em todo o projeto)
pwdctx = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _prehash_to_b64(password: str) -> str:
    """
    Pre-hash: SHA256 -> base64-url (sem '=' final).
    Isso mantém a entrada para bcrypt dentro dos limites e padroniza.
    """
    digest = hashlib.sha256(password.encode("utf-8")).digest()
    b64 = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return b64


def hash_password(pw: str) -> str:
    short = _prehash_to_b64(pw)
    # Note: bcrypt has a 72-byte input limit; pré-hash garante tamanho controlado.
    return pwdctx.hash(short)


def create_user(username: str, password: str, role: str = "member", account_id: Optional[int] = None) -> bool:
    """
    Cria um usuário no DB. Retorna True se criado, False se já existia.
    Em caso de erro lança exceção.
    """
    # garantir tabelas (opcional, idempotente)
    try:
        init_db()
    except Exception:
        # init_db pode falhar se já inicializado, mas tentamos fazer best-effort
        logger.debug("init_db falhou (não crítico). Prosseguindo.")

    with Session(engine) as s:
        # verificar duplicata
        existing = s.exec(select(User).where(User.username == username)).first()
        if existing:
            logger.info("Usuário já existe: %s", username)
            return False

        # criar user com role forçada em servidor (evitar self-promotion via client)
        forced_role = role or "member"
        try:
            hashed = hash_password(password)
        except Exception as exc:
            logger.exception("Falha ao hashear senha: %s", exc)
            raise

        u = User(username=username, password_hash=hashed, role=forced_role)

        # se o modelo de User tiver account_id, definimos
        if account_id is not None:
            try:
                if hasattr(u, "account_id"):
                    u.account_id = int(account_id)
            except Exception:
                logger.warning("Falha ao setar account_id no modelo User (campo ausente ou valor inválido). Ignorando.")

        s.add(u)
        try:
            s.commit()
        except Exception as exc:
            s.rollback()
            logger.exception("Falha ao inserir usuário no DB: %s", exc)
            raise

    logger.info("Usuário criado com sucesso: %s (role=%s)", username, forced_role)
    return True


def _print_usage_and_exit():
    print("Usage: python3 scripts/deploy/create_admin.py <username> <password> [<account_id>] [<role>]")
    print("Example: python3 scripts/deploy/create_admin.py Siegrfried hide2911 1002394327 commander")
    raise SystemExit(1)


def main(argv):
    if len(argv) < 3:
        _print_usage_and_exit()

    username = argv[1]
    password = argv[2]
    account_id = None
    role = "member"

    if len(argv) >= 4 and argv[3].strip() != "":
        try:
            account_id = int(argv[3])
        except Exception:
            # se não for inteiro, tratar como role em vez de account_id
            role = argv[3]
            account_id = None

    if len(argv) >= 5:
        role = argv[4]

    # se o terceiro argumento foi o account_id e o quarto existe, use como role
    # (coberto acima)

    try:
        created = create_user(username=username, password=password, role=role, account_id=account_id)
        if created:
            print(f"User created: {username} (role={role})")
            return 0
        else:
            print(f"User already exists: {username}")
            return 0
    except Exception as exc:
        logger.exception("Erro inesperado criando usuário: %s", exc)
        return 5


if __name__ == "__main__":
    rc = main(sys.argv)
    raise SystemExit(rc)
