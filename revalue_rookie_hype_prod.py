"""PROD one-off: re-value already-minted Rookie Hype cards to the 8.0/rookie scale.

SELF-CONTAINED on purpose — it does NOT import managers.cardEffects, because the
code deployed on the fly machine may still carry the OLD builder constant (8.4).
The new formula is hardcoded here so it produces the correct value regardless of
what's deployed.

Effect params are frozen in card_templates.effect_config at mint time, so a
builder-constant change never touches already-minted cards. This rewrites
perRookieFP (+ the detail string) for CURRENT-SEASON rookie_hype templates only —
the sole cards that can be equipped/score. Historical seasons are left as-is.

Reproduces mint-time _RATING_DAMPENING (holo = 0.5) exactly.

Run on the fly machine (no sqlite3 binary there — this is pure python3 + stdlib):
    DRY-RUN:  python3 revalue_rookie_hype_prod.py
    APPLY:    python3 revalue_rookie_hype_prod.py --apply
Idempotent — a second run reports everything already-current.
"""
import argparse, json, sqlite3

DB_DEFAULT = "/data/floosball.db"     # prod path
EFFECT = "rookie_hype"

# ── New builder math, hardcoded (mirrors cardEffects._buildFlatFPParams @ base 13.7) ──
#   perRookieFP = round((13.7 + rn*0.27) * editionScale(1.0) * _BAL_FP_MULT(0.5), 1)
#   rn = dampenedRating - 60 ;  dampenedRating = 60 + (rating-60)*dampening
_BASE = 13.7
_SLOPE = 0.27
_BAL_FP_MULT = 0.5
_RATING_DAMPENING = {"base": 1.0, "holographic": 0.5, "prismatic": 0.25, "diamond": 0.0}


def freshPerRookie(edition, rating):
    dampening = _RATING_DAMPENING.get(edition, 1.0)
    rn = (60 + (rating - 60) * dampening) - 60
    return round((_BASE + rn * _SLOPE) * 1.0 * _BAL_FP_MULT, 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=DB_DEFAULT)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--season", type=int, default=None)
    args = ap.parse_args()

    con = sqlite3.connect(args.db)
    cur = con.cursor()

    season = args.season
    if season is None:
        cur.execute("SELECT MAX(season_number) FROM seasons")
        season = cur.fetchone()[0]
    print("DB=%s  target season_created=%s  effect=%s  mode=%s\n" % (
        args.db, season, EFFECT, "APPLY" if args.apply else "DRY-RUN"))

    cur.execute("SELECT id, edition, player_rating, effect_config FROM card_templates "
                "WHERE season_created = ?", (season,))
    changes = []
    for tid, edition, rating, ec in cur.fetchall():
        try:
            cfg = json.loads(ec) if ec else {}
        except Exception:
            cfg = {}
        if (cfg.get("effectName") or "") != EFFECT:
            continue
        primary = cfg.get("primary") or {}
        oldVal = primary.get("perRookieFP")
        newVal = freshPerRookie(edition or "holographic", rating)
        if oldVal == newVal:
            print("  tid=%s r%s %s: perRookieFP=%s (already current, skip)" % (
                tid, rating, edition, oldVal))
            continue
        primary["perRookieFP"] = newVal
        cfg["primary"] = primary
        cfg["detail"] = "+%s FP per rookie on your roster" % newVal
        changes.append((tid, json.dumps(cfg)))
        print("  tid=%s r%s %s: perRookieFP %s -> %s" % (tid, rating, edition, oldVal, newVal))

    print("\n%d template(s) to update." % len(changes))
    if not changes:
        con.close(); return
    if not args.apply:
        print("DRY-RUN - no changes written. Re-run with --apply to commit.")
        con.close(); return
    for tid, cfgJson in changes:
        cur.execute("UPDATE card_templates SET effect_config = ? WHERE id = ?", (cfgJson, tid))
    con.commit()
    print("APPLIED - %d template(s) updated." % len(changes))
    con.close()


if __name__ == "__main__":
    main()
