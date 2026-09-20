"""The scouted view of a draft prospect — what a club BELIEVES, and what it shows.

A prospect must not show his true numbers. The uncertainty is the feature: it is
what makes a pick worth arguing about, what gives the Scouting Department a job,
and what makes trading a pick a real decision rather than an arithmetic one.

⚠️ WHAT IS KNOWN vs WHAT IS SCOUTED. Current rating is a FACT — he exists and plays
at that level. POTENTIAL is the scouted quantity, and it is shown as a band.

⚠️ THE VIEW IS PER (CLUB, PROSPECT), SO THERE IS NO SINGLE "THE CLASS" VIEW. A team
page shows that club's read; the league-wide list shows the viewing user's favourite
club's read. Two fans of different clubs looking at the same prospect see different
ranges, and that is the feature working rather than an inconsistency.

BELIEF AND RANGE ARE DIFFERENT THINGS, and conflating them leads to the wrong
implementation:

    belief   a single number, truePotential + draw x band.   Used by the GM: draft
             board, trade valuation, promotion.
    range    belief +- band, clamped.                        Used by a human. It is
             how the uncertainty is SHOWN.

The GM never acts on a range. It acts on its belief, which may be wrong, and the
range is the honest statement of how wrong it could be. Two clubs with identical
scouting and opposite opinions of a true-88 prospect believe 94 and 81 and pay
accordingly — same player, and each range still contains the truth.

See docs/PROSPECT_DRAFT_PLAN.md §1b.
"""

import hashlib
import random

from constants import (SCOUTING_BANDS, SCOUT_BAND_EARLY, SCOUT_BAND_LATE,
                       FO_SCOUT_VISION_FLOOR, FO_SCOUT_VISION_CEILING,
                       SCOUT_ERROR_SIGMA_FRACTION, GM_ACTIVE_WEEK)

# Ratings cap here (`floosball_player`: min(100, ...)); prod's highest potential is
# exactly 100. A band MUST be clamped or the UI prints impossible numbers.
RATING_CEILING = 100


def _clamp(value, low, high):
    return max(low, min(high, value))


def bandFor(vision: float) -> float:
    """Half-width of the potential band, in rating points, at this club's vision.

    `vision` is `frontOfficeBrain.scoutingVision` output — 0..1 — which is the one
    definition of how well a front office sees. ⚠️ `SCOUTING_BANDS` is keyed on the
    60-100 ATTRIBUTE scale, so the two have to be reconciled here rather than at each
    call site; the vision normalisation is exactly `(raw - FLOOR) / (CEILING - FLOOR)`,
    so this inverts it.
    """
    vision = max(0.0, min(1.0, float(vision or 0.0)))
    accuracy = FO_SCOUT_VISION_FLOOR + vision * (FO_SCOUT_VISION_CEILING - FO_SCOUT_VISION_FLOOR)
    for threshold, width in SCOUTING_BANDS:
        if accuracy >= threshold:
            return float(width)
    return float(SCOUTING_BANDS[-1][1])


def seasonProgress(week: int) -> float:
    """0.0 in week 1, 1.0 at the TRADE DEADLINE.

    ⚠️ THE RAMP ENDS AT `GM_ACTIVE_WEEK` (22), NOT AT WEEK 28, and the difference is
    the whole reason the ramp exists. The band narrows so that "a pick traded in week 3
    is speculation on a blurry class, and the same pick at week 22 is a priced asset
    both clubs can see" — so it has to be at its tightest by the moment the market
    closes and the roster freezes, not four weeks after nobody can act on it.

    Anchored here, all four rows of the plan's own worked table reproduce exactly
    (±14 / ±10 / ±7 / ±4 at weeks 1 / 8 / 15 / 22 on the ±10 tier). Anchored at 28 they
    do not — week 22 would still be showing ±6.2.

    Clamped at both ends, because the playoffs and the whole offseason sit past the
    deadline and a club that has watched a prospect all year does not un-learn him.
    """
    span = max(1, int(GM_ACTIVE_WEEK) - 1)
    return max(0.0, min(1.0, (int(week or 1) - 1) / span))


def bandWidth(vision: float, week: int) -> float:
    """The band a club actually sees, narrowed by how long it has been watching."""
    scale = SCOUT_BAND_EARLY - (SCOUT_BAND_EARLY - SCOUT_BAND_LATE) * seasonProgress(week)
    return bandFor(vision) * scale


def standingDraw(viewerId, prospectId, season: int) -> float:
    """This club's fixed opinion of this prospect, as a standard normal.

    ⚠️ DRAWN DETERMINISTICALLY, NOT STORED. `_scoutError` is the right model and gets
    two things right that this needs — the draw is held rather than re-rolled, so a GM
    who overrates a player overrates him consistently (on the board, at the pick, and
    in a trade); and it is stored as a STANDARD NORMAL, so the same opinion RESCALES
    when vision changes. A club that upgrades its Scouting Department mid-season sees
    its view TIGHTEN AROUND THE OPINION IT ALREADY HELD rather than jump to a different
    one, which is exactly the behaviour a fan should see after an upgrade.

    ⚠️ BUT ITS STORAGE WILL NOT DO HERE. `_scoutBeliefs` is an in-memory dict on a brain
    that lives ONE OFFSEASON (`_foBrainForOffseason`). A scouted view is fan-facing,
    season-long, and must survive every restart and deploy — a supporter checking the
    class on Monday and again on Thursday cannot be shown different numbers. So it is
    derived instead: no table, no cache, no migration, and identical before and after a
    deploy.

    ⚠️ NOT THE BUILT-IN `hash()`, WHICH IS PROCESS-RANDOMISED. `PYTHONHASHSEED` is random
    per interpreter for str and bytes, so `Random(hash(seed))` would hand every deploy a
    different set of opinions — the precise failure this function exists to prevent, and
    it would be invisible in a single-process test. md5 is stable everywhere.

    ⚠️ THE SEASON IS IN THE SEED ON PURPOSE: a club's read should reset for next year's
    class, not inherit last year's luck.
    """
    key = f"scout:{viewerId}:{prospectId}:{season}".encode()
    seed = int(hashlib.md5(key).hexdigest()[:16], 16)
    return random.Random(seed).gauss(0.0, 1.0)


def believedPotential(truePotential: float, viewerId, prospectId,
                      season: int, vision: float, week: int) -> float:
    """What this club thinks the prospect's ceiling is. The number the GM ACTS on."""
    band = bandWidth(vision, week)
    if band <= 0:
        return float(truePotential)
    # ⚠️ THE ERROR IS DRAWN AT A FRACTION OF THE BAND, not at the band itself. At the
    # full width, `belief ± band` contains the truth only when |draw| <= 1, so one club
    # in three would be shown a range the real number falls outside — a wrong answer
    # wearing error bars. See SCOUT_ERROR_SIGMA_FRACTION.
    sigma = band * SCOUT_ERROR_SIGMA_FRACTION
    return float(truePotential) + standingDraw(viewerId, prospectId, season) * sigma


def scoutedView(prospect, viewerId, season: int, vision: float, week: int,
                truePotential: float = None, currentRating: float = None) -> dict:
    """The fan-facing payload for one (club, prospect) pair.

    ⚠️ THE BAND HAS TO BE APPLIED SERVER-SIDE. Sending true potential to the client and
    hiding it in the UI leaks it to anyone who opens the network tab.

    ⚠️ THE CLAMP IS INFORMATIVE, NOT JUST A CORRECTNESS FIX. Near the top of the scale
    the range goes ASYMMETRIC, and that asymmetry is real information — "could be
    maxed" is exactly the signal a scout would have. A true-97 prospect seen by a ±10
    club shows 91-100 in week 1 and 95-100 in week 22, so an elite prospect still LOOKS
    elite through a wide band, which is what makes the top of a class legible to a fan
    in week 1. That is also why the clamp sits on the DISPLAYED RANGE rather than on the
    underlying draw: clamping the draw would quietly pull the belief down and destroy
    the asymmetry that carries the signal.

    ⚠️ THE LOW END IS FLOORED AT HIS CURRENT RATING, not at zero. Potential is
    `trueSkill + headroom` and trueSkill is at or above current by construction, so a
    ceiling BELOW what he already plays at is not an uncertain read, it is an
    impossible one.
    """
    if truePotential is None:
        truePotential = prospect.computeCeilingRating()
    if currentRating is None:
        currentRating = getattr(prospect, 'playerRating', 0) or 0
    band = bandWidth(vision, week)
    belief = believedPotential(truePotential, viewerId,
                               getattr(prospect, 'id', 0), season, vision, week)
    # ⚠️ BOTH ENDS ARE CLAMPED INTO THE SAME INTERVAL, which is what makes the two
    # invariants hold BY CONSTRUCTION rather than by a repair step. Clamping one end and
    # then patching the other against it fails at both extremes, and each failure was
    # real: a club that reads him as going nowhere printed a ceiling BELOW his current
    # rating, and a club that reads him as a superstar printed 105. Since
    # `belief - band <= belief + band`, clamping both into [current, 100] cannot invert
    # them, so there is no ordering repair to get wrong.
    floor = min(float(currentRating), float(RATING_CEILING))
    low = _clamp(belief - band, floor, RATING_CEILING)
    high = _clamp(belief + band, floor, RATING_CEILING)
    exact = int(round(truePotential)) if band <= 0 else None
    return {
        "low": int(round(low)),
        "high": int(round(high)),
        "exact": exact,
        "band": round(band, 1),
    }
