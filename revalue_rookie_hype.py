"""One-off: re-value already-minted Rookie Hype cards to the current builder.

Effect params are frozen in card_templates.effect_config at mint time, so the
8.0/rookie retune only affects newly-minted cards. This rewrites perRookieFP (and
the detail string) for CURRENT-SEASON rookie_hype templates in place, reproducing
the mint-time _RATING_DAMPENING so the value exactly matches a fresh mint.

Scope: current-season templates only (season_created == current season) — those
are the only cards that can be equipped/score. Historical seasons are left as-is.

Dry-run by default. Pass --apply to write. Idempotent.

    python3 revalue_rookie_hype.py            # dry-run, show diff
    python3 revalue_rookie_hype.py --apply    # commit
    python3 revalue_rookie_hype.py --db data/other.db --apply
"""
import argparse, json, sqlite3, sys

from managers.cardEffects import (
    _buildFlatFPParams, EFFECT_DETAIL_TEMPLATES, EFFECT_EDITION_TIER,
)

# Mirror buildEffectConfig's dampening (cardEffects.py) — rebuildPrimaryParams does NOT.
_RATING_DAMPENING = {"base": 1.0, "holographic": 0.5, "prismatic": 0.25, "diamond": 0.0}
EFFECT = "rookie_hype"


def freshPerRookie(edition: str, rating: int) -> float:
    dampening = _RATING_DAMPENING.get(edition, 1.0)
    dampenedRating = 60 + (rating - 60) * dampening
    return _buildFlatFPParams(EFFECT, dampenedRating, 1.0)["perRookieFP"]


def rebuiltDetail(perRookieFP) -> str:
    tpl = EFFECT_DETAIL_TEMPLATES.get(EFFECT, "")
    return tpl.replace("{perRookieFP}", str(perRookieFP)) if tpl else ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="data/floosball.db")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--season", type=int, default=None,
                    help="Override target season (default: current = max season_number)")
    args = ap.parse_args()

    con = sqlite3.connect(args.db)
    cur = con.cursor()

    season = args.season
    if season is None:
        cur.execute("SELECT MAX(season_number) FROM seasons")
        season = cur.fetchone()[0]
    print(f"DB={args.db}  target season_created={season}  effect={EFFECT}  "
          f"mode={'APPLY' if args.apply else 'DRY-RUN'}\n")

    cur.execute(
        "SELECT id, edition, player_rating, effect_config FROM card_templates "
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
            print(f"  tid={tid} r{rating} {edition}: perRookieFP={oldVal} (already current, skip)")
            continue
        primary["perRookieFP"] = newVal
        cfg["primary"] = primary
        newDetail = rebuiltDetail(newVal)
        if newDetail:
            cfg["detail"] = newDetail
        changes.append((tid, rating, edition, oldVal, newVal, json.dumps(cfg)))
        print(f"  tid={tid} r{rating} {edition}: perRookieFP {oldVal} -> {newVal}")

    print(f"\n{len(changes)} template(s) to update.")
    if not changes:
        con.close(); return
    if not args.apply:
        print("DRY-RUN — no changes written. Re-run with --apply to commit.")
        con.close(); return

    for tid, _r, _e, _o, _n, cfgJson in changes:
        cur.execute("UPDATE card_templates SET effect_config = ? WHERE id = ?", (cfgJson, tid))
    con.commit()
    print(f"APPLIED — {len(changes)} template(s) updated.")
    con.close()


if __name__ == "__main__":
    main()
