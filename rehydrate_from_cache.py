# scripts/rehydrate_from_cache.py
import os
import json
import time
from typing import Dict, Any

from sqlmodel import Session, select
from dotenv import load_dotenv

# garantir que o package 'app' esteja importável (execute a partir da raiz do projeto)
load_dotenv()

from app.db import engine
from app.models import GarageTank, Player

CACHE_PATH = os.getenv("TANK_CACHE_PATH", "data/tank_cache.json")
BATCH_SIZE = int(os.getenv("REHYDRATE_BATCH_SIZE", "200"))

def load_tank_cache(path: str = CACHE_PATH) -> Dict[str, Any]:
    if not os.path.exists(path):
        print(f"[WARN] cache não encontrado em {path}")
        return {}
    with open(path, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except Exception as e:
            print(f"[ERROR] Falha ao carregar cache JSON: {e}")
            return {}

def pick_image_from_meta(meta: dict) -> str | None:
    # extrai melhor imagem disponível (big_icon, contour, small_icon, fallback)
    imgs = meta.get("images") or {}
    for key in ("big_icon", "contour_icon", "small_icon", "small", "big"):
        if imgs.get(key):
            return imgs.get(key)
    # fallback para default_profile.icon ou paths conhecidos
    dp = meta.get("default_profile") or {}
    if isinstance(dp, dict):
        icon = dp.get("icon") or dp.get("image")
        if icon:
            return icon
    return None

def rehydrate_from_cache():
    tcache = load_tank_cache()
    if not tcache:
        print("[WARN] cache vazio — nada a fazer.")
        return

    updated = 0
    skipped = 0
    no_meta = 0
    now_ts = int(time.time())

    # Query all GarageTank entries (we'll update only if fields missing)
    with Session(engine) as s:
        q = select(GarageTank)
        all_rows = s.exec(q).all()
        total = len(all_rows)
        print(f"[INFO] Found {total} GarageTank rows to inspect.")

        # Iterate in batches to commit incrementalmente
        for i in range(0, total, BATCH_SIZE):
            batch = all_rows[i:i+BATCH_SIZE]
            for gt in batch:
                try:
                    tid = getattr(gt, "tank_id", None)
                    if not tid:
                        skipped += 1
                        continue
                    meta = tcache.get(str(tid)) or tcache.get(int(tid)) or {}
                    if not meta:
                        no_meta += 1
                        # nada a preencher a partir do cache, pular
                        continue

                    changed = False

                    # is_premium
                    if (not hasattr(gt, "is_premium") or getattr(gt, "is_premium") in (None, False)):
                        if hasattr(gt, "is_premium"):
                            val = bool(meta.get("is_premium", False))
                            setattr(gt, "is_premium", val)
                            changed = True

                    # nation (pode vir como 'nation' ou 'country')
                    if (not hasattr(gt, "nation") or not getattr(gt, "nation")):
                        if hasattr(gt, "nation"):
                            nat = meta.get("nation") or meta.get("country") or meta.get("nation_name")
                            if nat:
                                setattr(gt, "nation", str(nat))
                                changed = True

                    # type / vehicle type
                    if (not hasattr(gt, "type") or not getattr(gt, "type")):
                        if hasattr(gt, "type"):
                            vtype = meta.get("type") or meta.get("vehicle_type")
                            if vtype:
                                setattr(gt, "type", str(vtype))
                                changed = True

                    # name (sometimes present but check)
                    if hasattr(gt, "tank_name") and (not getattr(gt, "tank_name") or getattr(gt, "tank_name").startswith("Tank ")):
                        name = meta.get("name") or meta.get("short_name") or meta.get("localized_name")
                        if name:
                            setattr(gt, "tank_name", str(name))
                            changed = True

                    # image_url
                    if (hasattr(gt, "image_url") and (not getattr(gt, "image_url"))):
                        img = pick_image_from_meta(meta)
                        if img:
                            setattr(gt, "image_url", img)
                            changed = True

                    # raw_json / raw_stats: we will store the metadata (not the player's stats)
                    # Prefer field raw_json; fallback raw_stats
                    meta_blob = None
                    if hasattr(gt, "raw_json"):
                        current = getattr(gt, "raw_json")
                        if not current:
                            meta_blob = json.dumps(meta)
                            setattr(gt, "raw_json", meta_blob)
                            changed = True
                    elif hasattr(gt, "raw_stats"):
                        current = getattr(gt, "raw_stats")
                        if not current:
                            meta_blob = json.dumps(meta)
                            setattr(gt, "raw_stats", meta_blob)
                            changed = True

                    # last_updated
                    if hasattr(gt, "last_updated"):
                        # atualiza para agora se estiver vazio ou muito antigo
                        cur_ts = getattr(gt, "last_updated") or 0
                        if not cur_ts or (now_ts - int(cur_ts) > 60*60*24):  # 1 dia
                            setattr(gt, "last_updated", now_ts)
                            changed = True

                    if changed:
                        s.add(gt)
                        updated += 1
                    else:
                        skipped += 1

                except Exception as e:
                    print(f"[ERROR] falha ao processar tank_id={getattr(gt,'tank_id',None)}: {e}")
                    s.rollback()

            # commit batch
            try:
                s.commit()
            except Exception as e:
                print(f"[ERROR] commit falhou no batch: {e}")
                s.rollback()

    print(f"[RESULT] Rehydrate finished. updated={updated}, skipped={skipped}, no_meta={no_meta}")

if __name__ == "__main__":
    rehydrate_from_cache()