# app/api/auth.py
"""
Auth routes for WOT Clan Dashboard
- register: requires account_id or nickname (resolved from DB), verifies clan membership via WG API (cached)
- login / logout: cookie-based for POC

Notes:
- We resolve nickname -> account_id from the local Player table (no async calls).
- Role is forced to 'member' server-side.
- Passwords: SHA256 -> base64-url -> bcrypt (safe under bcrypt 72-byte limit).
"""

import logging
import hashlib
import base64
import os
import json
import time
from pathlib import Path
from typing import Optional
from urllib.parse import quote

import httpx
from fastapi import APIRouter, Request, Form
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select
from passlib.context import CryptContext
from sqlalchemy.exc import IntegrityError

from app.db import engine
from app.models import User, Player

logger = logging.getLogger("wotcs.auth")

# Config / cache
WOT_APP_ID = os.getenv("WOT_APP_ID", "")
CLAN_ID = os.getenv("CLAN_ID", "")
# Use realm configured in env; default to the NA API host we used elsewhere
WOT_REALM = os.getenv("WOT_REALM", "https://api.worldoftanks.com")

MEMBERS_CACHE_PATH = Path("data/members_cache.json")
MEMBERS_CACHE_TTL = 60 * 10  # 10 minutes

pwdctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
router = APIRouter()


# -------------------------
# Cache helpers
# -------------------------
def load_members_cache():
    if not MEMBERS_CACHE_PATH.exists():
        return {"ts": 0, "members": []}
    try:
        with open(MEMBERS_CACHE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        logger.exception("Failed to load members cache: %s", exc)
        return {"ts": 0, "members": []}


def save_members_cache(data):
    try:
        MEMBERS_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(MEMBERS_CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as exc:
        logger.exception("Failed to save members cache: %s", exc)


# -------------------------
# WG API helpers
# -------------------------
def fetch_clan_members(force_refresh: bool = False):
    """
    Returns a list of account_id integers of clan members.
    Uses a local cache to avoid excessive API calls.
    NOTE: we intentionally do a 'light' call (no extra param) because some realms
    returned INVALID_EXTRA previously. If you want to re-enable extra=members,
    test against your realm.
    """
    cache = load_members_cache()
    now = int(time.time())
    if not force_refresh and cache.get("ts", 0) + MEMBERS_CACHE_TTL > now and cache.get("members"):
        return cache["members"]

    if not WOT_APP_ID or not CLAN_ID:
        logger.warning("WOT_APP_ID or CLAN_ID not configured.")
        return []

    try:
        # call without `extra=members` to be conservative (works for your realm)
        url = f"{WOT_REALM}/wot/clans/info/?application_id={WOT_APP_ID}&clan_id={CLAN_ID}"
        with httpx.Client(timeout=10) as client:
            r = client.get(url)
            r.raise_for_status()
            js = r.json()
            # sometimes the response includes 'members' under data.<clan_id>
            members = js.get("data", {}).get(str(CLAN_ID), {}).get("members", []) or []
            account_ids = [int(m["account_id"]) for m in members if "account_id" in m]
            save_members_cache({"ts": now, "members": account_ids})
            return account_ids
    except Exception as exc:
        logger.exception("Erro ao buscar membros do WG (fetch_clan_members): %s", exc)
        # fallback to whatever we have in cache
        return cache.get("members", [])


# -------------------------
# Resolve nickname -> account_id via local DB
# -------------------------
def resolve_account_id_from_db(nickname: str) -> Optional[int]:
    """
    Try to find the player's account_id in local Player table.
    First exact (case-insensitive), then substring match as fallback.
    """
    if not nickname:
        return None
    try:
        with Session(engine) as s:
            # exact case-insensitive
            q = select(Player).where(Player.nickname.ilike(nickname))
            p = s.exec(q).first()
            if p:
                return int(p.account_id)
            # substring fallback
            q2 = select(Player).where(Player.nickname.ilike(f"%{nickname}%"))
            p2 = s.exec(q2).first()
            if p2:
                return int(p2.account_id)
    except Exception as exc:
        logger.exception("Erro ao buscar Player no DB: %s", exc)
    return None


# -------------------------
# Password helpers (SHA256 -> base64-url -> bcrypt)
# -------------------------
def _prehash_to_b64(password: str) -> str:
    digest = hashlib.sha256(password.encode("utf-8")).digest()
    b64 = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return b64


def hash_password(pw: str) -> str:
    short = _prehash_to_b64(pw)
    return pwdctx.hash(short)


def verify_password(plain: str, hashed: str) -> bool:
    short = _prehash_to_b64(plain)
    return pwdctx.verify(short, hashed)


# -------------------------
# Register (single consolidated endpoint)
# -------------------------
@router.post("/register")
def register(
    username: str = Form(...),
    password: str = Form(...),
    account_id: Optional[int] = Form(None),
    nickname: Optional[str] = Form(None),
):
    """
    Registration flow:
    - Prefer account_id from form
    - Otherwise try local DB lookup for nickname
    - Require account_id and verify membership via WG (cached)
    - Force role='member' on server side
    - Optionally store account_id on user model if field exists
    """
    try:
        # Resolve account_id: prefer explicit form value
        resolved_id = account_id
        if not resolved_id and nickname:
            resolved_id = resolve_account_id_from_db(nickname)

        if not resolved_id:
            return RedirectResponse(url="/auth/register?msg=need_account", status_code=303)

        members = fetch_clan_members()
        if int(resolved_id) not in members:
            return RedirectResponse(url="/auth/register?msg=not_member", status_code=303)

        # All good: create user but FORCE role = 'member'
        with Session(engine) as s:
            existing = s.exec(select(User).where(User.username == username)).first()
            if existing:
                return RedirectResponse(url="/auth/register?msg=exists", status_code=303)

            forced_role = "member"
            u = User(username=username, password_hash=hash_password(password), role=forced_role)

            # if your User model includes account_id attribute, set it
            try:
                if hasattr(u, "account_id"):
                    setattr(u, "account_id", int(resolved_id))
            except Exception:
                # ignore if model differs
                pass

            s.add(u)
            try:
                s.commit()
            except IntegrityError as ie:
                logger.exception("IntegrityError while committing new user: %s", ie)
                return RedirectResponse(url="/auth/register?msg=exists", status_code=303)

        return RedirectResponse(url="/auth/login?msg=registered", status_code=303)

    except Exception as exc:
        logger.exception("Erro ao registrar usuário: %s", exc)
        return RedirectResponse(url="/auth/register?msg=error", status_code=303)


# -------------------------
# Login / Logout
# -------------------------
@router.post("/login")
def login(request: Request, username: str = Form(...), password: str = Form(...)):
    with Session(engine) as s:
        user = s.exec(select(User).where(User.username == username)).first()
        if not user or not verify_password(password, user.password_hash):
            return RedirectResponse(url="/auth/login?msg=invalid", status_code=303)
        resp = RedirectResponse(url="/dashboard", status_code=303)
        resp.set_cookie(key="user", value=user.username, httponly=True, secure=False)
        return resp


@router.post("/logout")
def logout():
    resp = RedirectResponse(url="/", status_code=303)
    resp.delete_cookie("user")
    return resp