"""PersonalityManager - Assignment, drift, and template lookup.

Responsibilities:
- Assigning archetype / demeanor / quirk at player creation
- Enforcing Unique tier caps (1 active per league) and Common tier soft caps
- Weekly demeanor drift along the Composed<->Volatile spectrum
- Swapping quirks when demeanor drift pushes them out of range
- Loading YAML templates and selecting lines via the fallback cascade

The manager keeps in-memory indices of active quirks that are refreshed from
the player pool on init / after fresh start.
"""

import os
from collections import Counter, defaultdict
from random import random, choice, choices
from typing import List, Optional, Tuple

from logger_config import get_logger

from managers import personalityData as PD

logger = get_logger("floosball.personalityManager")

# Template directory (relative to project root)
TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'templates')
ARCHETYPE_TEMPLATE_FILE = 'archetype_reactions.yaml'
QUIRK_TEMPLATE_FILE = 'quirk_sidelines.yaml'
CROWD_TEMPLATE_FILE = 'crowd_atmosphere.yaml'


# Base weekly drift probability and modifiers
DRIFT_BASE_CHANCE = 0.015
DRIFT_EXTREME_MOOD_BONUS = 0.01    # Prolonged extreme mood amplifies change
DRIFT_YOUNG_BONUS = 0.01           # Players under 25 drift more readily
DRIFT_STOIC_PENALTY = -0.01        # Stoic players are "hard to leave"
DRIFT_DRAMATIC_BONUS = 0.01        # Dramatic players shift more frequently
DRIFT_YOUNG_AGE_CUTOFF = 25


class PersonalityManager:
    """Owns personality assignment, drift, and template selection."""

    def __init__(self, serviceContainer):
        self.serviceContainer = serviceContainer
        # Count of currently-active quirks keyed by quirk key
        self.activeQuirkCounts: Counter = Counter()
        # Set of currently-active Unique quirks (for the 1-active cap)
        self.activeUniqueQuirks: set = set()
        # Template pools keyed by layer tuple; lazy-loaded on first use
        self._archetypeTemplates: Optional[dict] = None
        self._quirkTemplates: Optional[dict] = None
        self._crowdTemplates: Optional[dict] = None
        # Per-player seen-template tracking for no-repeat during a season
        self._seenTemplates: defaultdict = defaultdict(set)
        logger.info("PersonalityManager initialized")

    # ------------------------------------------------------------------
    # Bookkeeping
    # ------------------------------------------------------------------

    def rebuildQuirkIndex(self, players: List) -> None:
        """Recount active quirks across a player population.

        Called after player generation / loading / retirement waves so the
        soft caps and unique-active set stay accurate.
        """
        counts: Counter = Counter()
        uniques: set = set()
        for player in players:
            attrs = getattr(player, 'attributes', None)
            if attrs is None:
                continue
            quirk = getattr(attrs, 'quirk', None)
            if not quirk:
                continue
            counts[quirk] += 1
            quirkDef = PD.QUIRKS.get(quirk)
            if quirkDef and quirkDef['tier'] == 'unique':
                uniques.add(quirk)
        self.activeQuirkCounts = counts
        self.activeUniqueQuirks = uniques
        logger.info(f"Quirk index rebuilt: {sum(counts.values())} quirked players, "
                    f"{len(uniques)} active uniques")

    def _registerQuirk(self, quirkKey: str) -> None:
        self.activeQuirkCounts[quirkKey] += 1
        quirkDef = PD.QUIRKS.get(quirkKey)
        if quirkDef and quirkDef['tier'] == 'unique':
            self.activeUniqueQuirks.add(quirkKey)

    def _unregisterQuirk(self, quirkKey: str) -> None:
        if self.activeQuirkCounts[quirkKey] > 0:
            self.activeQuirkCounts[quirkKey] -= 1
            if self.activeQuirkCounts[quirkKey] == 0:
                del self.activeQuirkCounts[quirkKey]
        quirkDef = PD.QUIRKS.get(quirkKey)
        if quirkDef and quirkDef['tier'] == 'unique' and self.activeQuirkCounts.get(quirkKey, 0) == 0:
            self.activeUniqueQuirks.discard(quirkKey)

    # ------------------------------------------------------------------
    # Assignment
    # ------------------------------------------------------------------

    def assignPersonality(self, player, forceRefresh: bool = False) -> None:
        """Assign archetype / demeanor / quirk to a player.

        Idempotent unless forceRefresh=True: if archetype is already set,
        existing values are preserved. Quirk assignment can re-roll if the
        current quirk is incompatible with the player's (archetype, demeanor).
        """
        attrs = getattr(player, 'attributes', None)
        if attrs is None:
            return

        # Archetype — permanent. Only rolls if unset or forced.
        if forceRefresh or not getattr(attrs, 'archetype', None):
            attrs.archetype = self._rollArchetype()

        # Demeanor — uniform random at creation, drifts over time.
        if forceRefresh or not getattr(attrs, 'demeanor', None):
            attrs.demeanor = self._rollDemeanor()

        # Normalize any legacy demeanor value to the new 6-value spectrum.
        if attrs.demeanor not in PD.DEMEANOR_INDEX:
            attrs.demeanor = self._migrateLegacyDemeanor(attrs.demeanor)

        # Quirk — rarity roll, then filter by (archetype, demeanor), soft caps.
        currentQuirk = getattr(attrs, 'quirk', None)
        if currentQuirk and not PD.isQuirkCompatible(currentQuirk, attrs.archetype, attrs.demeanor):
            # Stale quirk from prior state — unregister and re-roll.
            self._unregisterQuirk(currentQuirk)
            currentQuirk = None
            attrs.quirk = None

        if currentQuirk is None:
            newQuirk = self._rollQuirk(attrs.archetype, attrs.demeanor)
            attrs.quirk = newQuirk
            if newQuirk:
                self._registerQuirk(newQuirk)

    def _rollArchetype(self) -> str:
        keys = list(PD.ARCHETYPE_WEIGHTS.keys())
        weights = list(PD.ARCHETYPE_WEIGHTS.values())
        return choices(keys, weights=weights, k=1)[0]

    def _rollDemeanor(self) -> str:
        return choice(PD.DEMEANOR_SPECTRUM)

    def _migrateLegacyDemeanor(self, oldValue: Optional[str]) -> str:
        """Map a pre-personality-system demeanor to the new 6-state spectrum.

        Old values that were personality traits (goofy, wholesome, paranoid,
        superstitious, enigmatic, oblivious, shy, rude) moved to the quirk
        layer — here we approximate the closest emotional temperament so
        drift/templates still work. The player's archetype and quirk are
        re-rolled on assignment, so this is just a best-effort fallback.
        """
        mapping = {
            None: 'cool',
            '': 'cool',
            'stoic': 'stoic',
            'cool': 'cool',
            'intense': 'intense',
            'melancholy': 'melancholy',
            'fiery': 'fiery',
            'dramatic': 'dramatic',
            # Legacy trait-demeanors mapped to closest emotional state
            'goofy': 'cool',
            'shy': 'melancholy',
            'wholesome': 'cool',
            'rude': 'fiery',
            'paranoid': 'intense',
            'enigmatic': 'melancholy',
            'superstitious': 'intense',
            'oblivious': 'cool',
        }
        return mapping.get(oldValue, 'cool')

    # ------------------------------------------------------------------
    # Quirk rolling
    # ------------------------------------------------------------------

    def _rollQuirk(self, archetype: str, demeanor: str) -> Optional[str]:
        """Roll a quirk for the player, or return None if they don't get one.

        Steps:
        1. Roll quirked-vs-plain on QUIRKED_PLAYER_RATE
        2. Roll tier (75/20/4/1)
        3. Filter compatible quirks in that tier, demote tier if empty
        4. Enforce Unique tier cap and Common tier soft caps in selection
        """
        if random() > PD.QUIRKED_PLAYER_RATE:
            return None

        tier = self._rollTier()
        # Try selected tier first, demote if no viable pool
        tierOrder = ['unique', 'rare', 'uncommon', 'common']
        startIdx = tierOrder.index(tier)
        for idx in range(startIdx, len(tierOrder)):
            candidateTier = tierOrder[idx]
            quirkKey = self._selectQuirkInTier(candidateTier, archetype, demeanor)
            if quirkKey:
                return quirkKey
        return None

    def _rollTier(self) -> str:
        keys = list(PD.QUIRK_TIER_WEIGHTS.keys())
        weights = list(PD.QUIRK_TIER_WEIGHTS.values())
        return choices(keys, weights=weights, k=1)[0]

    def _selectQuirkInTier(self, tier: str, archetype: str, demeanor: str) -> Optional[str]:
        """Pick a quirk in the given tier compatible with archetype+demeanor.

        - Unique: must not already be active (organic pool)
        - Uncommon/Rare: subject to per-quirk caps
        - Common: soft-cap aware (prefers under-represented quirks)
        """
        eligible = PD.getEligibleQuirks(archetype, demeanor, tier=tier)
        if not eligible:
            return None

        cap = PD.QUIRK_TIER_CAPS.get(tier)

        if tier == 'unique':
            # Filter out already-active uniques
            eligible = [q for q in eligible if q not in self.activeUniqueQuirks]
            if not eligible:
                return None
            return choice(eligible)

        if tier in ('uncommon', 'rare'):
            # Filter out quirks at or above per-quirk cap
            eligible = [q for q in eligible if self.activeQuirkCounts.get(q, 0) < cap]
            if not eligible:
                return None
            return choice(eligible)

        if tier == 'common':
            # Soft-cap aware: weight by (targetShare - currentShare), with a
            # floor so every eligible quirk has some chance even if over cap.
            totalQuirked = sum(self.activeQuirkCounts.values())
            if totalQuirked == 0:
                return choice(eligible)
            weights = []
            for q in eligible:
                currentShare = self.activeQuirkCounts.get(q, 0) / totalQuirked
                headroom = PD.COMMON_QUIRK_TARGET_SHARE - currentShare
                # Floor at 0.05 so overrepresented quirks still appear rarely
                weights.append(max(0.05, headroom * 10 + 1.0))
            return choices(eligible, weights=weights, k=1)[0]

        return None

    # ------------------------------------------------------------------
    # Weekly drift
    # ------------------------------------------------------------------

    def checkWeeklyDrift(self, players: List, season: int, week: int, dbSession=None) -> list:
        """Run a drift roll on every active player.

        For each player whose roll succeeds, shift their demeanor +/- 1 on the
        spectrum and (if their current quirk falls out of range) swap to the
        nearest compatible quirk. Returns a list of change dicts for logging
        and optional WebSocket broadcasting.
        """
        changes = []
        for player in players:
            attrs = getattr(player, 'attributes', None)
            if attrs is None or not getattr(attrs, 'demeanor', None):
                continue
            if not getattr(attrs, 'archetype', None):
                continue

            if not self._rollDriftChance(player):
                continue

            newDemeanor = self._pickDriftTarget(attrs.demeanor)
            if newDemeanor is None or newDemeanor == attrs.demeanor:
                continue

            oldDemeanor = attrs.demeanor
            attrs.demeanor = newDemeanor
            changes.append({
                'playerId': getattr(player, 'id', None),
                'playerName': getattr(player, 'name', '?'),
                'type': 'demeanor',
                'from': oldDemeanor,
                'to': newDemeanor,
                'reason': 'weekly_drift',
            })

            # Check whether the existing quirk survives the shift
            oldQuirk = attrs.quirk
            if oldQuirk and not PD.isQuirkCompatible(oldQuirk, attrs.archetype, attrs.demeanor):
                newQuirk = self._swapQuirkAfterDrift(oldQuirk, attrs.archetype, attrs.demeanor)
                self._unregisterQuirk(oldQuirk)
                attrs.quirk = newQuirk
                if newQuirk:
                    self._registerQuirk(newQuirk)
                changes.append({
                    'playerId': getattr(player, 'id', None),
                    'playerName': getattr(player, 'name', '?'),
                    'type': 'quirk',
                    'from': oldQuirk,
                    'to': newQuirk,
                    'reason': 'demeanor_drift',
                })

        if changes and dbSession is not None:
            self._logChangesToDb(changes, season, week, dbSession)

        if changes:
            logger.info(f"Personality drift: {len(changes)} changes in S{season}W{week}")
        return changes

    def _rollDriftChance(self, player) -> bool:
        attrs = player.attributes
        chance = DRIFT_BASE_CHANCE

        # Mood extremes (tier 1 or 5) add drift pressure
        try:
            _, tierName = attrs.getMood()
            if tierName in ('electric', 'miserable'):
                chance += DRIFT_EXTREME_MOOD_BONUS
        except Exception:
            pass

        # Age: younger players drift more
        age = getattr(player, 'age', None)
        if age is not None and age < DRIFT_YOUNG_AGE_CUTOFF:
            chance += DRIFT_YOUNG_BONUS

        # Demeanor-specific stability
        if attrs.demeanor == 'stoic':
            chance += DRIFT_STOIC_PENALTY
        elif attrs.demeanor == 'dramatic':
            chance += DRIFT_DRAMATIC_BONUS

        chance = max(0.0, chance)
        return random() < chance

    def _pickDriftTarget(self, currentDemeanor: str) -> Optional[str]:
        """Pick an adjacent demeanor to drift toward. Edge nodes drift inward."""
        neighbors = PD.getAdjacentDemeanors(currentDemeanor)
        if not neighbors:
            return None
        return choice(neighbors)

    def _swapQuirkAfterDrift(self, oldQuirk: str, archetype: str, demeanor: str) -> Optional[str]:
        """Pick a replacement quirk using grid-proximity weighting.

        Strategy: find all quirks eligible for the new (archetype, demeanor),
        then weight them by similarity to the old quirk (same tier preferred,
        then similar archetype overlap). Rarity-matched where possible to keep
        the player's "flavor level" stable.
        """
        oldDef = PD.QUIRKS.get(oldQuirk)
        if oldDef is None:
            # Old quirk unknown — just pick a compatible one at the same tier.
            return self._selectQuirkInTier('common', archetype, demeanor)

        oldTier = oldDef['tier']
        oldArchs = set(oldDef['archetypes'])

        # Try same tier first, then progressively cheaper tiers
        tierOrder = [oldTier] + [t for t in ['uncommon', 'common'] if t != oldTier]
        for tier in tierOrder:
            candidates = [
                q for q in PD.getEligibleQuirks(archetype, demeanor, tier=tier)
                if q != oldQuirk
            ]
            if not candidates:
                continue

            weights = []
            for q in candidates:
                qDef = PD.QUIRKS[q]
                # Favor quirks with overlapping archetype pool (grid proximity proxy)
                overlap = len(set(qDef['archetypes']) & oldArchs)
                weights.append(1.0 + overlap)
            return choices(candidates, weights=weights, k=1)[0]

        return None

    def _logChangesToDb(self, changes: list, season: int, week: int, dbSession) -> None:
        try:
            from database.models import PlayerPersonalityHistory
            for change in changes:
                if change.get('playerId') is None:
                    continue
                row = PlayerPersonalityHistory(
                    player_id=change['playerId'],
                    season=season,
                    week=week,
                    change_type=change['type'],
                    from_value=change.get('from'),
                    to_value=change.get('to'),
                    reason=change.get('reason'),
                )
                dbSession.add(row)
            dbSession.commit()
        except Exception as e:
            logger.error(f"Failed to log personality history: {e}")
            try:
                dbSession.rollback()
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Bulk assignment helper
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Template loading and selection (Layers 1/2/3)
    # ------------------------------------------------------------------

    def _loadTemplates(self) -> None:
        """Lazy-load YAML template files into keyed lookup tables."""
        self._archetypeTemplates = self._loadYaml(ARCHETYPE_TEMPLATE_FILE)
        self._quirkTemplates = self._loadYaml(QUIRK_TEMPLATE_FILE)
        self._crowdTemplates = self._loadYaml(CROWD_TEMPLATE_FILE)

        total = 0
        for bag in (self._archetypeTemplates, self._quirkTemplates, self._crowdTemplates):
            for v in (bag or {}).values():
                if isinstance(v, list):
                    total += len(v)
                elif isinstance(v, dict):
                    for sub in v.values():
                        if isinstance(sub, list):
                            total += len(sub)
        logger.info(f"Personality templates loaded: {total} entries")

    def _loadYaml(self, filename: str) -> dict:
        import yaml
        path = os.path.join(TEMPLATE_DIR, filename)
        if not os.path.exists(path):
            logger.warning(f"Template file not found: {path}")
            return {}
        try:
            with open(path, 'r') as f:
                data = yaml.safe_load(f) or {}
            return data
        except Exception as e:
            logger.error(f"Failed to load {filename}: {e}")
            return {}

    def reloadTemplates(self) -> None:
        """Force-reload templates from disk (for hot editing during development)."""
        self._archetypeTemplates = None
        self._quirkTemplates = None
        self._crowdTemplates = None
        self._loadTemplates()

    def _ensureTemplatesLoaded(self) -> None:
        if self._archetypeTemplates is None:
            self._loadTemplates()

    def selectArchetypeLine(self, archetype: str, demeanor: str, event: str,
                            playerKey: Optional[str] = None) -> Optional[dict]:
        """Layer 1: pick a color-commentary line via fallback cascade.

        Cascade:
          1. (archetype, event) entries tagged with this demeanor
          2. (archetype, event) entries with no demeanor filter
          3. ('generic', event) entries
          4. None
        """
        self._ensureTemplatesLoaded()
        pool: list = []

        archEvents = (self._archetypeTemplates or {}).get(archetype, {})
        if isinstance(archEvents, dict):
            pool = archEvents.get(event) or []

        demeanorMatched = [e for e in pool if e.get('demeanor') == demeanor]
        demeanorAgnostic = [e for e in pool if not e.get('demeanor')]

        for candidates in (demeanorMatched, demeanorAgnostic):
            chosen = self._weightedPick(candidates, playerKey)
            if chosen:
                return chosen

        # Generic fallback
        genericEvents = (self._archetypeTemplates or {}).get('generic', {})
        if isinstance(genericEvents, dict):
            generic = genericEvents.get(event) or []
            chosen = self._weightedPick(generic, playerKey)
            if chosen:
                return chosen

        return None

    def selectQuirkSideline(self, quirk: str, demeanor: str,
                            playerKey: Optional[str] = None) -> Optional[dict]:
        """Layer 2: pick a sideline observation for a player's quirk."""
        self._ensureTemplatesLoaded()
        pool = (self._quirkTemplates or {}).get(quirk) or []

        demeanorMatched = [e for e in pool if e.get('demeanor') == demeanor]
        demeanorAgnostic = [e for e in pool if not e.get('demeanor')]

        for candidates in (demeanorMatched, demeanorAgnostic):
            chosen = self._weightedPick(candidates, playerKey)
            if chosen:
                return chosen
        return None

    def selectCrowdLine(self, quirk: str,
                        playerKey: Optional[str] = None) -> Optional[dict]:
        """Layer 3: crowd/atmosphere line keyed on quirk."""
        self._ensureTemplatesLoaded()
        pool = (self._crowdTemplates or {}).get(quirk) or []
        return self._weightedPick(pool, playerKey)

    def _weightedPick(self, pool: list, playerKey: Optional[str]) -> Optional[dict]:
        """Weighted random pick with per-player no-repeat tracking."""
        if not pool:
            return None

        if playerKey is not None:
            seen = self._seenTemplates[playerKey]
            fresh = [e for e in pool if id(e) not in seen]
            if fresh:
                pool = fresh
            else:
                seen.clear()

        weights = [max(1, int(e.get('weight', 1))) for e in pool]
        chosen = choices(pool, weights=weights, k=1)[0]
        if playerKey is not None:
            self._seenTemplates[playerKey].add(id(chosen))
        return chosen

    def resetSeasonalTracking(self) -> None:
        """Clear per-player template-usage tracking at season rollover."""
        self._seenTemplates.clear()

    def renderTemplate(self, entry: dict, tokens: dict) -> str:
        """Substitute {name}-style tokens in a template's text."""
        if not entry or 'text' not in entry:
            return ''
        text = entry['text']
        try:
            return text.format(**tokens)
        except (KeyError, IndexError):
            # Missing token — return raw text rather than crashing mid-game
            return text

    # ------------------------------------------------------------------
    # Bulk assignment helper
    # ------------------------------------------------------------------

    def assignToPlayerPool(self, players: List, forceRefresh: bool = False) -> dict:
        """Assign personality to every player in a pool, returning a summary."""
        # Reset counts so the pool is re-analyzed from scratch.
        if forceRefresh:
            self.activeQuirkCounts = Counter()
            self.activeUniqueQuirks = set()
        else:
            self.rebuildQuirkIndex(players)

        archetypeCounts: Counter = Counter()
        demeanorCounts: Counter = Counter()
        quirkedCount = 0
        for player in players:
            self.assignPersonality(player, forceRefresh=forceRefresh)
            attrs = getattr(player, 'attributes', None)
            if attrs is None:
                continue
            if attrs.archetype:
                archetypeCounts[attrs.archetype] += 1
            if attrs.demeanor:
                demeanorCounts[attrs.demeanor] += 1
            if attrs.quirk:
                quirkedCount += 1

        summary = {
            'total': len(players),
            'quirked': quirkedCount,
            'archetypes': dict(archetypeCounts),
            'demeanors': dict(demeanorCounts),
            'activeUniques': sorted(self.activeUniqueQuirks),
            'quirkCounts': dict(self.activeQuirkCounts),
        }
        return summary
