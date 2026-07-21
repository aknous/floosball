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


def _cleanNum(v):
    """Round a possibly-fractional score for UI display, dropping float-accumulation
    noise (3.0000000000000018 -> 3) and a trailing .0 on whole numbers. Mirrors
    api_response_builders.cleanScore but kept local to avoid an api-layer import."""
    try:
        n = round(float(v or 0), 1)
    except (TypeError, ValueError):
        return v
    return int(n) if n == int(n) else n


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
        back at the offense's own 20 (the possession gate), so a punt only wastes a down.
        innings returns it always (a punt is an out for nothing)."""
        return False

    def isLastScoringChance(self, game, offense) -> bool:
        """True when `offense` has NO future possession to make up points after this one,
        so a FG that still leaves them trailing is futile and the 4th-down caller should
        push for the touchdown. Default False — clock formats detect the endgame via the
        game clock / chess-clock lockout instead; innings (no clock) needs this signal."""
        return False

    def newDriveYardsToEndzone(self, game):
        """A fixed yards-to-endzone for EVERY new possession, or None to use the natural
        spot. innings starts every drive at the batting team's own 20 (a fresh at-bat)."""
        return None

    def openingOffense(self, game):
        """The team that gets the opening possession, or None to keep the coin toss.
        innings forces the AWAY team to bat first (top) so HOME bats last and can
        walk it off."""
        return None

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

    # ── Result / winner (the ONLY seam where a format decouples the winner from
    #    total points — frames uses this; every other format keeps most-points-wins) ──
    def winnerSide(self, game) -> str:
        """Who won: 'home', 'away', or 'tie'. Default = most cumulative points."""
        if game.homeScore > game.awayScore:
            return 'home'
        if game.awayScore > game.homeScore:
            return 'away'
        return 'tie'

    def resultDisplay(self, game):
        """The (home, away) values shown AS the final result / score string. Default =
        the point totals; frames shows frames-won."""
        return game.homeScore, game.awayScore

    def eloScores(self, game):
        """The (home, away) values ELO uses for its margin-of-victory. Default = the
        point totals; frames uses frames-won so the margin reflects the match result."""
        return game.homeScore, game.awayScore

    # ── Scoring interception (bust) ────────────────────────────────────────────
    def scorePoints(self, game, points):
        """Transform the points a scoring play awards before they're applied. Default =
        unchanged. bust ROUNDS to a whole number so a fractional score value can't make
        landing exactly on X impossible."""
        return points

    def voidsScore(self, game, team, points) -> bool:
        """True → VOID this score (don't apply the points; the scoring play becomes a
        no-score / turnover). Default never voids. bust voids a score that would push the
        team OVER the target X (you can't exceed X)."""
        return False

    def allowFieldGoal(self, game, fgPoints) -> bool:
        """Whether the offense may attempt a field goal right now. Default yes. bust
        forbids a FG that would OVERSHOOT X (a busted kick just wastes the down); a FG
        that lands on or under X is fine (exactly on X wins)."""
        return True

    def usesQuarterCoachAdjustments(self) -> bool:
        """Whether the adaptive mid-game coach re-plan fires at QUARTER boundaries.
        True for clock/quarter formats. frames returns False — its adjustment beat is
        at FRAME boundaries (which don't line up with quarters), so quarter re-plans
        would just double it up."""
        return True

    def usesQuarterBreaks(self) -> bool:
        """Whether the format has QUARTER structure at all — quarter-start callouts
        ('Start Nth Quarter') and the two-minute warning. True for clock/quarter
        formats. frames returns False (its periods are frames, not quarters), so those
        quarter-flavored beats are suppressed there."""
        return True

    def awardFrames(self, game) -> None:
        """Commit any period boundaries the clock has crossed. No-op for every format
        except frames (see FramesFormat), where it's called from a settled between-plays
        checkpoint so an end-of-frame play's score lands in its own frame."""
        return None

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
        # Advance the game clock from budget spent this period, so a period ends when
        # its share (totalBudget/4) of offense time is used.
        game._chessQuarterSpent = getattr(game, '_chessQuarterSpent', 0) + counted
        quarterBudget = self._totalBudget(game) / 4.0
        if game.currentQuarter >= 5:
            # OT: budgets are already spent — scale the OT clock to its display length.
            frac = min(1.0, game._chessQuarterSpent / quarterBudget) if quarterBudget else 1.0
            game.gameClockSeconds = max(0, round(game.gameRules.overtimeLengthSeconds * (1.0 - frac)))
        else:
            # Regulation: the game clock counts DOWN 1:1 with possession time spent — a
            # play that costs 20s of the offense's budget takes the same 20s off the game
            # clock, so the two clocks deplete together during a drive. Each quarter is
            # therefore totalBudget/4 of REAL offense time (no 15:00-scaled display).
            game.gameClockSeconds = max(0, round(quarterBudget - game._chessQuarterSpent))
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


class InningsFormat(GameFormat):
    """Baseball-style, try-driven — no game clock. Each team BATS until `triesPerInning`
    (3) TRIES, then teams switch; play `inningsPerGame` (3) innings, most points wins.
    A TRY = any possession that ENDS (a score, a punt, or a turnover), so an at-bat is
    up to 3 drives — the batting team keeps getting the ball at its own 20 until it uses
    3 tries, banking whatever it scores, then hands over. The AWAY team bats first (top);
    the HOME team bats last (bottom) and can WALK IT OFF: once it's the bottom of the
    final (or an extra) inning and HOME is ahead, HOME has won and doesn't need to bat.
    Extra innings on a tie. The engine's clock/quarter loop is left INERT (the clock
    never drains); the game is driven by the try/inning counters via the possession gate."""
    key = 'innings'
    label = 'Innings'
    EXTRA_INNINGS_CAP = 5   # accept a tie after this many extra innings (anti-stalemate)

    def _innings(self, game) -> int:
        return max(1, int(getattr(game.gameRules, 'inningsPerGame', 3)))

    def _tries(self, game) -> int:
        return max(1, int(getattr(game.gameRules, 'triesPerInning', 3)))

    def consumesRealTime(self) -> bool:
        return False

    def consumeTime(self, game, seconds: int) -> None:
        return None   # no game clock — the loop is try-driven

    def latchFinalMidPlay(self) -> bool:
        return False   # ends on score+inning conditions a defensive score can flip

    def suppressPunt(self, game) -> bool:
        return True    # a punt is a try for nothing; going for it is strictly better

    def isLastScoringChance(self, game, offense) -> bool:
        # The batting team is on its LAST try of its FINAL at-bat — no possession to come.
        # A FG that doesn't tie/take the lead here is futile, so the 4th-down caller should
        # go for the TD. The current inning/half already implies which team bats (top = away,
        # bottom = home), and offense IS that team, so the inning/try state is sufficient.
        # Covers regulation AND extra innings (inning >= N), and both halves. Non-last tries
        # / earlier innings return False so a team with a future at-bat can still kick.
        lastTry = getattr(game, '_inningsTries', 0) >= self._tries(game) - 1
        lastInning = getattr(game, '_inningsNumber', 1) >= self._innings(game)
        return lastTry and lastInning

    def newDriveYardsToEndzone(self, game):
        return game.gameRules.fieldLength - 20   # every at-bat starts at own 20

    def openingOffense(self, game):
        return game.awayTeam   # away bats first (top) → home bats last (bottom)

    def onPeriodStart(self, game) -> None:
        if game.currentQuarter == 1:
            game._inningsNumber = 1
            game._inningsHalf = 'top'
            game._inningsTries = 0
            game._inningsContinue = False
            game._inningsContinues = 0

    def possessionReceiver(self, game, giver, receiver):
        # One-shot: set when this resolution inserts an inning-style feed marker (a batting
        # change or an extended try), so the post-score "next try" marker knows to stay
        # quiet. A flag, not a peek at the feed head — an interleaved entry (a rally line,
        # say) used to hide the marker and let a duplicate through.
        game._inningsMarked = False
        # Conversion-gated continuation (docs/INNINGS_REDESIGN_PLAN.md): a TD whose TOP
        # conversion was MADE keeps the batting team's at-bat alive WITHOUT consuming a try
        # (baseball-style — scoring doesn't make an out). `_inningsContinue` is set by the
        # conversion resolver; a per-at-bat safety cap stops a freak no-miss streak hanging
        # the game. Everything else (kick / lesser rung / miss / failed drive) consumes a try.
        if getattr(game, '_inningsContinue', False):
            game._inningsContinue = False
            from constants import INNINGS_MAX_CONTINUATIONS
            cont = getattr(game, '_inningsContinues', 0)
            if cont < INNINGS_MAX_CONTINUATIONS:
                game._inningsContinues = cont + 1
                # Mark the extended at-bat in the play feed, styled like the inning marker
                # (batting team made its top conversion and keeps batting — no try spent).
                try:
                    game.gameFeed.insert(0, {'event': {
                        'text': f"{giver.abbr} · Try extended!",
                        '_type': 'inning',
                        'quarter': getattr(game, 'currentQuarter', 1),
                        'timeRemaining': '',
                    }})
                    game._inningsMarked = True
                except Exception:
                    pass
                return giver   # keep batting — same at-bat, try NOT consumed
            # cap reached → fall through and consume a try like any other outcome
        game._inningsContinue = False   # clear any stale flag before a normal resolution
        # Every OTHER possession-end is a TRY used by the batting team (the giver). Under 3
        # tries they keep batting; at 3 the at-bat flips to the other team.
        tries = getattr(game, '_inningsTries', 0) + 1
        if tries < self._tries(game):
            game._inningsTries = tries
            return giver
        game._inningsTries = 0
        game._inningsContinues = 0   # at-bat over → reset the continuation counter
        if getattr(game, '_inningsHalf', 'top') == 'top':
            game._inningsHalf = 'bottom'
        else:
            game._inningsHalf = 'top'
            game._inningsNumber = getattr(game, '_inningsNumber', 1) + 1
        # Mark the batting change in the play feed (like a new quarter) — unless this flip
        # just ended the final inning (the game is about to end, no new at-bat).
        _endFlip = (game._inningsHalf == 'top' and game._inningsNumber > self._innings(game))
        if not _endFlip:
            try:
                _bat = game.homeTeam if game._inningsHalf == 'bottom' else game.awayTeam
                _lbl = ('Bottom' if game._inningsHalf == 'bottom' else 'Top') + f" {game._inningsNumber}"
                game.gameFeed.insert(0, {'event': {
                    'text': f"{_lbl} · {_bat.abbr} up",
                    '_type': 'inning',
                    'quarter': game.currentQuarter,
                    'timeRemaining': '',
                }})
                game._inningsMarked = True
            except Exception:
                pass
        # The at-bat is over and the teams switch — give the coaches a moment to
        # regroup, like a manager between innings. innings leaves the clock inert (no
        # advanceQuarter), so this is its ONLY mid-game coach-adjustment beat. Skip the
        # flip that just completed the final inning (the game is about to end).
        gameEnding = (game._inningsHalf == 'top'
                      and game._inningsNumber > self._innings(game))
        if not gameEnding:
            try:
                game._maybeReadjustGameplans('inning')
            except Exception:
                pass
        return receiver

    def checkEarlyEnd(self, game):
        N = self._innings(game)
        inning = getattr(game, '_inningsNumber', 1)
        half = getattr(game, '_inningsHalf', 'top')
        # WALK-OFF: HOME bats last (bottom). Once it's the bottom of the final (or an
        # extra) inning and HOME is ahead, HOME has won — it needn't bat / keep batting.
        if half == 'bottom' and inning >= N and game.homeScore > game.awayScore:
            return True
        # A full inning just completed (back at the TOP with 0 tries, past N innings):
        # decided ends it; a tie goes to extra innings (until the anti-stalemate cap).
        if half == 'top' and getattr(game, '_inningsTries', 0) == 0 and inning > N:
            if game.homeScore != game.awayScore:
                return True
            if inning > N + self.EXTRA_INNINGS_CAP:
                return True   # accept a tie after too many extra innings
        return None

    def displayInning(self, game) -> int:
        """The inning number to SHOW. The flip that ends the final inning increments the
        counter to N+1 before the game-over check reads it (that increment is what tells
        `checkEarlyEnd` an inning completed), so a game decided in regulation would
        otherwise finish reading "inning 4". Clamp only while parked on that boundary
        state with the game actually over — extra innings really are inning N+1, and a
        game still sitting there undecided is tied and heading to extras."""
        N = self._innings(game)
        inning = getattr(game, '_inningsNumber', 1)
        if (inning > N and getattr(game, '_inningsHalf', 'top') == 'top'
                and getattr(game, '_inningsTries', 0) == 0
                and self.checkEarlyEnd(game)):
            return inning - 1
        return inning

    def adjustGameProgress(self, game, gameProgress: float) -> float:
        # Progress = fraction of the scheduled innings played (completed innings +
        # current half + tries within it), so WP reads late innings as "late game".
        total = self._innings(game)
        inning = getattr(game, '_inningsNumber', 1)
        halfFrac = 0.5 if getattr(game, '_inningsHalf', 'top') == 'bottom' else 0.0
        tryFrac = (getattr(game, '_inningsTries', 0) / self._tries(game)) * 0.5
        done = (inning - 1) + halfFrac + tryFrac
        return max(gameProgress, min(1.0, done / total))

    def stateExtra(self, game) -> dict:
        ls = getattr(game, '_inningsLineScore', None) or {'home': {}, 'away': {}}
        inning = self.displayInning(game)
        # Always show the full scheduled slate of innings (1..inningsPerGame), plus any
        # extra innings reached — future innings render blank on the frontend.
        maxInn = max([inning, self._innings(game)] + list(ls['home'].keys()) + list(ls['away'].keys()))
        innNums = list(range(1, int(maxInn) + 1))
        return {'innings': {
            'active': True,
            'inning': inning,
            'half': getattr(game, '_inningsHalf', 'top'),
            'tries': getattr(game, '_inningsTries', 0),
            'inningsPerGame': self._innings(game),
            'triesPerInning': self._tries(game),
            'lineScore': {
                'innings': innNums,
                'home': [ls['home'].get(i, 0) for i in innNums],
                'away': [ls['away'].get(i, 0) for i in innNums],
            },
        }}


class FramesFormat(GameFormat):
    """Match play (golf/snooker frames). The game is split into `framesPerGame` equal
    time frames; whoever OUTSCORES the other WITHIN a frame wins it (+1), a tied frame
    is HALVED (1/2 each). Most frames won wins the match — total points are irrelevant
    to the result (a lopsided frame is worth the same +1 as a squeaker). Frames tied at
    the end → total-points tiebreak; still tied → OT. The clock/quarter/OT loop runs
    NORMALLY; frames are a time-based OVERLAY, and only the WINNER is decided differently.
    """
    key = 'frames'
    label = 'Frames'

    def _frames(self, game) -> int:
        return max(1, int(getattr(game.gameRules, 'framesPerGame', 6)))

    def _regSeconds(self, game) -> int:
        return int(game.gameRules.quartersPerGame * game.gameRules.quarterLengthSeconds)

    def usesQuarterCoachAdjustments(self) -> bool:
        return False   # frames adjust between FRAMES, not quarters

    def usesQuarterBreaks(self) -> bool:
        return False   # frames have no quarters — no quarter callouts or 2-min warning

    def _elapsed(self, game) -> int:
        # Regulation seconds elapsed (capped at the full game; OT is past all frames).
        total = self._regSeconds(game)
        if game.currentQuarter >= 5:
            return total
        q = game.gameRules.quarterLengthSeconds
        return min(total, (game.currentQuarter - 1) * q + (q - game.gameClockSeconds))

    def latchFinalMidPlay(self) -> bool:
        return False   # the final frame's winner can shift on the last play's score

    def consumeTime(self, game, seconds: int) -> None:
        super().consumeTime(game, seconds)   # normal game-clock drain ONLY.
        # Frame AWARDS are NOT done here anymore. This drain runs mid-play, BEFORE
        # _addScore applies a scoring play's points, so awarding here read a pre-score
        # board and leaked an end-of-frame play's points into the next frame. The game
        # loop calls awardFrames() at a settled between-plays checkpoint instead.

    def awardFrames(self, game) -> None:
        """Commit every frame whose time boundary the clock has now crossed, reading a
        SETTLED score (called between plays, after _addScore applies the last play's
        points). Idempotent — keyed on _frameIndex vs elapsed, so repeat calls are
        no-ops. The final frame commits when the clock reaches 0 at end of regulation."""
        N = self._frames(game)
        frameLen = self._regSeconds(game) / N
        target = min(N, int(self._elapsed(game) / frameLen)) if frameLen else N
        awarded = False
        while getattr(game, '_frameIndex', 0) < target:
            h = game.homeScore - getattr(game, '_frameStartHome', 0)
            a = game.awayScore - getattr(game, '_frameStartAway', 0)
            if h > a:
                game._framesWonHome = getattr(game, '_framesWonHome', 0.0) + 1
                winner = 'home'
            elif a > h:
                game._framesWonAway = getattr(game, '_framesWonAway', 0.0) + 1
                winner = 'away'
            else:
                game._framesWonHome = getattr(game, '_framesWonHome', 0.0) + 0.5
                game._framesWonAway = getattr(game, '_framesWonAway', 0.0) + 0.5
                winner = 'tie'
            # Record the completed frame's points + winner for the box-score line.
            if not hasattr(game, '_frameResults'):
                game._frameResults = []
            game._frameResults.append({'home': h, 'away': a, 'winner': winner})
            game._frameStartHome = game.homeScore
            game._frameStartAway = game.awayScore
            game._frameIndex = getattr(game, '_frameIndex', 0) + 1
            awarded = True
        # A frame just ended (and it's not the game-ending final frame) — give the
        # coaches a moment to regroup between frames, like a break in match play, and flag
        # the boundary so the game loop resets possession (the frame is over, the next
        # frame kicks off to the alternating team). Reuses the adaptive, adaptability-gated
        # mid-game re-plan (frame boundaries don't line up with quarters).
        if awarded and getattr(game, '_frameIndex', 0) < N:
            game._frameBoundaryPending = True
            try:
                game._maybeReadjustGameplans('frame')
            except Exception:
                pass

    def onPeriodStart(self, game) -> None:
        if game.currentQuarter == 1:
            game._frameIndex = 0
            game._frameStartHome = 0
            game._frameStartAway = 0
            game._framesWonHome = 0.0
            game._framesWonAway = 0.0

    def checkEarlyEnd(self, game):
        # Match clinched (like a golf match "3 & 2"): if the trailing team can't win enough
        # of the frames still to be decided to even TIE the frames, the match is over. A
        # tie is still winnable (it defers to the points tiebreak), so only end when the
        # trailer literally can't reach the leader's frames-won even by sweeping the rest.
        N = self._frames(game)
        fh = getattr(game, '_framesWonHome', 0.0)
        fa = getattr(game, '_framesWonAway', 0.0)
        remaining = N - int(getattr(game, '_frameIndex', 0))   # frames not yet decided (incl. current)
        if remaining >= 0 and (fa + remaining < fh or fh + remaining < fa):
            return True
        # End of regulation: the match is decided by frames won; a frames tie falls to
        # the total-points tiebreak; if BOTH are tied, defer (None) so it goes to OT.
        if game.currentQuarter == 4 and game.gameClockSeconds <= 0:
            fh = getattr(game, '_framesWonHome', 0.0)
            fa = getattr(game, '_framesWonAway', 0.0)
            if fh != fa:
                return True
            if game.homeScore != game.awayScore:
                return True
            return None   # frames AND points tied -> OT
        return None

    def winnerSide(self, game) -> str:
        fh = getattr(game, '_framesWonHome', 0.0)
        fa = getattr(game, '_framesWonAway', 0.0)
        if fh > fa:
            return 'home'
        if fa > fh:
            return 'away'
        # frames tied -> total-points tiebreak
        if game.homeScore > game.awayScore:
            return 'home'
        if game.awayScore > game.homeScore:
            return 'away'
        return 'tie'

    def resultDisplay(self, game):
        return (getattr(game, '_framesWonHome', 0.0), getattr(game, '_framesWonAway', 0.0))

    def eloScores(self, game):
        return (getattr(game, '_framesWonHome', 0.0), getattr(game, '_framesWonAway', 0.0))

    def adjustWinProbability(self, game, homeWp, awayWp, expectedPoints):
        # Frames-based WP: the point-logistic WP is meaningless here (points don't win
        # the match). Home's edge = frames-won lead + the current frame's lean, damped
        # by how many frames remain. Keep a light touch of the ELO/point prior early.
        import math
        N = self._frames(game)
        fh = getattr(game, '_framesWonHome', 0.0)
        fa = getattr(game, '_framesWonAway', 0.0)
        curH = game.homeScore - getattr(game, '_frameStartHome', 0)
        curA = game.awayScore - getattr(game, '_frameStartAway', 0)
        curLean = 0.5 if curH > curA else -0.5 if curA > curH else 0.0
        remaining = max(1, N - getattr(game, '_frameIndex', 0))
        lead = (fh - fa) + curLean
        z = lead / (0.7 * math.sqrt(remaining))
        framesWp = 100.0 / (1.0 + math.exp(-z))
        # Blend: mostly frames, a little of the incoming (ELO+form) prior, fading as the
        # match progresses so late frames are almost purely frames-driven.
        priorWeight = 0.30 * (remaining / N)
        home = priorWeight * homeWp + (1 - priorWeight) * framesWp
        return home, 100.0 - home

    def stateExtra(self, game) -> dict:
        idx = getattr(game, '_frameIndex', 0)
        N = self._frames(game)
        # Time remaining in the current 10-min frame (the mini-game clock).
        frameLen = self._regSeconds(game) / N if N else 0
        frameRem = max(0, int(round(frameLen - (self._elapsed(game) % frameLen)))) if frameLen else 0
        # Frames-tie tiebreak: when the frames won are level, the match is decided by
        # TOTAL POINTS (winnerSide). Surface it so a 3-3 frames final doesn't look like a
        # silent tie — the UI can say "level on frames, decided by points". Live: shows the
        # current points edge; final: the deciding margin. None when frames aren't level or
        # points are also tied (→ OT).
        fh = getattr(game, '_framesWonHome', 0.0)
        fa = getattr(game, '_framesWonAway', 0.0)
        tiebreak = None
        if fh == fa and game.homeScore != game.awayScore:
            tiebreak = {
                'decidedByPoints': True,
                'homePoints': _cleanNum(game.homeScore),
                'awayPoints': _cleanNum(game.awayScore),
                'winner': 'home' if game.homeScore > game.awayScore else 'away',
            }
        return {'frames': {
            'tiebreak': tiebreak,
            'active': True,
            'framesPerGame': N,
            'currentFrame': min(N, idx + 1),
            'frameClock': game.formatTime(frameRem),
            'framesWonHome': _cleanNum(getattr(game, '_framesWonHome', 0.0)),
            'framesWonAway': _cleanNum(getattr(game, '_framesWonAway', 0.0)),
            'frameHome': _cleanNum(game.homeScore - getattr(game, '_frameStartHome', 0)),
            'frameAway': _cleanNum(game.awayScore - getattr(game, '_frameStartAway', 0)),
            # Per-frame line: completed frames (points + winner); the current frame's
            # in-progress points are frameHome/frameAway, future frames render blank.
            'frameResults': [{'home': _cleanNum(r.get('home')), 'away': _cleanNum(r.get('away')),
                              'winner': r.get('winner')} for r in getattr(game, '_frameResults', [])],
        }}


class BustFormat(GameFormat):
    """Darts — land EXACTLY on the target X to win. A score that would push you OVER X is
    VOIDED (no points) and turns the ball over, so a greedy TD that overshoots wastes the
    drive; you can never exceed X. Reaching exactly X wins; if the clock expires first the
    higher score (both <= X) wins. Score values are forced to WHOLE NUMBERS so landing on
    X is always possible, and Sideline Goals is bundled on so the 1-pt hoops let you land
    precisely. The clock/quarter loop runs normally — only scoring + the win condition
    change. The decision tree inverts: near X, don't kick a busting FG or chase a busting
    TD — dink the exact remainder with a FG / hoop."""
    key = 'bust'
    label = 'Darts'

    def _target(self, game) -> int:
        return int(getattr(game.gameRules, 'targetScore', 18))

    def scorePoints(self, game, points):
        return int(round(points))   # whole numbers only — a fractional score can't land on X

    def voidsScore(self, game, team, points) -> bool:
        cur = game.homeScore if team is game.homeTeam else game.awayScore
        return (cur + points) > self._target(game)

    def bustNeed(self, game, team) -> int:
        cur = game.homeScore if team is game.homeTeam else game.awayScore
        return self._target(game) - cur

    def allowFieldGoal(self, game, fgPoints) -> bool:
        off = getattr(game, 'offensiveTeam', None)
        if off is None:
            return True
        return self.bustNeed(game, off) >= int(round(fgPoints))

    def checkEarlyEnd(self, game):
        # Reached exactly X → win (the standard higher-score winner picks that team).
        X = self._target(game)
        if game.homeScore == X or game.awayScore == X:
            return True
        return None

    def adjustGameProgress(self, game, gameProgress: float) -> float:
        # Nearing X is "late game" (a lead near X reads decisive). Scores never exceed X.
        X = self._target(game)
        if X > 0:
            return max(gameProgress, min(1.0, max(game.homeScore, game.awayScore) / X))
        return gameProgress


_FORMATS = {f.key: f for f in (GameFormat(), TargetFormat(), PlayLimitFormat(),
                               ChessClockFormat(), InningsFormat(), FramesFormat(),
                               BustFormat())}


def getFormat(key: Optional[str]) -> GameFormat:
    """Resolve a `gameFormat` string to its (shared, stateless) strategy object.
    Unknown / None falls back to standard."""
    return _FORMATS.get(key or 'standard', _FORMATS['standard'])
