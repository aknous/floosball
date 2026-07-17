"""Cores rule-change vote — trigger, ballot, resolution (docs/RULE_CHANGES_PLAN.md).

Encapsulates the domain logic so seasonManager only makes two thin hook calls:
  - maybeOpenWindow(): at the start of a game day (weeks 1/8/15/22) roll the
    escalating chance a vote fires; if it does, open a window (Aris CHANGE or Pyre
    REVERT), pick the Core's conversation lines, and announce it.
  - resolveOpenWindow(): 15 min before the day's first game, tally the vote, apply
    the most-voted rule (or none), and announce the outcome.

Most-voted wins, no quorum. Applied changes drift across seasons until reverted.
"""

import datetime
import os
import random
from typing import List, Optional

from logger_config import get_logger

logger = get_logger('floosball.rulevote')

# Weeks that begin a game day (day index = (week-1)//7).
GAME_DAY_START_WEEKS = (1, 8, 15, 22)

# Candidate fields left OUT of the per-game Criticality chaos LOOP. `scoringModel` is a
# display-only lens read league-wide from /api/rules — threading a per-game display
# model through the game payload isn't built, so chaos leaves it at the league value.
# `gameFormat` is NOT excluded from chaos anymore (all formats are built) — but it's
# handled FIRST (see randomChaosRules) rather than in the general loop, so it's listed
# here to skip it in the loop.
# Fields the chaos randomizer never touches: scoringModel (display-only), gameFormat
# (format-first step owns it), the two mechanic gates handled by the dedicated coin-flip
# (conversionLadder/sidelineGoals), and Contested Scoring (held out until vetted → stays
# at its base/off value).
_CHAOS_EXCLUDE = frozenset({'scoringModel', 'gameFormat',
                            'conversionLadderEnabled', 'sidelineGoalsEnabled',
                            'contestedScoringEnabled'})


class RuleVoteManager:
    def __init__(self, serviceContainer=None):
        self.serviceContainer = serviceContainer

    # ── helpers ──────────────────────────────────────────────────────────────
    def dayIndexForWeek(self, week: int) -> int:
        return (week - 1) // 7  # 0..3

    def _repo(self, session):
        from database.repositories.rule_vote_repository import RuleVoteRepository
        return RuleVoteRepository(session)

    def _respectsScoreOrder(self, field: str, value, gameRules) -> bool:
        """Enforce the invariant TOUCHDOWN > FIELD GOAL: a proposed field-goal value
        must stay strictly below the current touchdown value, and a proposed touchdown
        value strictly above the current field-goal value. (Reverts move toward the
        defaults 6/3, which already satisfy this given the candidate ranges.)"""
        if field == 'fieldGoalPoints':
            return value < float(getattr(gameRules, 'touchdownPoints', 6))
        if field == 'touchdownPoints':
            return value > float(getattr(gameRules, 'fieldGoalPoints', 3))
        return True

    def _formatDisplayName(self, fmtKey) -> str:
        """Clean display name for a game format (parenthetical config stripped). A format
        is never "Off" — the default is Standard."""
        import re
        from constants import GAME_FORMAT_PRESETS
        if not fmtKey or fmtKey == 'standard':
            return 'Standard'
        for p in GAME_FORMAT_PRESETS:
            if p['patch'].get('gameFormat') == fmtKey:
                return re.sub(r'\s*\(.*\)\s*', '', p['label']).strip()
        return str(fmtKey)

    def _pickProposedValue(self, field: str, current, gameRules):
        """Choose a specific CHANGE value for a field from its alternate space —
        always different from the current value AND the default (so a change moves a
        rule to a genuinely new value; returning to default is REVERT's job), and
        always keeping TD > FG. Returns None if no such value exists (e.g. a bool
        already flipped off, or no in-range value keeps TD above FG)."""
        import game_rules as gr
        from constants import RULE_VOTE_CANDIDATES
        spec = RULE_VOTE_CANDIDATES.get(field, {})
        default = gr.defaultRuleValue(field)
        if 'values' in spec:
            pool = [v for v in spec['values']
                    if v != current and v != default
                    and self._respectsScoreOrder(field, v, gameRules)]
            return random.choice(pool) if pool else None
        rng = spec.get('range')
        if not rng:
            return None
        lo, hi = rng
        isFloat = bool(spec.get('float'))
        for _ in range(30):
            if isFloat and random.random() < 0.5:
                v = round(random.uniform(lo, hi), 1)      # e.g. 6.4
            else:
                v = random.randint(int(lo), int(hi))       # e.g. 5
            if v != current and v != default and self._respectsScoreOrder(field, v, gameRules):
                return v
        return None

    def _presetFields(self, spec) -> List[str]:
        """The fields a PRESET candidate controls (union of its presets' patch keys —
        same keys across presets, so the first is enough)."""
        presets = spec.get('presets') or []
        return list(presets[0]['patch'].keys()) if presets else []

    def _isChangedCandidate(self, f, spec, gameRules) -> bool:
        """Whether a candidate is currently OFF its default. For a preset candidate
        that's whether its `gate` field is off-default; for a scalar, the field."""
        import game_rules as gr
        if 'presets' in spec:
            gate = spec.get('gate')
            return bool(gate and getattr(gameRules, gate, None) != gr.defaultRuleValue(gate))
        return getattr(gameRules, f, None) != gr.defaultRuleValue(f)

    def _changeOptions(self, gameRules) -> List[dict]:
        """Options available for a CHANGE vote, as generic {key, label, patch, field,
        value} dicts. A scalar candidate proposes one specific new value; a PRESET
        candidate (e.g. Drive Clock) proposes one random preset — offered only while
        the mechanic is currently off."""
        from constants import RULE_VOTE_CANDIDATES, SCORING_MODEL_FORMATS
        fmt = getattr(gameRules, 'gameFormat', 'standard') or 'standard'
        out = []
        for f, spec in RULE_VOTE_CANDIDATES.items():
            # Score-display alternates only make sense under cumulative-point formats;
            # withhold the candidate under target/bust/frames (only additive reads there).
            if f == 'scoringModel' and fmt not in SCORING_MODEL_FORMATS:
                continue
            if 'presets' in spec:
                if f == 'gameFormat':
                    # Offer EVERY format as its own option (a menu, not one random pick),
                    # excluding whichever format is currently active (swap-directly; a
                    # revert-to-standard is day 3's job).
                    curFmt = getattr(gameRules, 'gameFormat', 'standard') or 'standard'
                    for p in spec['presets']:
                        if p['patch'].get('gameFormat') == curFmt:
                            continue
                        out.append({"key": p['key'], "label": p['label'],
                                    "patch": dict(p['patch']), "field": None, "value": None})
                elif not self._isChangedCandidate(f, spec, gameRules):   # only when off
                    p = random.choice(spec['presets'])
                    out.append({"key": p['key'], "label": p['label'],
                                "patch": dict(p['patch']), "field": None, "value": None})
            else:
                v = self._pickProposedValue(f, getattr(gameRules, f, None), gameRules)
                if v is not None:
                    out.append({"key": f, "label": spec.get('label', f),
                                "patch": {f: v}, "field": f, "value": v})
        return out

    def _revertOptions(self, gameRules) -> List[dict]:
        """Options for a REVERT vote — candidates currently away from their default.
        A scalar reverts its one field; a preset reverts all its fields to default."""
        import game_rules as gr
        from constants import RULE_VOTE_CANDIDATES
        out = []
        for f, spec in RULE_VOTE_CANDIDATES.items():
            if not self._isChangedCandidate(f, spec, gameRules):
                continue
            if 'presets' in spec:
                fields = self._presetFields(spec)
                patch = {fld: gr.defaultRuleValue(fld) for fld in fields}
                out.append({"key": "revert:" + f, "label": spec.get('label', f),
                            "patch": patch, "field": None, "value": None})
            else:
                default = gr.defaultRuleValue(f)
                out.append({"key": f, "label": spec.get('label', f),
                            "patch": {f: default}, "field": f, "value": default})
        return out

    def _changedCount(self, gameRules) -> int:
        from constants import RULE_VOTE_CANDIDATES
        return sum(1 for f, spec in RULE_VOTE_CANDIDATES.items()
                   if self._isChangedCandidate(f, spec, gameRules))

    # ── Criticality chaos rules ────────────────────────────────────────────────
    def _randomChaosValue(self, field: str):
        """A fully random value for a candidate field — no exclusions, NO TD>FG
        guard (chaos: a field goal may outscore a touchdown). Floats get a whole/
        one-decimal mix; lists pick any member; bools pick either."""
        from constants import RULE_VOTE_CANDIDATES
        spec = RULE_VOTE_CANDIDATES.get(field, {})
        if 'values' in spec:
            return random.choice(spec['values'])
        rng = spec.get('range')
        if not rng:
            return None
        lo, hi = rng
        if spec.get('float') and random.random() < 0.5:
            return round(random.uniform(lo, hi), 1)
        return random.randint(int(lo), int(hi))

    def randomChaosRules(self, baseRules):
        """A per-game randomized ruleset for a Criticality game. FORMAT FIRST: pick the
        game format (standard or a preset) and apply its patch, THEN randomize every other
        candidate with values that WORK for that format — the format's own fields stay
        locked, the Drive Clock is skipped where it can't combine (synthetic / no game
        clock), and bust keeps whole-number scores so a game is still winnable. Both teams
        share it; hidden from users; results count. Base left untouched (deep-copied)."""
        import copy
        from constants import RULE_VOTE_CANDIDATES, GAME_FORMAT_PRESETS, CHAOS_FORMAT_CHANCE
        g = copy.deepcopy(baseRules)

        # 1) FORMAT FIRST — the format sets the game's whole contract, so choose + apply it
        #    before anything else and LOCK the fields it owns (a later random value must not
        #    break the format, e.g. bust needs integer scores + Sideline Goals on).
        formatFields = set()
        if random.random() < CHAOS_FORMAT_CHANCE:
            preset = random.choice(GAME_FORMAT_PRESETS)
            for fld, v in preset['patch'].items():
                setattr(g, fld, v)
                formatFields.add(fld)
        fmt = getattr(g, 'gameFormat', 'standard') or 'standard'
        # The Drive Clock is a GAME-clock shot clock — it only combines with formats that
        # actually run the game clock (skip the synthetic / no-clock formats).
        realClock = fmt in ('standard', 'target', 'bust', 'frames')

        # 1b) DORMANT MECHANICS — each independently coin-flipped ON/OFF (they don't all
        # have to be on). Contested Scoring is held out (in _CHAOS_EXCLUDE) until vetted.
        # A format preset may already own one (e.g. bust bundles Sideline Goals) — respect
        # that and don't re-roll it. These are excluded from the generic loop below.
        for mech in ('conversionLadderEnabled', 'sidelineGoalsEnabled'):
            if mech not in formatFields:
                setattr(g, mech, random.random() < 0.5)
        # The Conversion Ladder is played WITHOUT the safe kick — every post-TD try is a
        # forced go-for-it — so drop the kick whenever the ladder rolls on.
        if getattr(g, 'conversionLadderEnabled', False):
            g.conversionKickEnabled = False

        # 2) EVERY OTHER RULE — random, but within ranges that fit the chosen format.
        for f, spec in RULE_VOTE_CANDIDATES.items():
            if f == 'gameFormat' or f in _CHAOS_EXCLUDE or f in formatFields:
                continue
            if 'presets' in spec:
                # A preset mechanic (Drive Clock): coin-flip it on with a random preset
                # (impactful, so not every chaos game gets it) — but only where it fits.
                if f == 'driveClock' and not realClock:
                    continue
                if random.random() < 0.5:
                    for fld, v in random.choice(spec['presets'])['patch'].items():
                        setattr(g, fld, v)
                continue
            v = self._randomChaosValue(f)
            if v is None:
                continue
            # Bust is only winnable with WHOLE-number scores (land exactly on X). The bust
            # preset already locks the scoring values; this guards any stray float field.
            if fmt == 'bust' and spec.get('float'):
                v = round(v)
            setattr(g, f, v)
        return g

    # ── open ─────────────────────────────────────────────────────────────────
    def maybeOpenWindow(self, season: int, week: int, gameRules,
                        closesAt: Optional[datetime.datetime] = None) -> None:
        from constants import RULE_VOTE_ENABLED, RULE_VOTE_BALLOT_SIZE
        if not RULE_VOTE_ENABLED or week not in GAME_DAY_START_WEEKS:
            return
        dayIndex = self.dayIndexForWeek(week)
        from database.connection import get_session
        session = get_session()
        try:
            repo = self._repo(session)
            if repo.hasWindow(season, dayIndex):
                return  # this game day already processed (idempotent on restart)

            # Deterministic weekly cadence — a vote fires EVERY game day, no roll:
            #   day 0 -> Aris CHANGE, the Game Format only
            #   day 1,2 -> Aris CHANGE, everything else (scalars / display / mechanics)
            #   day 3 -> Pyre REVERT (the fan safety valve before the last day + playoffs)
            if dayIndex >= 3:
                kind = 'revert'
                options = self._revertOptions(gameRules)
            else:
                kind = 'change'
                allChange = self._changeOptions(gameRules)
                gfOpts = [o for o in allChange if 'gameFormat' in (o.get('patch') or {})]
                otherOpts = [o for o in allChange if 'gameFormat' not in (o.get('patch') or {})]
                # Day 0 is the Game Format day. If no format change is available (e.g.
                # the only built format is already active, no swap target), fall back
                # to the general pool so the day still fires.
                options = (gfOpts or otherOpts) if dayIndex == 0 else otherOpts

            # The Game Format day shows the FULL menu of formats (no truncation); every
            # other change/revert ballot is a random subset up to the ballot size.
            isFormatMenu = (dayIndex == 0 and bool(gfOpts))

            if not options:
                repo.recordDay(season, dayIndex, fired=False)
                session.commit()
                logger.info(f"Rule vote: S{season} day {dayIndex} ({kind}) — no candidates")
                return

            random.shuffle(options)
            if not isFormatMenu:
                options = options[:RULE_VOTE_BALLOT_SIZE]

            from managers.coresManager import ruleVoteConversation
            convo = ruleVoteConversation(kind)

            openedAt = datetime.datetime.utcnow()
            # closes_at (passed in) = the real games-start time = the countdown target.
            # Voting stays open until the sim resolves it AT games start; this is only
            # the cosmetic countdown, not the gate (see api _isVotingOpen).

            window = repo.recordDay(
                season, dayIndex, fired=True, kind=kind, core=convo['core'],
                options=options, promptLine=convo['prompt'],
                reactPickLine=convo['reactPick'], reactNoneLine=convo['reactNone'],
                openedAt=openedAt, closesAt=closesAt,
            )
            session.commit()
            logger.info(f"Rule vote OPEN: S{season} day {dayIndex} kind={kind} "
                        f"options={options} closes={closesAt}")

            # Announce it in the feed (Aris for change, Pyre for revert).
            self._broadcast(f'rule_vote_open_{kind}', session, season, week)
        except Exception as e:
            logger.warning(f"Rule vote open failed: {e}")
        finally:
            session.close()

    def forceOpenWindow(self, season: int, week: int, gameRules,
                        kind: Optional[str] = None, minutesOpen: int = 60) -> Optional[int]:
        """DEBUG/testing: open a rule vote on demand — bypasses the escalation roll
        AND the once-per-day idempotency, replacing any window for the current game
        day. Stays open `minutesOpen`. Returns the new window id (or None if there's
        no candidate for the requested kind)."""
        dayIndex = self.dayIndexForWeek(week)
        from database.connection import get_session
        from database.models import RuleVoteWindow
        from constants import RULE_VOTE_BALLOT_SIZE
        session = get_session()
        try:
            repo = self._repo(session)
            session.query(RuleVoteWindow).filter_by(season=season, day_index=dayIndex).delete()
            session.commit()
            changeOpts = self._changeOptions(gameRules)
            revertOpts = self._revertOptions(gameRules)
            if kind not in ('change', 'revert'):
                kind = 'change' if changeOpts else 'revert'
            pool = revertOpts if kind == 'revert' else changeOpts
            if not pool:  # requested kind has nothing to offer — fall back to the other
                kind = 'revert' if kind == 'change' else 'change'
                pool = revertOpts if kind == 'revert' else changeOpts
            if not pool:
                return None
            random.shuffle(pool)
            options = pool[:RULE_VOTE_BALLOT_SIZE]
            from managers.coresManager import ruleVoteConversation
            convo = ruleVoteConversation(kind)
            openedAt = datetime.datetime.utcnow()
            closesAt = openedAt + datetime.timedelta(minutes=minutesOpen)
            window = repo.recordDay(
                season, dayIndex, fired=True, kind=kind, core=convo['core'],
                options=options, promptLine=convo['prompt'],
                reactPickLine=convo['reactPick'], reactNoneLine=convo['reactNone'],
                openedAt=openedAt, closesAt=closesAt,
            )
            session.commit()
            self._broadcast(f'rule_vote_open_{kind}', session, season, week)
            logger.info(f"Rule vote FORCE-OPEN (debug): S{season} day {dayIndex} kind={kind}")
            return window.id
        except Exception as e:
            logger.warning(f"Force-open rule vote failed: {e}")
            return None
        finally:
            session.close()

    # ── resolve ──────────────────────────────────────────────────────────────
    def resolveOpenWindow(self, season: int, gameRules, requireClosed: bool = False) -> Optional[str]:
        """Resolve the season's open vote (most-voted wins). Applies the winner to
        the live rules + persists it, and announces the outcome. Returns the winner
        key ('none' or a field), or None if there was nothing to resolve.

        `requireClosed` (the sim's auto-resolve) only resolves a window whose close
        time has actually arrived, so a still-open window (esp. a debug-opened one
        with a future close time) is left alone until it's genuinely due."""
        if not self._enabled():
            return None
        from database.connection import get_session
        session = get_session()
        try:
            repo = self._repo(session)
            window = repo.getOpenWindow(season)
            if window is None:
                return None
            if requireClosed and window.closes_at is not None \
                    and datetime.datetime.utcnow() < window.closes_at:
                return None  # not due yet — leave it open (manual/debug window)
            specs = repo.optionSpecsOf(window)
            options = [s["key"] for s in specs]
            import game_rules as gr

            if window.kind == 'revert':
                # MULTI-SELECT approval: revert every active rule that lands on >= 50%
                # of the ballots (Pyre's fan safety valve). Below any voters => no-op.
                import math
                from constants import AWARD_HOF_APPROVAL_FRACTION
                counts, voters = repo.revertCounts(window.id)
                threshold = math.ceil(voters * AWARD_HOF_APPROVAL_FRACTION) if voters else 0
                winners = [k for k in options
                           if threshold and counts.get(k, 0) >= threshold]
                revertedLabels = []
                singlePrev = singleNew = None
                for k in winners:
                    winOpt = next((s for s in specs if s["key"] == k), None)
                    if not winOpt:
                        continue
                    patch = winOpt.get("patch") or {}
                    isScalar = winOpt.get("field") is not None
                    # Capture the REAL before/after for the 'what changed' line, the same
                    # way the change path does — storing the label as the "from" produced
                    # "Pyre restored Game Format: Game Format → Reverted".
                    if isScalar:
                        _prev = getattr(gameRules, winOpt["field"], None)
                    elif 'gameFormat' in patch:
                        _prev = self._formatDisplayName(getattr(gameRules, 'gameFormat', 'standard'))
                    else:
                        _prev = "On"
                    for fld in patch:
                        gr.revertRule(gameRules, fld, reason="pyre revert vote",
                                      source="cores_vote")
                    if isScalar:
                        _new = getattr(gameRules, winOpt["field"], None)
                    elif 'gameFormat' in patch:
                        _new = self._formatDisplayName(getattr(gameRules, 'gameFormat', 'standard'))
                    else:
                        _new = "Off"
                    revertedLabels.append(winOpt.get("label") or k)
                    if len(winners) == 1:
                        singlePrev, singleNew = _prev, _new
                applied = len(winners) > 0
                if not applied:
                    winnerKey, prevValue, newValue = 'none', None, None
                elif len(winners) == 1:
                    # e.g. "Pyre restored Game Format: Frames → Standard"
                    winnerKey, prevValue, newValue = winners[0], singlePrev, singleNew
                else:
                    # Several rules put back at once — no single from→to reads sensibly, so
                    # carry the LIST of labels and let the display name them without arrows.
                    winnerKey = 'revert:multi'
                    prevValue, newValue = ", ".join(revertedLabels), None
                repo.resolveWindow(window.id, winnerKey=winnerKey, applied=applied,
                                   prevValue=prevValue, newValue=newValue)
                session.commit()
                logger.info(f"Rule vote RESOLVE (revert): S{season} day {window.day_index} "
                            f"voters={voters} threshold={threshold} reverted={winners} "
                            f"counts={counts}")
                event = 'rule_reverted' if applied else 'rule_revert_none'
                self._broadcast(event, session, season, self._weekForDay(window.day_index))
                return winnerKey

            # ── change (single-pick plurality) ────────────────────────────────
            tally = repo.tally(window.id)
            winner = self._pickWinner(options, tally)
            applied = False
            prevValue = newValue = None
            newsText = None
            if winner != 'none' and winner in options:
                winOpt = next(s for s in specs if s["key"] == winner)
                patch = winOpt.get("patch") or {}
                isScalar = winOpt.get("field") is not None
                # 'what changed' display: scalar shows the field's before/after; a game
                # FORMAT shows the previous/new format name (never "Off" — default is
                # Standard); any other preset shows Off + its label.
                prevFmt = getattr(gameRules, 'gameFormat', 'standard')
                if isScalar:
                    prevValue = getattr(gameRules, winOpt["field"], None)
                for fld, v in patch.items():
                    gr.applyRuleChange(gameRules, fld, v, reason="aris change vote",
                                       source="cores_vote")
                if isScalar:
                    newValue = getattr(gameRules, winOpt["field"], None)
                elif 'gameFormat' in patch:
                    prevValue = self._formatDisplayName(prevFmt)
                    newValue = self._formatDisplayName(patch['gameFormat'])
                else:
                    prevValue, newValue = "Off", winOpt.get("label")
                applied = True
                # Factual headline for the league-news feed (neutral, not in a
                # Core's voice — Aris's in-character line lives in the Cores popover).
                label = winOpt.get("label") or "A rule"
                if 'gameFormat' in patch:
                    newsText = f"Rule change: the game format is now {newValue}."
                elif isScalar:
                    newsText = f"Rule change: {label} is now {newValue} (was {prevValue})."
                else:
                    newsText = f"Rule change: {label} is now on."

            repo.resolveWindow(window.id, winnerKey=winner, applied=applied,
                               prevValue=prevValue, newValue=newValue)
            session.commit()
            tiebroken = applied and getattr(self, '_lastTiebreak', False)
            if newsText:
                if tiebroken:
                    newsText += " Aris broke a tie to decide it."
                self._broadcastRuleChangeNews(
                    newsText, session, season, self._weekForDay(window.day_index))
            logger.info(f"Rule vote RESOLVE (change): S{season} day {window.day_index} "
                        f"winner={winner} applied={applied} tiebroken={tiebroken} tally={tally}")
            if tiebroken:
                event = 'rule_change_tiebreak'   # Aris broke a rule-vs-rule tie at random
            elif applied:
                event = 'rule_change_applied'
            else:
                event = 'rule_change_none'
            self._broadcast(event, session, season, self._weekForDay(window.day_index))
            return winner
        except Exception as e:
            logger.warning(f"Rule vote resolve failed: {e}")
            return None
        finally:
            session.close()

    def _pickWinner(self, options: List[str], tally: dict) -> str:
        """Most-voted option. A tie for the lead between two or more RULE options is
        broken at random — Aris's call (announced via the rule_change_tiebreak beat).
        A tie that includes 'none', a 'none' lead, or no votes resolves to no change:
        when 'keep it' is tied for the top, caution wins. `_lastTiebreak` records
        whether the winner came from a random tiebreak (for the announcement).
        RULE_VOTE_SIM_AUTOPICK breaks a zero-vote tie by random-picking a field
        (headless engine testing only)."""
        self._lastTiebreak = False
        total = sum(tally.values()) if tally else 0
        if total == 0:
            if os.environ.get('RULE_VOTE_SIM_AUTOPICK') and options:
                return random.choice(options)
            return 'none'
        # Consider every option plus 'none'.
        keys = list(options) + ['none']
        best = max(tally.get(k, 0) for k in keys)
        leaders = [k for k in keys if tally.get(k, 0) == best]
        if len(leaders) == 1:
            return leaders[0]
        # Tie for the lead. Aris breaks a tie BETWEEN rules at random; but if 'none'
        # (keep it as-is) is tied for the top, no change — caution takes the deadlock.
        ruleLeaders = [k for k in leaders if k != 'none']
        if len(ruleLeaders) >= 2:
            self._lastTiebreak = True
            return random.choice(ruleLeaders)
        return 'none'

    # ── plumbing ─────────────────────────────────────────────────────────────
    def _enabled(self) -> bool:
        from constants import RULE_VOTE_ENABLED
        return bool(RULE_VOTE_ENABLED)

    def _weekForDay(self, dayIndex: int) -> int:
        return dayIndex * 7 + 1

    def _broadcast(self, eventType: str, session, season: int, week: int) -> None:
        try:
            from managers.coresManager import entriesForEvent
            from managers.anomalyManager import _broadcastCoreEntries
            entries = entriesForEvent(eventType)
            _broadcastCoreEntries(entries, session=session, seasonNumber=season, week=week)
        except Exception as e:
            logger.warning(f"Rule vote broadcast ({eventType}) failed: {e}")

    def _broadcastRuleChangeNews(self, text: str, session, season: int, week: int) -> None:
        """Persist + broadcast a factual rule-change headline to the league-news
        feed (category 'rules'). Distinct from the Cores banter: this is the plain
        'what changed' item that shows in the main HighlightFeed (which filters out
        'cores' lines), so a rule change is actually visible there."""
        try:
            from database.models import LeagueNewsItem
            session.add(LeagueNewsItem(season=season, week=week, category='rules',
                                       event_type='rule_change', text=text))
            session.commit()
        except Exception as e:
            session.rollback()
            logger.debug(f"Rule news persist skipped: {e}")
        try:
            from api.game_broadcaster import broadcaster
            from api.event_models import LeagueNewsEvent
            if broadcaster is None or not broadcaster.is_enabled():
                return
            event = LeagueNewsEvent.leagueNews(text=text)
            event['category'] = 'rules'
            event['eventType'] = 'rule_change'
            broadcaster.broadcast_sync('season', event)
        except Exception as e:
            logger.debug(f"Rule news broadcast skipped: {e}")
