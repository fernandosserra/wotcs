# app/api/admin.py
from fastapi import APIRouter, Request, HTTPException, Depends, Path
from fastapi.responses import JSONResponse
from sqlmodel import Session, select
from typing import List, Dict, Any
import logging
from app.db import engine
from app.models import User
from datetime import datetime

logger = logging.getLogger("wotcs.admin")
router = APIRouter()

# Helper: obtain current user from cookie (local copy of logic to avoid circular import)
def get_current_user_from_cookie(request: Request) -> User:
    username = request.cookies.get("user")
    if not username:
        raise HTTPException(status_code=401, detail="Não autenticado")
    with Session(engine) as s:
        user = s.exec(select(User).where(User.username == username)).first()
        if not user:
            raise HTTPException(status_code=401, detail="Usuário não existe")
        return user

def require_commander(request: Request) -> User:
    user = get_current_user_from_cookie(request)
    if getattr(user, "role", None) != "commander":
        raise HTTPException(status_code=403, detail="Apenas comandantes podem acessar")
    return user

# GET /admin/pending -> lista usuários com role='pending'
@router.get("/admin/pending")
def list_pending(request: Request, commander: User = Depends(require_commander)):
    with Session(engine) as s:
        rows = s.exec(select(User).where(User.role == "pending")).all()
        out = []
        for u in rows:
            d = {"id": getattr(u, "id", None), "username": u.username, "account_id": getattr(u, "account_id", None)}
            out.append(d)
        return JSONResponse(content={"pending": out})

# POST /admin/promote/{user_id} -> promove para commander (grava auditoria se tabelas existirem)
@router.post("/admin/promote/{user_id}")
def promote_user(request: Request, user_id: int = Path(...), commander: User = Depends(require_commander)):
    promoted_by = commander.username
    now = datetime.utcnow()
    with Session(engine) as s:
        target = s.get(User, user_id)
        if not target:
            raise HTTPException(status_code=404, detail="Usuário não encontrado")
        old_role = getattr(target, "role", None)
        if old_role == "commander":
            return JSONResponse(content={"ok": False, "msg": "Usuário já é comandante"})
        # update role
        target.role = "commander"
        s.add(target)
        s.commit()
        s.refresh(target)

        # Try insert audit record (if role_changes table exists)
        try:
            s.execute(
                "INSERT INTO role_changes (user_id, old_role, new_role, changed_by, ts) VALUES (:u, :o, :n, :c, :t)",
                {"u": int(user_id), "o": old_role, "n": "commander", "c": promoted_by, "t": now},
            )
            s.commit()
        except Exception:
            # audit table might not exist yet — log and continue
            logger.debug("role_changes table not present or audit insert failed; continuing without audit")

    return JSONResponse(content={"ok": True, "user_id": user_id, "old_role": old_role, "new_role": "commander", "promoted_by": promoted_by})
