"""Game-format strategy layer (docs/GAME_FORMATS_PLAN.md).

One `Game` engine runs every format; the format-SPECIFIC logic (when the game
ends, how "far along" it is for win-probability, the win-condition possession
pull, per-format clock/tempo semantics, and any decision biases) lives here in a
pluggable policy object instead of scattered `if gameFormat == ...` branches.

The engine holds a `Game.format` (resolved from `gameRules.gameFormat`) and
delegates to it at a handful of seams:

  - `checkEarlyEnd(game)`      -> Optional[bool]  end BEFORE the standard clock/OT
                                                  logic (None = defer to standard)
  - `adjustGameProgress(g, p)` -> float           WP "how far along" (0..1)
  - `adjustWinProbability(...)`-> (homeWp, awayWp) win-condition possession pull
  - `consumesRealTime()`       -> bool            False = the engine's per-play
                                                  clock decrements are neutralized
  - `onPlayTick(game)`         -> None            once per play (after totalPlays++)
  - `matchPoint(game)`/`shouldPush(game)`         tempo/decision biases
  - `stateExtra(game)`         -> dict            extra game_state fields (UI)

Every base method is the STANDARD behavior, so a format only overrides what it
changes and `standard` is a pure pass-through — OFF stays byte-identical.
"""
from typing import Optional, Tuple


class GameFormat:
    """Standard football: cumulative score, higher wins at the end of regulation/OT.
    Every hook here is the identity/no-op the engine assumes by default."""
    key = 'standard'
    label = 'Standard'

    # ── End condition ─────────────────────────────────────────────────────────
    def checkEarlyEnd(self, game) -> Optional[bool]:
        """Return True/False to decide the game BEFORE the engine's standard
        clock/OT logic, or None to defer to it (the default)."""
        return None

    def latchFinalMidPlay(self) -> bool:
        """Whether the engine may mark the game Final MID-PLAY (during a broadcast).
        True for clock-based formats (they only end when the clock hits 0, a stable
        moment). chess_clock ends on volatile score+budget conditions that a defensive
        score can flip within the same play, so it defers to the main loop's
        stable-state check instead of latching on a transient score."""
        return True

    # ── Win probability ───────────────────────────────────────────────────────
    def adjustGameProgress(self, game, gameProgress: float) -> float:
        """Map elapsed-fraction (0 kickoff → 1 end of regulation). Formats where the
        score itself advances the game (target) push this higher as X nears."""
        return gameProgress

    def adjustWinProbability(self, game, homeWp: float, awayWp: float,
                             expectedPoints: float) -> Tuple[float, float]:
        """Apply a win-condition possession pull (e.g. target match point). Default
        leaves the engine's computed WP untouched."""
        return homeWp, awayWp

    # ── Clock / tempo semantics ───────────────────────────────────────────────
    def consumesRealTime(self) -> bool:
        """True: the game clock (and the seconds-unit Drive Clock) drain in real
        seconds (standard). False: the format drives the game clock itself (play_limit
        from a play counter, chess_clock from a budget), so the seconds-unit Drive
        Clock is moot under it (it would use the plays unit)."""
        return True

    def consumeTime(self, game, seconds: int) -> None:
        """Consume `seconds` of game time. Standard drains the game clock; play_limit
        no-ops (its clock is play-count driven); chess_clock drains the possessing
        team's budget and recomputes its synthetic clock."""
        if seconds > 0:
            game.gameClockSeconds = max(0, game.gameClockSeconds - seconds)

    def possessionReceiver(self, game, giver, receiver):
        """Which team gets the ball on a possession change. Default: the defense
        (`receiver`). chess_clock keeps it with the `giver` when the `receiver` is
        locked out (offense budget spent)."""
        return receiver

    def suppressPunt(self, game) -> bool:
        """True → the offense should go for it on 4th down instead of punting. chess_clock
        returns this when the DEFENSE is locked out: a failed 4th down just hands the ball
        back at the offense's own 20 (the possession gate), so a punt only wastes a down."""
        return False

    def onPeriodStart(self, game) -> None:
        """Called when a new quarter/OT period begins (and at kickoff). No-op unless a
        format tracks per-period state (play budgets, chess-clock synthetic clock)."""
        return None

    def onPlayTick(self, game) -> None:
        """Called once per SCRIMMAGE play, right after it's counted. No-op for
        clock-driven formats."""
        return None

    # ── Decision biases ───────────────────────────────────────────────────────
    def matchPoint(self, game) -> bool:
        """The team on offense can END the game in its favor on THIS possession."""
        return False

    def shouldPush(self, game) -> bool:
        """The offense should PUSH to end the game now (hurry-up / aggressive) rather
        than sit on a lead. Standard football has no such win-by-scoring race."""
        return False

    # ── Display ───────────────────────────────────────────────────────────────
    def stateExtra(self, game) -> dict:
        """Extra fields merged into the game_state broadcast (format-specific UI)."""
        return {}


class TargetFormat(GameFormat):
    """First to X points wins — a walk-off the instant a team reaches the target, any
    quarter. If nobody reaches X the clock still bounds it and the higher score wins."""
    key = 'target'
    label = 'Target'

    def _target(self, game) -> int:
        return getattr(game.gameRules, 'targetScore', 30)

    def checkEarlyEnd(self, game) -> Optional[bool]:
        tgt = self._target(game)
        if game.homeScore >= tgt or game.awayScore >= tgt:
            return True
        return None

    def adjustGameProgress(self, game, gameProgress: float) -> float:
        # A near-target lead is "late game" even with clock left: a 24-0 lead in a
        # first-to-30 game reads ~0.80 done. Inert at 0-0.
        tgt = float(self._target(game))
        if tgt > 0:
            return max(gameProgress,
                       min(1.0, max(game.homeScore, game.awayScore) / tgt))
        return gameProgress

    def adjustWinProbability(self, game, homeWp, awayWp, expectedPoints):
        # Match point: a team on offense that can reach X THIS possession is pulled
        # toward winning like a late-game go-ahead drive, ramped by how reachable X is
        # (expected points vs points still needed). Regulation only; OT handled below.
        if game.currentQuarter >= 5 or game.offensiveTeam is None:
            return homeWp, awayWp
        off = game.offensiveTeam
        offScore = game.homeScore if off is game.homeTeam else game.awayScore
        need = self._target(game) - offScore
        if 0 < need <= game._maxPossession():
            reach = min(1.0, max(0.0, expectedPoints / max(1.0, float(need))))
            pull = 0.6 * reach
            targetWp = 99 if (off is game.homeTeam) else 1
            homeWp = homeWp + (targetWp - homeWp) * pull
            awayWp = 100 - homeWp
        return homeWp, awayWp

    def matchPoint(self, game) -> bool:
        off = game.offensiveTeam
        if off is None:
            return False
        offScore = game.homeScore if off is game.homeTeam else game.awayScore
        need = self._target(game) - offScore
        return 0 < need <= game._maxPossession()

    def shouldPush(self, game) -> bool:
        # Trailing / tied / one-score lead → always push to reach X. With a
        # comfortable lead only an aggressive coach goes for the outright win; a
        # conservative one burns the clock (falls through to normal burn logic).
        if not self.matchPoint(game):
            return False
        off = game.offensiveTeam
        offScore = game.homeScore if off is game.homeTeam else game.awayScore
        oppScore = game.awayScore if off is game.homeTeam else game.homeScore
        if (offScore - oppScore) <= game._oneScore():
            return True
        coach = getattr(off, 'coach', None)
        aggr = getattr(coach, 'aggressiveness', 80) if coach else 80
        return aggr >= 80

    def stateExtra(self, game) -> dict:
        tgt = self._target(game)
        return {'gameFormatInfo': {
            'format': 'target', 'targetScore': tgt,
            'homeToGo': max(0, tgt - game.homeScore),
            'awayToGo': max(0, tgt - game.awayScore),
        }}


class PlayLimitFormat(GameFormat):
    """No game clock: each quarter is a fixed number of PLAYS (`playsPerQuarter`).
    Implemented with a SYNTHETIC clock — the engine's clock machinery, WP, and the
    entire time-based decision tree are reused unchanged (kneel-to-end and late-game
    aggression translate because "plays remaining" is proportional to "seconds
    remaining"). Each play drains one slice so exactly `playsPerQuarter` plays end a
    quarter; the standard clock/OT end conditions then fire off the synthetic clock."""
    key = 'play_limit'
    label = 'Play Limit'

    def budget(self, game) -> int:
        return max(1, int(getattr(game.gameRules, 'playsPerQuarter', 30)))

    def _periodSeconds(self, game) -> int:
        return (game.gameRules.overtimeLengthSeconds if game.currentQuarter >= 5
                else game.gameRules.quarterLengthSeconds)

    def consumesRealTime(self) -> bool:
        return False

    def consumeTime(self, game, seconds: int) -> None:
        # No-op: the game clock is driven by the play counter in onPlayTick.
        return None

    def onPeriodStart(self, game) -> None:
        game._playLimitQuarterPlays = 0

    def onPlayTick(self, game) -> None:
        # Drive the synthetic clock from a format-owned per-period play counter (NOT
        # totalPlays, which also counts conversions), so exactly `budget` scrimmage
        # plays take the period clock from full to 0.
        game._playLimitQuarterPlays = getattr(game, '_playLimitQuarterPlays', 0) + 1
        budget = self.budget(game)
        frac = min(1.0, game._playLimitQuarterPlays / budget)
        game.gameClockSeconds = max(0, round(self._periodSeconds(game) * (1.0 - frac)))

    def stateExtra(self, game) -> dict:
        budget = self.budget(game)
        used = min(budget, max(0, getattr(game, '_playLimitQuarterPlays', 0)))
        return {'playLimit': {
            'active': True, 'playsPerQuarter': budget,
            'playsThisQuarter': used, 'playsRemaining': max(0, budget - used),
        }}


class ChessClockFormat(GameFormat):
    """Per-team offense-time budget. Each team drains its own budget only while it
    possesses the ball; when its budget hits 0 it's LOCKED OUT — it can't take the
    ball again, and the other team keeps it to the end. The game ends when both
    budgets are spent. Cumulative score, highest wins.

    Implemented with a SYNTHETIC clock (like play_limit): the game clock is scaled so
    4 quarters span the TOTAL budget (both teams), which keeps gameClockSeconds in the
    0..quarterLength range WP + halftime expect. The individual budgets are a parallel
    overlay that drives the possession gate. A leader that hogs the ball drains its own
    budget faster and hands the trailer uncontested late possessions — the strategic
    axis. Budgets are ignored in OT (a fresh sudden-death period on the synthetic clock)."""
    key = 'chess_clock'
    label = 'Chess Clock'

    def _budget(self, game) -> int:
        return max(1, int(getattr(game.gameRules, 'offenseClockBudgetSeconds', 1080)))

    def _totalBudget(self, game) -> int:
        return 2 * self._budget(game)

    # Budget accessors default to the full budget, so any call BEFORE the game loop
    # inits them (e.g. the season manager's pre-game WP) reads "not locked out".
    def _homeBudget(self, game):
        return getattr(game, '_chessHomeBudget', self._budget(game))

    def _awayBudget(self, game):
        return getattr(game, '_chessAwayBudget', self._budget(game))

    def consumesRealTime(self) -> bool:
        return False

    def latchFinalMidPlay(self) -> bool:
        return False

    def consumeTime(self, game, seconds: int) -> None:
        if seconds <= 0:
            return
        if game.currentQuarter >= 5:
            # OT: budgets are spent; advance the synthetic OT clock by full seconds.
            counted = seconds
        else:
            # Drain the possessing team's budget, FLOORED at 0. Only the portion within
            # their remaining budget advances the shared synthetic clock — a locked-out
            # team's overshoot plays are "free" so they can't end the game early and the
            # opponent still gets its full budget.
            if game.offensiveTeam is game.homeTeam:
                before = self._homeBudget(game)
                counted = min(seconds, max(0, before))
                game._chessHomeBudget = max(0, before - seconds)
            elif game.offensiveTeam is game.awayTeam:
                before = self._awayBudget(game)
                counted = min(seconds, max(0, before))
                game._chessAwayBudget = max(0, before - seconds)
            else:
                counted = seconds
        # Advance the synthetic game clock from TOTAL (capped) budget spent this period,
        # so a period ends when its share (totalBudget/4) of offense time is used.
        game._chessQuarterSpent = getattr(game, '_chessQuarterSpent', 0) + counted
        quarterBudget = self._totalBudget(game) / 4.0
        frac = min(1.0, game._chessQuarterSpent / quarterBudget) if quarterBudget else 1.0
        period = (game.gameRules.overtimeLengthSeconds if game.currentQuarter >= 5
                  else game.gameRules.quarterLengthSeconds)
        game.gameClockSeconds = max(0, round(period * (1.0 - frac)))
        # Both budgets spent in regulation → force the period to end so Q4 resolves
        # (the all-free plays would otherwise freeze the synthetic clock).
        if (game.currentQuarter < 5 and self._homeBudget(game) <= 0
                and self._awayBudget(game) <= 0):
            game.gameClockSeconds = 0

    def _lockedOut(self, game, team) -> bool:
        if team is game.homeTeam:
            return self._homeBudget(game) <= 0
        if team is game.awayTeam:
            return self._awayBudget(game) <= 0
        return False

    def suppressPunt(self, game) -> bool:
        # If the DEFENSE is locked out, a failed 4th down just returns the ball to the
        # offense at its own 20 (the gate), so punting only wastes a down — go for it.
        return game.currentQuarter < 5 and self._lockedOut(game, game.defensiveTeam)

    def possessionReceiver(self, game, giver, receiver):
        # A locked-out team can't take the ball back — the giver keeps it (fresh drive
        # at its own 20). Gate is off in OT. If both are spent the game is ending.
        if game.currentQuarter >= 5:
            return receiver
        if self._lockedOut(game, receiver) and not self._lockedOut(game, giver):
            return giver
        return receiver

    def checkEarlyEnd(self, game):
        # A locked-out team that is TRAILING can never catch up (no offense left) → the
        # game is decided the instant that's true, whether it locked out first (losing)
        # or fell behind after (the opponent scored past it). If both are spent and
        # someone leads, likewise over. A tie returns None so the standard Q4->OT path
        # runs. OT (>=5) defers to standard sudden-death.
        if game.currentQuarter >= 5:
            return None
        hLock = self._homeBudget(game) <= 0
        aLock = self._awayBudget(game) <= 0
        diff = game.homeScore - game.awayScore
        if hLock and diff < 0:            # home depleted and trailing
            return True
        if aLock and diff > 0:            # away depleted and trailing
            return True
        if hLock and aLock and diff != 0:  # both depleted, decided
            return True
        return None

    def onPeriodStart(self, game) -> None:
        game._chessQuarterSpent = 0
        if game.currentQuarter == 1:
            b = self._budget(game)
            game._chessHomeBudget = b
            game._chessAwayBudget = b

    def adjustWinProbability(self, game, homeWp, awayWp, expectedPoints):
        # A locked-out team can't score again. If it isn't leading, it's nearly done;
        # if it leads, the other team still has budget to try to catch up (leave WP).
        if game.currentQuarter >= 5:
            return homeWp, awayWp
        hLock = self._homeBudget(game) <= 0
        aLock = self._awayBudget(game) <= 0
        if hLock == aLock:
            return homeWp, awayWp
        diff = game.homeScore - game.awayScore
        if hLock and diff <= 0:        # home can't score & isn't ahead → away all but won
            homeWp = min(homeWp, 4.0)
            awayWp = 100 - homeWp
        elif aLock and diff >= 0:       # away can't score & isn't ahead → home all but won
            awayWp = min(awayWp, 4.0)
            homeWp = 100 - awayWp
        return homeWp, awayWp

    def stateExtra(self, game) -> dict:
        return {'chessClock': {
            'active': True,
            'homeBudget': max(0, round(getattr(game, '_chessHomeBudget', 0))),
            'awayBudget': max(0, round(getattr(game, '_chessAwayBudget', 0))),
            'homeLockedOut': getattr(game, '_chessHomeBudget', 1) <= 0,
            'awayLockedOut': getattr(game, '_chessAwayBudget', 1) <= 0,
        }}


_FORMATS = {f.key: f for f in
            (GameFormat(), TargetFormat(), PlayLimitFormat(), ChessClockFormat())}


def getFormat(key: Optional[str]) -> GameFormat:
    """Resolve a `gameFormat` string to its (shared, stateless) strategy object.
    Unknown / None falls back to standard."""
    return _FORMATS.get(key or 'standard', _FORMATS['standard'])
