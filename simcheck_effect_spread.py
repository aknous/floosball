"""Per-EFFECT power spread within one edition — the instrument for "some base cards
are way better to have equipped than others".

`simcheck_edition_power.py` answers whether an EDITION averages ~100% of a lineup's own
FP. It cannot answer this question, because it scores six random effects together: a
dead card and a monster card in the same hand net out to a fine-looking edition mean.

This isolates ONE effect at a time. Five of the six slots hold no-effect floor prints
(the `base` edition), the sixth holds the effect under test on a real player. Whatever
the score gains over raw player FP is that effect's marginal contribution, measured
against real week stats on real rosters.

Reported per effect:
  payFP / payFloo   mean marginal FP (and Floobits) the card adds
  hit%              share of trials where it paid ANYTHING — the number that separates
                    an unconditional card from one that needs its roster condition
  p10/p90           the floor and ceiling a user actually experiences

A high hit% with a healthy mean is a card you always want equipped. That combination is
what makes a "boring" base card strictly better than a conditional one at the same tier,
and it is invisible in any aggregate measurement.

Env: PROBE_EDITION (metallic), PROBE_TRIALS (60), PROBE_WEEK (14), PROBE_DB,
     PROBE_EFFECTS (comma-separated subset).
Run: .venv/bin/python simcheck_effect_spread.py
"""
import asyncio, os, random, shutil, statistics, tempfile, logging

DB = os.environ.get('PROBE_DB', 'data/floosball_prod_latest.db')
WEEK = int(os.environ.get('PROBE_WEEK', '14'))
TRIALS = int(os.environ.get('PROBE_TRIALS', '60'))
EDITION = os.environ.get('PROBE_EDITION', 'metallic')
SEED = 90210

tmp = tempfile.mkdtemp(prefix='floos_effspread_')
shutil.copy(DB, os.path.join(tmp, 'floosball.db'))
os.environ['DATABASE_DIR'] = tmp
logging.disable(logging.WARNING)

from simcheck_cards import boot, preloadSeason, applyWeekState
container, app = asyncio.run(boot())
from database.connection import get_session
from database.models import (FantasyRoster, EquippedCard, UserCard, CardTemplate,
                             Game, GamePlayerStats, WeeklyPlayerFP, Player)
from sqlalchemy import func
from managers.cardProjection import buildProjectionContext
from managers.cardEffectCalculator import calculateWeekCardBonuses, aggregateMultFactors
from managers.cardManager import SLOT_TO_ORDINAL
from managers.cardEffects import (buildEffectConfig, EFFECT_EDITION_TIER,
                                  EFFECT_DISPLAY_NAMES, effectValidPositions)

sm = getattr(app, 'seasonManager', None) or container.getService('season_manager')
pm = getattr(app, 'playerManager', None) or container.getService('player_manager')
s = get_session()
season = s.query(func.max(FantasyRoster.season)).scalar()
teamGames, byWeek, eloByTeam = preloadSeason(s, season)

from managers.fantasyTracker import _dbStatsToCardFormat
weekFP = {r.player_id: r.fantasy_points
          for r in s.query(WeeklyPlayerFP).filter_by(season=season, week=WEEK).all()}
REAL = {}
for gps in (s.query(GamePlayerStats).join(Game, GamePlayerStats.game_id == Game.id)
            .filter(Game.season == season, Game.week == WEEK).all()):
    REAL[gps.player_id] = _dbStatsToCardFormat(
        gps.passing_stats, gps.rushing_stats, gps.receiving_stats, gps.kicking_stats,
        weekFP.get(gps.player_id, 0), teamId=gps.team_id)
    if gps.q4_fantasy_points:
        REAL[gps.player_id]["q4FantasyPoints"] = gps.q4_fantasy_points
for pid, fp in weekFP.items():
    REAL.setdefault(pid, _dbStatsToCardFormat({}, {}, {}, {}, fp))

byPos = {}
for p in s.query(Player).all():
    if p.position is None:
        continue
    byPos.setdefault(int(p.position), []).append(p)
for pos in byPos:
    byPos[pos] = [p for p in byPos[pos] if (weekFP.get(p.id, 0) or 0) > 0]

SLOTS = [('QB', 1), ('RB', 2), ('WR1', 3), ('WR2', 3), ('TE', 4), ('K', 5)]
user = s.query(FantasyRoster).filter_by(season=season).first().user_id

# Season performance ratings live in memory during a season, so a booted snapshot has
# them all at 0 and every over/underperformer effect (Resplendent, Windfall, Buy Low,
# Reclamation, Rising Tide) counts zero players and reads as a dead card. That is an
# instrument artifact, not a balance finding, so restore the season stats first and let
# the real rating pass run off them.
pm.loadCurrentSeasonStats(season, currentWeek=WEEK)
_perf = sum(1 for p in pm.activePlayers if (getattr(p, 'seasonPerformanceRating', 0) or 0) > 0)
if not _perf:
    print("WARNING: no season performance ratings — over/underperformer effects will "
          "read as dead cards. Treat their rows as unmeasured, not as zero.")

_cols = {c.name for c in CardTemplate.__table__.columns} - {'id', 'created_at'}
_anySrc = s.query(CardTemplate).first()


def synth(effectName, edition, player, pos):
    """A card template for `effectName` on `player`, built with the CURRENT builder so
    the live gate + EDITION_POWER_SCALE apply (the prod snapshot predates both)."""
    data = {c: getattr(_anySrc, c) for c in _cols}
    rating = int(getattr(player, 'player_rating', 80) or 80)
    data.update(player_id=player.id, player_name=getattr(player, 'name', '') or 'Probe',
                team_id=getattr(player, 'team_id', None), player_rating=rating,
                position=pos, edition=edition, classification=None,
                effect_config=buildEffectConfig(edition, rating, pos,
                                                forceEffect=effectName))
    t = CardTemplate(**data)
    s.add(t)
    s.flush()
    return t


def scoreLineup(lineup, effectName, testSlot):
    """Score a lineup whose only live effect sits in `testSlot`; the rest are no-effect
    floor prints. `effectName=None` scores the all-floor CONTROL. Returns
    (scoreOverRawFP, floobits, rawPlayerFP)."""
    s.query(EquippedCard).filter_by(user_id=user, season=season, week=WEEK).delete()
    s.flush()
    for slot, pos, player in lineup:
        if slot == testSlot and effectName is not None:
            t = synth(effectName, EDITION, player, pos)
        else:
            t = synth(None, 'base', player, pos)   # no-effect floor print
        uc = UserCard(user_id=user, card_template_id=t.id, acquired_via='probe', tier=1)
        s.add(uc)
        s.flush()
        s.add(EquippedCard(user_id=user, season=season, week=WEEK, slot=slot,
                           slot_number=SLOT_TO_ORDINAL.get(slot, 1),
                           user_card_id=uc.id, streak_count=1))
    s.flush()
    ctx = buildProjectionContext(s, user, season, WEEK, sm, pm)
    if ctx is None:
        return None
    applyWeekState(ctx, ctx.userFavoriteTeamId, WEEK, teamGames, byWeek, eloByTeam)
    # buildProjectionContext leaves the context in PROJECTION mode, where the FP power
    # bar returns a fractional clear PROBABILITY and every payout comes out EV-scaled.
    # Week-end banking is the live path: the bar is pure on/off. Measure what users
    # actually receive, not the projection they were shown.
    ctx.isProjection = False
    ctx.weekPlayerStats = {pid: REAL.get(pid, {}) for pid in ctx.rosterPlayerIds}
    ctx.weekRawFP = sum((st or {}).get('fantasyPoints', 0)
                        for st in ctx.weekPlayerStats.values())
    ctx.rosterTotalTds = sum(
        (st or {}).get('passing_stats', {}).get('tds', 0)
        + (st or {}).get('rushing_stats', {}).get('runTds', 0)
        + (st or {}).get('receiving_stats', {}).get('rcvTds', 0)
        for st in ctx.weekPlayerStats.values())
    eqs = s.query(EquippedCard).filter_by(user_id=user, season=season, week=WEEK).all()
    res = calculateWeekCardBonuses(eqs, ctx)
    mult = aggregateMultFactors(res.multFactors or [])
    raw = ctx.weekRawFP
    if raw <= 0:
        return None
    total = (raw + res.totalBonusFP) * mult
    return (total - raw, res.floobitsEarned or 0, raw)


def randomLineup(rng):
    used, out = set(), []
    for slot, pos in SLOTS:
        pool = [p for p in byPos.get(pos, []) if p.id not in used]
        if not pool:
            return None
        p = rng.choice(pool)
        used.add(p.id)
        out.append((slot, pos, p))
    return out


names = sorted(n for n, ed in EFFECT_EDITION_TIER.items() if ed == EDITION)
if os.environ.get('PROBE_EFFECTS'):
    want = {x.strip() for x in os.environ['PROBE_EFFECTS'].split(',')}
    names = [n for n in names if n in want]

BY_POSITION = os.environ.get('PROBE_BY_POSITION') == '1'

if BY_POSITION:
    # An effect's premise is usually written for ONE position ("per reception", "per
    # rush attempt") but the pool mints it on every position it isn't excluded from.
    # This pins the slot instead of sampling it, so a card that is dead on a QB and
    # huge on a WR shows as exactly that rather than as one noisy average.
    rng = random.Random(SEED)
    print(f"season {season} · week {WEEK} · edition {EDITION} · {TRIALS} trials/slot")
    print("same effect, minted on each position in turn\n")
    print(f"  {'effect':20} " + ' '.join(f'{sl:>8}' for sl, _ in SLOTS))
    for effectName in names:
        valid = effectValidPositions(effectName) or {1, 2, 3, 4, 5}
        cells = []
        for slot, pos in SLOTS:
            if pos not in valid:
                cells.append('     n/a')
                continue
            vals = []
            for _ in range(TRIALS):
                lineup = randomLineup(rng)
                if lineup is None:
                    continue
                try:
                    r = scoreLineup(lineup, effectName, slot)
                    s.rollback()
                    c = scoreLineup(lineup, None, slot)
                except Exception:
                    s.rollback()
                    break
                s.rollback()
                if r is not None and c is not None:
                    vals.append(r[0] - c[0])
            cells.append(f'{statistics.mean(vals):8.1f}' if vals else '       -')
        label = EFFECT_DISPLAY_NAMES.get(effectName, effectName)
        print(f"  {label[:20]:20} " + ' '.join(cells))
    print("\na flat row = the effect works the same wherever it mints;")
    print("a row with dead cells = the premise only fits some positions")
    shutil.rmtree(tmp, ignore_errors=True)
    raise SystemExit

rng = random.Random(SEED)
print(f"season {season} · week {WEEK} · edition {EDITION} · {TRIALS} trials/effect "
      f"· {len(names)} effects")
print("one live card per lineup; the other five slots are no-effect floor prints\n")
print(f"  {'effect':22} {'payFP':>7} {'hit%':>6} {'p10':>7} {'p90':>7} {'payFloo':>8}")

rows = []
for effectName in names:
    valid = effectValidPositions(effectName) or {1, 2, 3, 4, 5}
    fps, floos = [], []
    for _ in range(TRIALS):
        lineup = randomLineup(rng)
        if lineup is None:
            continue
        choices = [sl for sl, pos in SLOTS if pos in valid]
        if not choices:
            break
        testSlot = rng.choice(choices)
        try:
            # Same lineup, scored with and without the live card. Differencing removes
            # the team-stacking FPx the filler prints generate on their own — without it
            # every dead effect reads a phantom 1-2 FP and looks like it pays.
            r = scoreLineup(lineup, effectName, testSlot)
            s.rollback()
            ctrl = scoreLineup(lineup, None, testSlot)
        except Exception as e:
            s.rollback()
            print(f"  {effectName:22}  ERROR {type(e).__name__}: {e}")
            r = None
            break
        s.rollback()
        if r is not None and ctrl is not None:
            fps.append(r[0] - ctrl[0])
            floos.append(r[1] - ctrl[1])
    if not fps:
        continue
    fps.sort()
    hit = 100 * sum(1 for x in fps if abs(x) > 0.01 or False) / len(fps)
    hitAny = 100 * sum(1 for i, x in enumerate(fps) if abs(x) > 0.01) / len(fps)
    if statistics.mean(floos) > 0:
        hitAny = max(hitAny, 100 * sum(1 for f in floos if f > 0) / len(floos))
    rows.append((effectName, statistics.mean(fps), hitAny,
                 fps[int(0.1 * (len(fps) - 1))], fps[int(0.9 * (len(fps) - 1))],
                 statistics.mean(floos)))

for name, mean, hit, p10, p90, floo in sorted(rows, key=lambda r: -r[1]):
    label = EFFECT_DISPLAY_NAMES.get(name, name)
    print(f"  {label[:22]:22} {mean:7.1f} {hit:5.0f}% {p10:7.1f} {p90:7.1f} {floo:8.1f}")

if rows:
    means = [r[1] for r in rows]
    print(f"\n  spread: best {max(means):.1f} FP vs worst {min(means):.1f} FP "
          f"· median effect {statistics.median(means):.1f} FP")
    print("  a wide spread at one edition means the tier has strictly-better picks")
shutil.rmtree(tmp, ignore_errors=True)
