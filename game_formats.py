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
        """True: plays drain the game clock in seconds (standard). False: the engine
        neutralizes its per-play clock decrements and the format drives the clock in
        `onPlayTick` (play_limit's synthetic clock)."""
        return True

    def onPeriodStart(self, game) -> None:
        """Called when a new quarter/OT period begins (and at kickoff). No-op unless a
        format tracks per-period play budgets."""
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


_FORMATS = {f.key: f for f in (GameFormat(), TargetFormat(), PlayLimitFormat())}


def getFormat(key: Optional[str]) -> GameFormat:
    """Resolve a `gameFormat` string to its (shared, stateless) strategy object.
    Unknown / None falls back to standard."""
    return _FORMATS.get(key or 'standard', _FORMATS['standard'])
