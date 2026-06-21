"""
test_db.py — Checkpoint 1 verification script.
Run with: python test_db.py
"""
import sqlite3
from db import create_tables
from db import SessionLocal
from models import Session

# Trigger table creation
create_tables()

# Verify by inspecting the SQLite file directly
conn = sqlite3.connect("lodestone.db")
cur = conn.cursor()
cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
tables = [row[0] for row in cur.fetchall()]
conn.close()

print("Tables in lodestone.db:", tables)
assert "sessions" in tables, "MISSING: sessions table"
assert "student_sks" in tables, "MISSING: student_sks table"
assert "cohort_events" in tables, "MISSING: cohort_events table"
print("PASS: All 3 tables verified. Checkpoint 1 COMPLETE.")

# -----------------------------
# CRUD Test
# -----------------------------
db = SessionLocal()

try:
    # Create
    test_session = Session(
        id="test-001",
        student_id="nakul",
        problem_id="p1",
        state_json="{}",
        phase="spec_gate"
    )

    db.add(test_session)
    db.commit()

    # Read
    result = db.query(Session).filter_by(id="test-001").first()
    print("Retrieved student_id:", result.student_id)

    # Delete
    db.delete(result)
    db.commit()

    print("PASS: CRUD operations verified.")

finally:
    db.close()