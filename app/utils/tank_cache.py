# app/utils/tank_cache.py
import json
from pathlib import Path
from typing import Dict, Any

CACHE_PATH = Path('data/tank_cache.json')

def load_tank_cache() -> Dict[str, Any]:
    if not CACHE_PATH.exists():
        return {}
    try:
        with open(CACHE_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}

def save_tank_cache(cache: Dict[str, Any]):
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CACHE_PATH, 'w', encoding='utf-8') as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)
