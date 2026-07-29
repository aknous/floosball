"""GM turnover — fired / retire / leave, all sim-decided (AFO plan Part C).

Three exit paths, each rolling the same replacement gamble. Because coaches are
SPECIALISTS (Part B), a replacement is better-or-worse **per dimension** rather
than a scalar up or down: fire a GM for botching the roster and you may land a
superb evaluator who is a worse gameday coach. That is the point — turnover is a
real trade, not a reroll on a quality number.

  1. fired   — poor record (and, once Part D lands, hostile fan sentiment)
               crossing the GM's own threshold. Replaces the `fire_coach` vote.
  2. retire  — the existing tenure curve (`Coach.shouldRetire`), untouched here.
  3. leave   — voluntary departure. Hooked to sentiment so a GM in a hostile
               fanbase can walk away EVEN WHILE WINNING, and so a well-run team
               can still lose a beloved GM.

**Sentiment is not built yet** (plan steps 4-6). Every entry point takes a
`sentiment` argument defaulting to neutral, exactly like
`frontOfficeBrain.sentimentTilt` — so wiring Part D later is a matter of passing
a real number, with no restructuring here.

Tuning target: a few GM changes league-wide per season, NOT a carousel.
"""

import logging
from random import Random

from constants import (
    GM_TURNOVER_ENABLED,
    GM_FIRE_BASELINE_WINPCT, GM_FIRE_SENSITIVITY, GM_FIRE_GRACE_SEASONS,
    GM_FIRE_GOODWILL_MAX, GM_FIRE_MAX_CHANCE,
    GM_LEAVE_BASE_CHANCE, GM_LEAVE_SENTIMENT_WEIGHT,
    GM_FIRE_SENTIMENT_WEIGHT,
)

logger = logging.getLogger(__name__)

EXIT_FIRED = 'fired'
EXIT_LEFT = 'left'


def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


def teamWinPct(team) -> float:
    """Completed-season win rate, or 0.5 when there's no record to judge (a
    brand-new team shouldn't read as a disaster)."""
    stats = getattr(team, 'seasonTeamStats', None) or {}
    wins = float(stats.get('wins', 0) or 0)
    losses = float(stats.get('losses', 0) or 0)
    played = wins + losses
    if played <= 0:
        return 0.5
    return wins / played


class GmTurnover:
    """Decides which GMs leave their post this offseason, and why."""

    def __init__(self, rng=None):
        self.rng = rng or Random()

    # --------------------------------------------------------------- fire

    def fireChance(self, team, coach, sentiment: float = 0.0) -> float:
        """Probability this GM is fired for performance.

        Pressure comes from how far the team fell BELOW a baseline win rate —
        at or above it there is no pressure at all, so a competent GM is never
        rolled on. Two things buy rope:

        - **Tenure grace**: a GM in their first season(s) isn't fired for one
          bad year, since they inherited the roster and haven't had an offseason
          to shape it.
        - **Goodwill**: a coach with a strong locker-room presence (`attitude`)
          survives a bad season that would sink a disliked one. This is the
          "threshold varies by GM" from the plan, sourced from an attribute
          rather than a hidden per-coach roll, so it's legible.

        `sentiment` (negative = hostile fanbase) adds pressure once Part D exists.
        """
        seasons = int(getattr(coach, 'seasonsCoached', 0) or 0)
        if seasons <= GM_FIRE_GRACE_SEASONS:
            return 0.0

        deficit = max(0.0, GM_FIRE_BASELINE_WINPCT - teamWinPct(team))
        if deficit <= 0 and sentiment >= 0:
            return 0.0

        chance = deficit * GM_FIRE_SENSITIVITY

        # Hostile fans push for a firing; supportive fans protect. No-op at 0.
        chance += max(0.0, -sentiment) * GM_FIRE_SENTIMENT_WEIGHT

        # Goodwill: attitude 60 -> no protection, 100 -> full GM_FIRE_GOODWILL_MAX.
        attitude = float(getattr(coach, 'attitude', 80) or 80)
        goodwill = _clamp((attitude - 60.0) / 40.0, 0.0, 1.0) * GM_FIRE_GOODWILL_MAX
        chance -= goodwill

        return _clamp(chance, 0.0, GM_FIRE_MAX_CHANCE)

    # -------------------------------------------------------------- leave

    def leaveChance(self, team, coach, sentiment: float = 0.0) -> float:
        """Probability this GM walks away voluntarily.

        Deliberately INDEPENDENT of record: the plan wants a hostile fanbase
        able to drive out a GM who is winning, so fans can push someone out by
        poisoning the well as well as by demanding a firing. With sentiment
        unbuilt this is just a small base rate — the occasional GM who steps
        away — which is the intended floor anyway.
        """
        chance = GM_LEAVE_BASE_CHANCE
        chance += max(0.0, -sentiment) * GM_LEAVE_SENTIMENT_WEIGHT
        return _clamp(chance, 0.0, 1.0)

    # ------------------------------------------------------------ resolve

    def evaluateExit(self, team, coach, sentiment: float = 0.0):
        """Roll this GM's non-retirement exits.

        Returns EXIT_FIRED, EXIT_LEFT, or None. Retirement is handled by the
        caller BEFORE this (it's the existing tenure curve and takes precedence
        — a retiring GM isn't also fired).

        Fire is rolled before leave: if a GM was going to be fired anyway,
        that's the story, and rolling both would double the exit rate.
        """
        if not GM_TURNOVER_ENABLED or coach is None:
            return None

        fire = self.fireChance(team, coach, sentiment)
        if fire > 0 and self.rng.random() < fire:
            return EXIT_FIRED

        leave = self.leaveChance(team, coach, sentiment)
        if leave > 0 and self.rng.random() < leave:
            return EXIT_LEFT

        return None

    def describeExit(self, exitKind: str, coach, team) -> str:
        """Human-readable line for the league news / logs."""
        name = getattr(coach, 'name', 'The GM')
        teamName = getattr(team, 'name', 'the team')
        seasons = int(getattr(coach, 'seasonsCoached', 0) or 0)
        if exitKind == EXIT_FIRED:
            return (f"{teamName} fire {name} after {seasons} season"
                    f"{'s' if seasons != 1 else ''}")
        if exitKind == EXIT_LEFT:
            return (f"{name} steps down as {teamName} GM after {seasons} season"
                    f"{'s' if seasons != 1 else ''}")
        return f"{name} leaves {teamName}"
