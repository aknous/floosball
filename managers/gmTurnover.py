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

**Sentiment IS wired** — `teamManager.handleCoachRetirement` loads real fan
standing (`CoachSentimentRepository.getStandingMap`) and passes it in. It matters:
a maximally hostile fanbase adds 25 points of fire chance and takes the voluntary
walk-away rate from 3% to 38%, which is the designed path for fans driving out a
GM who is winning. Entry points still default to neutral so callers without a
session behave sanely.

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
    GM_FIRE_STALL_GRACE, GM_FIRE_DROUGHT_STEP, GM_FIRE_STAGNATION_STEP,
    GM_FIRE_MEDIOCRITY_BAND, GM_FIRE_MEDIOCRITY_GRACE, GM_FIRE_MEDIOCRITY_STEP,
    GM_FIRE_TENURE_MAX,
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

    # ------------------------------------------------------- tenure record

    def tenurePressure(self, history) -> float:
        """Fire pressure from a GM's RECORD AT THIS CLUB, not just last season.

        `history` is newest-first, one entry per completed season of this GM's tenure:
            {'winPct': float, 'madePlayoffs': bool, 'wonPlayoffRound': bool}

        ⚠️ WITHOUT THIS, PERSISTENT MEDIOCRITY WAS FREE. `fireChance`'s deficit term reads
        the latest season only and goes to zero at a 0.45 win rate, so a club going 13-15
        forever produced 0.0% risk every year without end — five such seasons left an 86%
        chance of the same GM still being in post, and being reliably slightly-below-average
        was the safest place in the league to stand.

        Two axes, deliberately separate because they answer different questions:

        **Stall** — how long since this GM's club won a playoff game. Walks back from the
        most recent season and stops at the first one they advanced in, because winning a
        round is the thing that says the project is going somewhere. Missing the postseason
        costs more per season than reaching it and losing immediately, which is how "no
        playoffs in years" and "one-and-done in years" stay distinguishable rather than
        collapsing into one number.

        **Treading water** — consecutive seasons whose RECORD sits around .500. Its band
        starts at the fire baseline, so a season already generating deficit pressure is
        never also counted here.

        Capped at `GM_FIRE_TENURE_MAX` so a long grey tenure is a reason to be at risk,
        never a substitute for a catastrophic season.
        """
        if not history:
            return 0.0

        stall = 0.0
        counted = 0
        for s in history:
            if s.get('wonPlayoffRound'):
                break  # they got somewhere; the clock restarts here
            counted += 1
            if counted <= GM_FIRE_STALL_GRACE:
                continue
            stall += (GM_FIRE_STAGNATION_STEP if s.get('madePlayoffs')
                      else GM_FIRE_DROUGHT_STEP)

        lo, hi = GM_FIRE_MEDIOCRITY_BAND
        tread = 0
        for s in history:
            # ⚠️ Winning a playoff round is not treading water, whatever the record says.
            # Without this a club that goes 15-13 and wins a round still accrues plateau
            # pressure, which reads as punishing the one thing the stall axis rewards.
            if s.get('wonPlayoffRound'):
                break
            pct = float(s.get('winPct', 0.0) or 0.0)
            if not (lo <= pct <= hi):
                break
            tread += 1
        treading = max(0, tread - GM_FIRE_MEDIOCRITY_GRACE) * GM_FIRE_MEDIOCRITY_STEP

        return _clamp(stall + treading, 0.0, GM_FIRE_TENURE_MAX)

    # --------------------------------------------------------------- fire

    def fireChance(self, team, coach, sentiment: float = 0.0, history=None) -> float:
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

        `sentiment` (negative = hostile fanbase) adds pressure. ⚠️ Its quorum floor is
        ONE rater, so at a club with 0-2 fans a single hostile rating is a full -1.0.
        """
        # ⚠️ GRACE IS TIME AT THIS CLUB, NOT CAREER LENGTH. This read `seasonsCoached`,
        # which follows a GM to a new job — so a veteran hired to fix a bad team had NO
        # protection in their first season there and could be fired at 54% for the roster
        # they had just walked into. That is precisely the case the grace exists to cover,
        # and its own reasoning ("they inherited the roster and haven't had an offseason to
        # shape it") is about the club. Falls back to the career count only for a coach
        # object predating `seasonsWithTeam`.
        clubSeasons = getattr(coach, 'seasonsWithTeam', None)
        if clubSeasons is None:
            clubSeasons = getattr(coach, 'seasonsCoached', 0)
        if int(clubSeasons or 0) <= GM_FIRE_GRACE_SEASONS:
            return 0.0

        # ⚠️ TENURE IS EVALUATED EVEN ON A FINE SEASON. The early return below used to fire
        # whenever the latest record cleared the baseline, which is exactly the hole that
        # made persistent mediocrity free — a 13-15 club never reached the rest of this
        # function. A GM who has not won a playoff game in years is under pressure whatever
        # they just went.
        tenure = self.tenurePressure(history or [])

        deficit = max(0.0, GM_FIRE_BASELINE_WINPCT - teamWinPct(team))
        if deficit <= 0 and sentiment >= 0 and tenure <= 0:
            return 0.0

        chance = deficit * GM_FIRE_SENSITIVITY + tenure

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
        poisoning the well as well as by demanding a firing. With neutral fans this is
        just a small base rate — the occasional GM who steps away.
        """
        chance = GM_LEAVE_BASE_CHANCE
        chance += max(0.0, -sentiment) * GM_LEAVE_SENTIMENT_WEIGHT
        return _clamp(chance, 0.0, 1.0)

    # ------------------------------------------------------------ resolve

    def evaluateExit(self, team, coach, sentiment: float = 0.0, history=None):
        """Roll this GM's non-retirement exits.

        Returns EXIT_FIRED, EXIT_LEFT, or None. Retirement is handled by the
        caller BEFORE this (it's the existing tenure curve and takes precedence
        — a retiring GM isn't also fired).

        Fire is rolled before leave: if a GM was going to be fired anyway,
        that's the story, and rolling both would double the exit rate.
        """
        if not GM_TURNOVER_ENABLED or coach is None:
            return None

        fire = self.fireChance(team, coach, sentiment, history=history)
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
