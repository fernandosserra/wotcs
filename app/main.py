# app/main.py
import os
import logging
import warnings
import time
import math
import json
import asyncio
import httpx

from typing import Optional, Dict, Any
from fastapi import FastAPI, Request, Depends, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv
from sqlmodel import select, Session, delete
from sqlalchemy import func, and_

# Load environment
load_dotenv()

# -----------------------------
# Basic config & constants
# -----------------------------
WOT_APP_ID = os.getenv("WOT_APP_ID", "")
CLAN_ID = os.getenv("CLAN_ID", "")
WOT_REALM = os.getenv("WOT_REALM", "https://api.worldoftanks.com")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/db.sqlite3")
SECRET_KEY = os.getenv("SECRET_KEY", "change-me-to-a-strong-secret")

# sync controls & batching
ENCYCLOPEDIA_BATCH = int(os.getenv("ENCYCLOPEDIA_BATCH", "50"))
SLEEP_BETWEEN_BATCHES = float(os.getenv("SLEEP_BETWEEN_BATCHES", "0.3"))
SYNC_RUNNING = False
LAST_SYNC_TS = 0
MIN_SYNC_INTERVAL = int(os.getenv("MIN_SYNC_INTERVAL", "45"))  # seconds

# Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("wotcs")
warnings.filterwarnings("ignore", message="error reading bcrypt version", module="passlib.handlers.bcrypt")

# Password hashing (passlib)
from passlib.context import CryptContext
pwdctx = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Templates & static
templates = Jinja2Templates(directory="app/templates")

# FastAPI app
app = FastAPI(title="WOT Clan Dashboard")
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# -----------------------------
# Imports that rely on app package (avoid circular issues)
# Ensure app.db does not import app.main
# -----------------------------
from app.db import engine, init_db
from app.models import User, Player, GarageTank

# Tank cache utils (assumed present)
from app.utils.tank_cache import load_tank_cache, save_tank_cache

TANK_CACHE: Dict[str, Any] = load_tank_cache() or {}

# -----------------------------
# Auth helpers (POC cookie-based)
# -----------------------------
def hash_password(pw: str) -> str:
    return pwdctx.hash(pw)

def verify_password(plain: str, hashed: str) -> bool:
    return pwdctx.verify(plain, hashed)

def get_current_user_from_cookie(request: Request) -> User:
    username = request.cookies.get("user")
    if not username:
        raise HTTPException(status_code=401, detail="Não autenticado")
    with Session(engine) as s:
        user = s.exec(select(User).where(User.username == username)).first()
        if not user:
            raise HTTPException(status_code=401, detail="Usuário não existe")
        return user

# -----------------------------
# Pages (GET) - templates
# -----------------------------
@app.get("/auth/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "title": "Login - Danonão Grosso"})

@app.get("/auth/register", response_class=HTMLResponse)
def register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request, "title": "Registrar - Danonão Grosso"})

@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    username = request.cookies.get("user")
    if username:
        return RedirectResponse(url="/dashboard")
    return RedirectResponse(url="/auth/login")

# -----------------------------
# Dashboard route (tolerant parsing)
# -----------------------------
# NOTE: tier is Optional[str] to avoid FastAPI int-parsing errors on empty string query params.
@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(
    request: Request,
    tier: Optional[str] = None,         # receber como string e validar internamente
    player_id: Optional[str] = None,    # idem
    nation: Optional[str] = None,
    tank_type: Optional[str] = None,
    page: int = 1,
    per_page: int = 25,
    current_user = Depends(get_current_user_from_cookie)
):
    # --- normalize pagination ---
    try:
        page = max(1, int(page))
    except Exception:
        page = 1
    try:
        per_page = int(per_page)
    except Exception:
        per_page = 25
    per_page = max(1, min(per_page, 200))

    # --- normalize filters ---
    resolved_player_id = None
    if player_id:
        try:
            resolved_player_id = int(player_id)
        except Exception:
            resolved_player_id = None

    # tier: se veio vazio ou '': tratar como None; se for número, converter para int
    resolved_tier = None
    if tier is not None and tier != "":
        try:
            resolved_tier = int(tier)
        except Exception:
            resolved_tier = None

    # --- load dropdowns & distinct nations/types as strings ---
    players = []
    nations = []
    types = []
    try:
        with Session(engine) as s:
            if getattr(current_user, "role", None) == "commander":
                players = s.exec(select(Player).order_by(Player.nickname)).all()

            # try to get distinct nations/types from DB, trimming whitespace
            try:
                nations_rows = s.exec(select(func.distinct(func.trim(GarageTank.nation)))).all()
                types_rows = s.exec(select(func.distinct(func.trim(GarageTank.type)))).all()
                # filter out null/empty strings and normalize to plain str
                nations = sorted([str(n).strip() for n in (nations_rows or []) if n and str(n).strip() != ""])
                types = sorted([str(t).strip() for t in (types_rows or []) if t and str(t).strip() != ""])
            except Exception:
                logger.exception("Erro ao buscar distinct nations/types do DB; fallback para cache.")
                nations = []
                types = []

    except Exception:
        # in case the DB session itself failed
        logger.exception("Falha ao carregar players/nations/types")
        players = players or []
        nations = nations or []
        types = types or []

    # --- fallback: if DB yielded nothing, try extracting from TANK_CACHE (file) ---
    if (not nations or not types) and isinstance(TANK_CACHE, dict) and len(TANK_CACHE) > 0:
        try:
            # extract nations/types from tank cache entries (keys are tank_id strings)
            cache_nations = set()
            cache_types = set()
            for meta in TANK_CACHE.values():
                if not isinstance(meta, dict):
                    continue
                n = meta.get("nation") or meta.get("default_profile", {}).get("nation") or None
                t = meta.get("type") or meta.get("vehicle_type") or None
                if n and str(n).strip():
                    cache_nations.add(str(n).strip())
                if t and str(t).strip():
                    cache_types.add(str(t).strip())
            # only fill missing ones, preserve DB results if any
            if not nations:
                nations = sorted(cache_nations)
            if not types:
                types = sorted(cache_types)
        except Exception:
            logger.exception("Fallback TANK_CACHE failed while building nations/types.")

    # --- build query with filters ---
    with Session(engine) as s:
        base_q = select(GarageTank, Player).join(Player, GarageTank.account_id == Player.account_id)

        filters = []
        if resolved_tier:
            filters.append(GarageTank.tier == resolved_tier)

        # player filter allowed only for commanders
        if getattr(current_user, "role", None) == "commander":
            if resolved_player_id:
                filters.append(Player.account_id == resolved_player_id)
        else:
            # non-commander: optionally restrict to user's own account
            try:
                if getattr(current_user, "account_id", None):
                    filters.append(Player.account_id == current_user.account_id)
            except Exception:
                pass

        if nation:
            filters.append(GarageTank.nation == nation)
        if tank_type:
            filters.append(GarageTank.type == tank_type)

        if filters:
            base_q = base_q.where(and_(*filters))

        # total count
        count_q = select(func.count()).select_from(GarageTank).join(Player, GarageTank.account_id == Player.account_id)
        if filters:
            count_q = count_q.where(and_(*filters))
        try:
            total_count = int(s.exec(count_q).one())
        except Exception:
            # fallback
            try:
                total_count = int(s.exec(select(func.count()).select_from(GarageTank)).one())
            except Exception:
                total_count = 0

        # aggregates (over the full filtered set, not paginated)
        agg_q = select(
            func.coalesce(func.sum(GarageTank.battles), 0),
            func.coalesce(func.sum(GarageTank.wins), 0),
            func.coalesce(func.sum(GarageTank.mark_of_mastery), 0),
        ).select_from(GarageTank).join(Player, GarageTank.account_id == Player.account_id)
        if filters:
            agg_q = agg_q.where(and_(*filters))
        agg_res = s.exec(agg_q).one()
        total_battles = int(agg_res[0] or 0)
        total_wins = int(agg_res[1] or 0)
        total_marks = int(agg_res[2] or 0)

        avg_battles = round(total_battles / total_count, 2) if total_count > 0 else 0.0
        win_pct = round((total_wins / total_battles) * 100.0, 2) if total_battles > 0 else 0.0

        # pagination and ordering
        offset = (page - 1) * per_page
        page_q = base_q.order_by(Player.nickname, GarageTank.tier.desc()).limit(per_page).offset(offset)
        rows = s.exec(page_q).all()

    total_pages = max(1, math.ceil(total_count / per_page)) if per_page else 1

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "title": "Dashboard do Clã",
        "rows": rows,
        "user": current_user,
        "players": players,
        "nations": nations,
        "types": types,
        "selected_tier": resolved_tier,
        "selected_player": resolved_player_id,
        "selected_nation": nation or "",
        "selected_type": tank_type or "",
        "page": page,
        "per_page": per_page,
        "total_count": total_count,
        "total_pages": total_pages,
        "stats": {
            "avg_battles": avg_battles,
            "win_pct": win_pct,
            "total_marks": total_marks,
            "total_battles": total_battles,
            "total_wins": total_wins
        }
    })
    
# -----------------------------
# Health & debug endpoints
# -----------------------------
@app.get("/health", response_class=JSONResponse)
def health():
    return JSONResponse({"status": "ok"})

@app.get("/health/db", response_class=JSONResponse)
def health_db():
    try:
        with engine.connect() as conn:
            # lightweight check
            conn.execute(select(1))
        return JSONResponse({"status": "ok", "db": "reachable"})
    except Exception as exc:
        logger.exception("Health DB failed: %s", exc)
        return JSONResponse({"status": "error", "db": "unreachable"}, status_code=500)

@app.get("/debug/users")
def debug_users():
    with Session(engine) as s:
        users = s.exec(select(User)).all()
        return [{"id": u.id, "username": u.username, "role": u.role} for u in users]

# -----------------------------
# SYNC: fetch_and_sync with batching, cache, debounce/lock
# -----------------------------
async def fetch_and_sync():
    """
    Sync optimized to use /wot/account/tanks and /wot/encyclopedia/vehicles (batch).
    Persists Player and GarageTank (only tiers 6,8,10). Uses TANK_CACHE and save_tank_cache().
    """
    global SYNC_RUNNING, LAST_SYNC_TS, TANK_CACHE

    now_ts = int(time.time())
    if SYNC_RUNNING:
        logger.info("Sync ignored: already running.")
        return
    if now_ts - LAST_SYNC_TS < MIN_SYNC_INTERVAL:
        logger.info(f"Sync ignored: last sync was {now_ts - LAST_SYNC_TS}s (<{MIN_SYNC_INTERVAL}s).")
        return

    SYNC_RUNNING = True
    logger.info(f"Iniciando sync para clã {CLAN_ID} no realm {WOT_REALM}")

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            # 1) fetch clan members (no extra param)
            members = []
            try:
                members_url = f"{WOT_REALM}/wot/clans/info/?application_id={WOT_APP_ID}&clan_id={CLAN_ID}"
                r = await client.get(members_url)
                r.raise_for_status()
                js = r.json()
                members = js.get("data", {}).get(str(CLAN_ID), {}).get("members", []) or []
            except Exception as exc:
                logger.exception("Erro ao obter membros do clã: %s", exc)
                members = []

            if not members:
                logger.warning("Nenhum membro obtido; abortando sync.")
                return

            # persist/update players
            account_ids = []
            with Session(engine) as s:
                for m in members:
                    try:
                        acc_id = int(m.get("account_id"))
                    except Exception:
                        continue
                    account_ids.append(acc_id)
                    nickname = m.get("account_name") or m.get("nickname") or f"player_{acc_id}"
                    p = s.get(Player, acc_id)
                    if not p:
                        p = Player(account_id=acc_id, nickname=nickname)
                        s.add(p)
                    else:
                        if p.nickname != nickname:
                            p.nickname = nickname
                            s.add(p)
                s.commit()

            # 2) gather tanks per player via account/tanks
            account_tanks_map = {}
            unique_tank_ids = set()

            for acc in account_ids:
                try:
                    tanks_url = f"{WOT_REALM}/wot/account/tanks/?application_id={WOT_APP_ID}&account_id={acc}"
                    rr = await client.get(tanks_url)
                    rr.raise_for_status()
                    j = rr.json()
                    items = j.get("data", {}).get(str(acc), []) or []
                except Exception as exc:
                    logger.warning("Falha account/tanks para %s: %s", acc, exc)
                    items = []

                account_tanks_map[acc] = items
                for it in items:
                    tid = it.get("tank_id") or it.get("tankId")
                    if tid:
                        try:
                            unique_tank_ids.add(int(tid))
                        except Exception:
                            pass

            logger.info("Coletados %d tank_ids únicos de %d jogadores", len(unique_tank_ids), len(account_ids))

            # 3) fetch vehicles metadata in batches (preferred endpoint)
            missing = [tid for tid in unique_tank_ids if str(tid) not in TANK_CACHE]
            logger.info("Tank IDs faltando no cache: %d", len(missing))

            if missing:
                for i in range(0, len(missing), ENCYCLOPEDIA_BATCH):
                    batch = missing[i:i + ENCYCLOPEDIA_BATCH]
                    ids_param = ",".join(str(x) for x in batch)
                    try:
                        meta_url = f"{WOT_REALM}/wot/encyclopedia/vehicles/?application_id={WOT_APP_ID}&tank_id={ids_param}"
                        rmeta = await client.get(meta_url)
                        rmeta.raise_for_status()
                        meta_js = rmeta.json()
                        data = meta_js.get("data", {}) or {}
                        returned = 0
                        for k, v in data.items():
                            if v:
                                TANK_CACHE[str(k)] = v
                                returned += 1
                        logger.info("Batch encyclopedia fetched: requested %d, returned %d", len(batch), returned)
                        try:
                            save_tank_cache(TANK_CACHE)
                        except Exception:
                            logger.exception("Falha ao salvar tank cache incremental.")
                    except Exception as exc:
                        logger.exception("Erro batch encyclopedia (vehicles): %s", exc)
                    await asyncio.sleep(SLEEP_BETWEEN_BATCHES)

                missing_after = [tid for tid in unique_tank_ids if str(tid) not in TANK_CACHE]
                logger.info("Missing after batch fetch: %d", len(missing_after))

                if len(missing_after) > 0 and len(missing_after) > 0.25 * max(1, len(unique_tank_ids)):
                    try:
                        logger.info("Fazendo fallback: baixando lista completa de vehicles para popular cache (apenas uma vez).")
                        full_url = f"{WOT_REALM}/wot/encyclopedia/vehicles/?application_id={WOT_APP_ID}"
                        rf = await client.get(full_url, timeout=60)
                        rf.raise_for_status()
                        fj = rf.json()
                        all_data = fj.get("data", {}) or {}
                        for k, v in all_data.items():
                            TANK_CACHE[str(k)] = v
                        try:
                            save_tank_cache(TANK_CACHE)
                        except Exception:
                            logger.exception("Falha ao salvar tank cache após full dump.")
                        logger.info("Full vehicles dump populou cache com %d entries (aprox).", len(TANK_CACHE))
                    except Exception as exc:
                        logger.exception("Falha no fallback full vehicles list: %s", exc)

            logger.info("Tank cache size após fetch: %d", len(TANK_CACHE))

            # 4) persist GarageTank: remove old tanks for each account and insert relevant ones (tiers 6/8/10)
            saved_tanks = 0
            with Session(engine) as s:
                for acc, items in account_tanks_map.items():
                    try:
                        s.exec(delete(GarageTank).where(GarageTank.account_id == acc))
                        s.commit()
                    except Exception:
                        s.rollback()

                    for it in items:
                        try:
                            tid = int(it.get("tank_id") or it.get("tankId") or 0)
                        except Exception:
                            continue
                        if not tid:
                            continue
                        meta = TANK_CACHE.get(str(tid), {}) or {}
                        tier = meta.get("tier") or meta.get("level") or None
                        try:
                            tier = int(tier) if tier is not None else None
                        except Exception:
                            tier = None

                        if tier not in (6, 8, 10):
                            continue

                        name = meta.get("name") or meta.get("localized_name") or f"Tank {tid}"
                        stats = it.get("statistics") or {}
                        mark = it.get("mark_of_mastery") if "mark_of_mastery" in it else it.get("mark_of_mastery", None)
                        battles = stats.get("battles") or 0
                        wins = stats.get("wins") or 0

                        gt = GarageTank(
                            account_id=acc,
                            tank_id=tid,
                            tank_name=name,
                            tier=tier,
                        )

                        try:
                            if hasattr(gt, "battles"):
                                gt.battles = int(battles)
                            if hasattr(gt, "wins"):
                                gt.wins = int(wins)
                            if hasattr(gt, "mark_of_mastery") and mark is not None:
                                gt.mark_of_mastery = int(mark)
                            if hasattr(gt, "raw_stats"):
                                gt.raw_stats = json.dumps(it)
                            if hasattr(gt, "last_updated"):
                                gt.last_updated = int(time.time())
                        except Exception:
                            pass

                        s.add(gt)
                        saved_tanks += 1
                s.commit()

            logger.info("Sync concluído! Tanks gravados: %d", saved_tanks)

    except Exception as exc:
        logger.exception("Erro inesperado no sync: %s", exc)
    finally:
        LAST_SYNC_TS = int(time.time())
        SYNC_RUNNING = False

# -----------------------------
# /sync/check endpoint (triggers background sync if DB empty)
# -----------------------------
@app.get("/sync/check")
def sync_check(background_tasks: BackgroundTasks, current_user = Depends(get_current_user_from_cookie)):
    try:
        with Session(engine) as s:
            cnt_res = s.exec(select(GarageTank)).all()
            total = len(cnt_res)
    except Exception as exc:
        logger.exception("Erro ao contar GarageTank: %s", exc)
        return JSONResponse({"status": "error", "msg": "Erro ao verificar DB"}, status_code=500)

    if total > 0:
        return JSONResponse({"status": "ok", "found": total})

    # wrapper to run async fetch in background thread (safe)
    def _run_sync_task():
        try:
            asyncio.run(fetch_and_sync())
        except Exception as e:
            logger.exception("fetch_and_sync background task failed: %s", e)

    background_tasks.add_task(_run_sync_task)
    return JSONResponse({"status": "started", "msg": "Sync em background iniciado. Aguarde alguns instantes."})

# -----------------------------
# Optional status endpoint
# -----------------------------
@app.get("/sync/status")
def sync_status(current_user = Depends(get_current_user_from_cookie)):
    return JSONResponse({
        "status": "running" if SYNC_RUNNING else "idle",
        "last_sync_ts": LAST_SYNC_TS,
        "tank_cache_size": len(TANK_CACHE),
    })

# -----------------------------
# Startup: DB init, include routers, scheduler
# -----------------------------
@app.on_event("startup")
async def on_startup():
    logger.info("Startup: inicializando DB e scheduler")
    # create tables
    init_db()

    # include routers late to avoid circular import issues
    try:
        from app.api.auth import router as auth_router
        app.include_router(auth_router, prefix="/auth")
        logger.info("Auth router registrado.")
    except Exception:
        logger.exception("Falha ao registrar auth router. Verifique app.api.auth.")

    try:
        from app.api.admin import router as admin_router
        app.include_router(admin_router)
        logger.info("Admin router registrado.")
    except Exception:
        logger.exception("Falha ao registrar admin router.")

    # ensure data dir
    try:
        from pathlib import Path
        Path("data").mkdir(parents=True, exist_ok=True)
    except Exception:
        pass

    # schedule periodic job (every 20 minutes)
    scheduler = AsyncIOScheduler()
    # APScheduler accepts coroutine functions with AsyncIOScheduler in recent versions.
    scheduler.add_job(fetch_and_sync, "interval", minutes=20)
    scheduler.start()
    logger.info("Scheduler iniciado (fetch_and_sync a cada 20 minutos).")