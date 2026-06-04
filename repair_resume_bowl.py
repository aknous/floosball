"""One-shot repair: re-point simulation_state at the completed-round-3 checkpoint
so the next restart resumes straight into the Floos Bowl.

Use when a pre-fix run left in_playoffs=False/current_week=0 in the DB while the
playoff_state JSON still holds completedRound=3. Stop the sim BEFORE running this.

    python repair_resume_bowl.py
"""
import json
import sqlite3

DB = "data/floosball.db"

conn = sqlite3.connect(DB)
cur = conn.cursor()

row = cur.execute(
    "SELECT current_season, playoff_state FROM simulation_state WHERE id=1"
).fetchone()
if not row:
    raise SystemExit("No simulation_state row found.")

season, rawState = row
if not rawState:
    raise SystemExit("playoff_state is empty — nothing to resume. Run a fresh sim instead.")

state = json.loads(rawState)
completedRound = state.get("completedRound")
roundText = state.get("roundText") or "League Championship"
if not completedRound:
    raise SystemExit("playoff_state has no completedRound — cannot resume.")

week = 28 + completedRound
cur.execute(
    "UPDATE simulation_state SET in_playoffs=1, in_offseason=0, is_active=1, "
    "current_week=?, playoff_round=? WHERE id=1",
    (week, roundText),
)
conn.commit()
conn.close()

print(f"Repaired: season={season}, in_playoffs=1, current_week={week}, "
      f"playoff_round='{roundText}' (completedRound={completedRound}).")
print("Restart with --timing=sequential to resume into the next round (the Floos Bowl).")
