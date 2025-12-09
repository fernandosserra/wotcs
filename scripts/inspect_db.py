# scripts/inspect_db.py
from sqlalchemy import inspect, text
from app.db import engine
from app.models import GarageTank, Player
import traceback

print("ENGINE URL:", engine.url)

inspector = inspect(engine)
print("TABLES visible to engine:", inspector.get_table_names())

tbl = "garagetank"
if tbl in inspector.get_table_names():
    print(f"\nColumns in DB table '{tbl}':")
    for c in inspector.get_columns(tbl):
        print("  -", c["name"], ":", c["type"])
else:
    print(f"\nTable '{tbl}' NOT found.")

print("\nModel GarageTank columns (SQLModel):")
try:
    print(list(GarageTank.__table__.columns.keys()))
except Exception:
    print("Failed reading GarageTank.__table__")
    traceback.print_exc()

print("\nTrying a simple SELECT 1 from garagetank (safe):")
try:
    with engine.connect() as conn:
        res = conn.execute(text(f"SELECT count(*) FROM {tbl}"))
        print("Row count:", res.scalar())
except Exception:
    print("Error when selecting from garagetank:")
    traceback.print_exc()

# Try a SQLModel query (to reproduce what your app does)
from sqlmodel import Session, select
try:
    with Session(engine) as s:
        q = select(GarageTank)
        rows = s.exec(q).all()
        print(f"SQLModel can select {len(rows)} GarageTank rows (showing first 2):")
        for r in rows[:2]:
            print(" ", r)
except Exception:
    print("SQLModel select failed:")
    traceback.print_exc()
