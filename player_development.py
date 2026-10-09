"""Player development service for offseason training.

Career-arc model: each player has a PEAK season (a jittered fraction of their
longevity). They RISE toward peak, PLATEAU, then DECLINE — and the decline is
decoupled from the retirement clock so it actually manifests while the player is
still rostered. The phase sign (up vs down) is INTRINSIC to where the player is
in their arc; coach playerDevelopment + market tier (devBias) only modulate how
fast/much a RISING player climbs (their realized peak height), never reversing
the aging decline. This replaces the old prime/decline binary that let ratings
ratchet upward forever (the league inflated to all-5-star by ~season 9).
"""

import random
from random import randint
from typing import Dict, Any
from dataclasses import dataclass
from enum import Enum
from constants import (
    MIN_ATTRIBUTE_VALUE, MAX_ATTRIBUTE_VALUE,
    DEV_PEAK_FRACTION_LOW, DEV_PEAK_FRACTION_HIGH, DEV_PEAK_SEASON_MIN,
    DEV_RISE_RANGE, DEV_PEAK_RANGE, DEV_DECLINE_RANGE,
    DEV_DECLINE_STEEPEN_PER_SEASON, DEV_DECLINE_PAST_LONGEVITY_KICK,
    DEV_DECLINE_MAX_STEEPEN, DEV_PROSPECT_SPREAD, DEV_PROSPECT_SEASONS,
    DEV_ATTRIBUTE_FLOOR, DEV_DECLINE_FACTOR_LOW, DEV_DECLINE_FACTOR_HIGH,
    DEV_DECLINE_FACTOR_MODE, DEV_PEAK_FLOOR_FRACTION,
    DEV_OVERSHOOT_BASE_CHANCE, DEV_OVERSHOOT_BIAS_PER_POINT,
)
from logger_config import get_logger

# Each developing attribute's PEAK field: the highest value it has reached, which sets
# its decline floor (DEV_PEAK_FLOOR_FRACTION). 0 = not yet recorded.
PEAK_ATTR_NAMES = {a: 'peak' + a[0].upper() + a[1:] for a in (
    'speed', 'power', 'agility', 'reach', 'hands', 'armStrength', 'accuracy', 'legStrength')}

logger = get_logger("floosball.development")


class CareerPhase(Enum):
    RISING = "rising"
    PEAK = "peak"
    DECLINING = "declining"


@dataclass
class DevContext:
    """Everything the per-attribute change needs for one player this offseason."""
    phase: CareerPhase
    intensity: int        # decline steepening (0 while rising/at peak)
    isProspect: bool      # boom/bust volatility
    devBias: int          # coach + market-tier push (applied to the climb only)
    declineFactor: float = 1.0  # per-player decline severity (gentle..cliff)


class PlayerDevelopment:
    """Service class for handling player development during offseason."""

    @staticmethod
    def peakSeason(player: Any) -> int:
        """The season a player peaks — a jittered fraction of longevity, stable
        per player (seeded off id) so it doesn't wander between offseasons. No
        DB storage needed."""
        attrs = getattr(player, 'attributes', None)
        longevity = getattr(attrs, 'longevity', 6) if attrs else 6
        pid = getattr(player, 'id', None)
        seed = int(pid) if pid else (abs(hash(getattr(player, 'name', ''))) % (2 ** 31))
        rng = random.Random((seed * 2654435761) & 0xFFFFFFFF)
        frac = rng.uniform(DEV_PEAK_FRACTION_LOW, DEV_PEAK_FRACTION_HIGH)
        return max(DEV_PEAK_SEASON_MIN, round(longevity * frac))

    @staticmethod
    def declineProfile(player: Any) -> float:
        """Per-player decline severity, stable per player (seeded off id, and mixed
        independently of peak timing). Low = ages gracefully / good for a long career;
        ~1.0 = a normal gradual slide; high = falls off a cliff. So not every player
        follows the same arc. No DB storage needed."""
        pid = getattr(player, 'id', None)
        seed = int(pid) if pid else (abs(hash(getattr(player, 'name', ''))) % (2 ** 31))
        rng = random.Random((seed * 1099087573 + 12345) & 0xFFFFFFFF)
        # Triangular around MODE so most players are gradual decliners, with the
        # ageless (low) and cliff (high) ends as rarer tails.
        return rng.triangular(DEV_DECLINE_FACTOR_LOW, DEV_DECLINE_FACTOR_HIGH,
                              DEV_DECLINE_FACTOR_MODE)

    @staticmethod
    def careerSeasons(player: Any) -> int:
        """Seasons since he entered the league: pro seasons PLUS pipeline seasons.

        ⚠️ DEVELOPMENT DOES NOT DEPEND ON ROSTER STATUS (owner, 2026-09-27). The arc used to
        read `seasonsPlayed` alone, which does not advance while a player is a prospect —
        so every pipeline season was a free RISING season that never aged him, and
        promotion started the clock. Two players drafted together developed differently
        depending on whether their team promoted them. `prospect_seasons` counts the
        pipeline seasons served and is deliberately KEPT through promotion (and a washout
        keeps it too), so the sum is the same clock whatever his status.

        ⚠️ DEVELOPMENT ONLY. Retirement, contracts and service time still read
        `seasonsPlayed`, which is pro seasons.
        """
        return int(getattr(player, 'seasonsPlayed', 0) or 0) + \
            int(getattr(player, 'prospect_seasons', 0) or 0)

    @staticmethod
    def careerContext(player: Any, devBias: int) -> DevContext:
        """Resolve the player's current arc phase + decline steepening."""
        seasons = PlayerDevelopment.careerSeasons(player)
        attrs = getattr(player, 'attributes', None)
        longevity = getattr(attrs, 'longevity', 6) if attrs else 6
        peak = PlayerDevelopment.peakSeason(player)
        # Boom/bust for his first seasons in the league, prospect or not.
        isProspect = seasons <= DEV_PROSPECT_SEASONS

        if seasons < peak:
            phase = CareerPhase.RISING
            intensity = 0
        elif seasons == peak:
            phase = CareerPhase.PEAK
            intensity = 0
        else:
            phase = CareerPhase.DECLINING
            steepen = (seasons - peak) * DEV_DECLINE_STEEPEN_PER_SEASON
            if seasons > longevity:
                steepen += DEV_DECLINE_PAST_LONGEVITY_KICK
            intensity = min(DEV_DECLINE_MAX_STEEPEN, steepen)

        return DevContext(phase=phase, intensity=intensity,
                          isProspect=isProspect, devBias=devBias,
                          declineFactor=PlayerDevelopment.declineProfile(player))

    @staticmethod
    def declineFloor(peak: int) -> int:
        """The lowest a declining attribute may fall: DEV_PEAK_FLOOR_FRACTION of its
        peak, or the absolute DEV_ATTRIBUTE_FLOOR, whichever is higher."""
        return max(DEV_ATTRIBUTE_FLOOR, round((peak or 0) * DEV_PEAK_FLOOR_FRACTION))

    @staticmethod
    def _changeRange(ctx: DevContext):
        """The (lo, hi) range one offseason's raw change is drawn from, uniformly."""
        if ctx.phase == CareerPhase.RISING:
            lo, hi = DEV_RISE_RANGE
            lo += ctx.devBias
            hi += ctx.devBias
        elif ctx.phase == CareerPhase.PEAK:
            lo, hi = DEV_PEAK_RANGE
        else:  # DECLINING — intrinsic aging, devBias deliberately NOT applied
            lo, hi = DEV_DECLINE_RANGE
            lo -= ctx.intensity
            hi -= ctx.intensity

        if ctx.isProspect:
            # Boom/bust: widen both tails; good dev skews the top tail up.
            lo -= DEV_PROSPECT_SPREAD
            hi += DEV_PROSPECT_SPREAD + max(0, ctx.devBias)
        return lo, hi

    @staticmethod
    def _growthCeiling(trueSkill: int, potential: int) -> int:
        return trueSkill if trueSkill and trueSkill > 0 else potential

    @staticmethod
    def _canOvershoot(change: int, trueSkill: int, potential: int, ctx: DevContext) -> bool:
        """Whether this roll gets an overshoot chance: growth, not declining, and a
        potential above the true-skill cap."""
        return (change > 0 and ctx.phase != CareerPhase.DECLINING
                and potential > PlayerDevelopment._growthCeiling(trueSkill, potential))

    @staticmethod
    def _overshootChance(ctx: DevContext) -> float:
        return DEV_OVERSHOOT_BASE_CHANCE + max(0, ctx.devBias) * DEV_OVERSHOOT_BIAS_PER_POINT

    @staticmethod
    def _settle(current: int, change: int, trueSkill: int, potential: int, ctx: DevContext,
                peak: int, overshoot: bool) -> int:
        """The attribute after a raw change from `_changeRange`, given whether the
        overshoot roll came up. Deterministic: `developAttribute` rolls and calls this,
        `expectedAttribute` averages it over every roll."""
        # Per-player decline severity: scale the drop so some players age gracefully
        # and others fall off a cliff, instead of every vet following the same arc.
        if ctx.phase == CareerPhase.DECLINING and change < 0:
            change = round(change * ctx.declineFactor)
        # Positive growth is capped at TRUE SKILL (the reliable target). A gated
        # per-season overshoot roll — likelier with good coaching/facilities —
        # lifts the cap to the potential ceiling, letting a few players exceed
        # their projection. Declining players never overshoot.
        if change > 0:
            ceiling = PlayerDevelopment._growthCeiling(trueSkill, potential)
            if overshoot:
                ceiling = potential
            change = min(change, max(0, ceiling - current))

        floor = PlayerDevelopment.declineFloor(peak)
        return min(MAX_ATTRIBUTE_VALUE, max(current + change, min(current, floor)))

    @staticmethod
    def developAttribute(current: int, trueSkill: int, potential: int, ctx: DevContext,
                         peak: int = 0) -> int:
        """Apply one offseason's change to a single trained attribute.

        Phase sets the base direction; devBias accelerates the climb (rising
        only); prospects get a boom/bust spread.

        Growth is capped at the player's TRUE SKILL (the mature target they
        reliably develop into) — NOT their potential. Each non-declining season
        there's a gated chance (raised by devBias) that the player OVERSHOOTS,
        lifting the cap to their potential ceiling for that season — the rare
        overachiever who exceeds projection. Decline stops at `declineFloor(peak)`:
        80% of the highest value the attribute reached, never below 60. The floor
        never LIFTS an attribute already under it; it only stops it falling.
        (trueSkill <= 0 → no true-skill data; fall back to the potential ceiling so
        unmapped/legacy attrs still behave.)
        """
        lo, hi = PlayerDevelopment._changeRange(ctx)
        change = randint(lo, hi)
        overshoot = (PlayerDevelopment._canOvershoot(change, trueSkill, potential, ctx)
                     and random.random() < PlayerDevelopment._overshootChance(ctx))
        return PlayerDevelopment._settle(current, change, trueSkill, potential, ctx, peak, overshoot)

    @staticmethod
    def expectedAttribute(current: int, trueSkill: int, potential: int, ctx: DevContext,
                          peak: int = 0) -> float:
        """The AVERAGE of `developAttribute` over every roll, computed exactly: each
        change in the range is equally likely, and an overshoot-eligible roll splits
        on the overshoot chance. What the front office projects with."""
        lo, hi = PlayerDevelopment._changeRange(ctx)
        chance = PlayerDevelopment._overshootChance(ctx)
        total = 0.0
        for change in range(lo, hi + 1):
            plain = PlayerDevelopment._settle(current, change, trueSkill, potential, ctx, peak, False)
            if PlayerDevelopment._canOvershoot(change, trueSkill, potential, ctx):
                over = PlayerDevelopment._settle(current, change, trueSkill, potential, ctx, peak, True)
                total += (1 - chance) * plain + chance * over
            else:
                total += plain
        return total / (hi - lo + 1)

    @staticmethod
    def update_intangible_attributes(attributes: Any) -> None:
        """Update attitude and discipline with small random changes."""
        attributes.attitude = max(0, min(100, attributes.attitude + randint(-5, 5)))
        attributes.discipline = max(0, min(100, attributes.discipline + randint(-5, 5)))
        if hasattr(attributes, 'calculateIntangibles'):
            attributes.calculateIntangibles()

    @staticmethod
    def _dev(attributes: Any, attrName: str, trueSkillName: str, potentialName: str, ctx: DevContext) -> None:
        """Develop one named attribute in place — climbs toward true skill,
        overshoots toward potential on a gated roll."""
        current = getattr(attributes, attrName, 0)
        trueSkill = getattr(attributes, trueSkillName, 0)
        potential = getattr(attributes, potentialName, MAX_ATTRIBUTE_VALUE)
        peak = PlayerDevelopment._resolvePeak(attributes, attrName, current, trueSkill, ctx)
        newValue = PlayerDevelopment.developAttribute(current, trueSkill, potential, ctx, peak=peak)
        setattr(attributes, attrName, newValue)
        peakName = PEAK_ATTR_NAMES.get(attrName)
        if peakName:
            setattr(attributes, peakName, max(peak, newValue))

    @staticmethod
    def _resolvePeak(attributes: Any, attrName: str, current: int, trueSkill: int,
                     ctx: DevContext) -> int:
        """The attribute's peak for this offseason (never below today's value)."""
        peakName = PEAK_ATTR_NAMES.get(attrName)
        peak = int(getattr(attributes, peakName, 0) or 0) if peakName else 0
        if peak <= 0:
            # Not recorded yet (every player before peaks were tracked, and a new one).
            # A rising player's best is today's value. One already past his peak season
            # most likely got as far as his true skill, the target development carries a
            # player to, so that is the best estimate of a high nobody recorded.
            peak = current
            if ctx.phase == CareerPhase.DECLINING and trueSkill:
                peak = max(current, trueSkill)
        return max(peak, current)

    # The attributes each position trains, as (attribute, trueSkill, potential) names.
    TRAINED_ATTRIBUTES = {
        'QB': [('armStrength', 'trueSkillArmStrength', 'potentialArmStrength'),
               ('accuracy', 'trueSkillAccuracy', 'potentialAccuracy'),
               ('agility', 'trueSkillAgility', 'potentialAgility')],
        'RB': [('speed', 'trueSkillSpeed', 'potentialSpeed'),
               ('power', 'trueSkillPower', 'potentialPower'),
               ('agility', 'trueSkillAgility', 'potentialAgility'),
               ('reach', 'trueSkillReach', 'potentialReach')],
        'WR': [('speed', 'trueSkillSpeed', 'potentialSpeed'),
               ('hands', 'trueSkillHands', 'potentialHands'),
               ('agility', 'trueSkillAgility', 'potentialAgility'),
               ('reach', 'trueSkillReach', 'potentialReach')],
        'K': [('legStrength', 'trueSkillLegStrength', 'potentialLegStrength'),
              ('accuracy', 'trueSkillAccuracy', 'potentialAccuracy')],
    }
    TRAINED_ATTRIBUTES['TE'] = TRAINED_ATTRIBUTES['WR']

    @staticmethod
    def _developAll(attributes: Any, positionType: str, ctx: DevContext) -> None:
        for attrName, trueName, potName in PlayerDevelopment.TRAINED_ATTRIBUTES[positionType]:
            PlayerDevelopment._dev(attributes, attrName, trueName, potName, ctx)

    @staticmethod
    def develop_quarterback_attributes(attributes: Any, ctx: DevContext) -> None:
        PlayerDevelopment._developAll(attributes, 'QB', ctx)

    @staticmethod
    def develop_skill_position_attributes(attributes: Any, position_type: str, ctx: DevContext) -> None:
        PlayerDevelopment._developAll(attributes, 'RB' if position_type == 'RB' else 'WR', ctx)

    @staticmethod
    def develop_kicker_attributes(attributes: Any, ctx: DevContext) -> None:
        PlayerDevelopment._developAll(attributes, 'K', ctx)

    @staticmethod
    def expectedAttributes(player: Any, devBias: int) -> Dict[str, float]:
        """{attribute: expected value after this offseason's development} for every
        attribute the player's position trains, from the same rules and the same
        career context the offseason uses. Late blooms and the intangible drift are
        left out: the bloom is a hidden roll and the drift averages to zero."""
        position = getattr(getattr(player, 'position', None), 'name', None)
        trained = PlayerDevelopment.TRAINED_ATTRIBUTES.get(position)
        attributes = getattr(player, 'attributes', None)
        if not trained or attributes is None:
            return {}
        ctx = PlayerDevelopment.careerContext(player, devBias)
        out = {}
        for attrName, trueName, potName in trained:
            current = getattr(attributes, attrName, 0)
            trueSkill = getattr(attributes, trueName, 0)
            potential = getattr(attributes, potName, MAX_ATTRIBUTE_VALUE)
            peak = PlayerDevelopment._resolvePeak(attributes, attrName, current, trueSkill, ctx)
            out[attrName] = PlayerDevelopment.expectedAttribute(current, trueSkill, potential,
                                                                ctx, peak=peak)
        return out

    @staticmethod
    def selfDevelopmentBias(player: Any) -> int:
        """Development bias for an UNROSTERED player, from their own mental
        makeup rather than a coach's `playerDevelopment`.

        A free agent has no staff, so what improvement they make comes down to
        whether they keep themselves sharp — discipline, focus, resilience and
        self-belief. Mapped onto the same scale coaches use so the two are
        directly comparable, then damped (FA_SELF_DEV_SCALE) because training
        alone is genuinely less effective than being coached, and floored at
        FA_SELF_DEV_MIN so sitting in the pool is stagnation, never decay.
        """
        from constants import (FA_SELF_DEV_ATTRS, FA_SELF_DEV_SCALE, FA_SELF_DEV_MIN,
                               FA_SELF_DEV_YEARS_BONUS, FA_SELF_DEV_YEARS_CAP,
                               FA_SELF_DEV_TOTAL_CAP)
        attrs = getattr(player, 'attributes', None)
        if attrs is None:
            return FA_SELF_DEV_MIN

        # ⚠️ THE UNSIGNED YEARS TERM IS WHAT STOPS THE POOL BEING A HOLDING PEN. The
        # floor above means an unsigned player stagnates rather than declines, but a GM
        # signs by comparing against an incumbent, so a player who stagnates below that
        # bar misses again next season and every season after — the pool then only ever
        # drains through retirement. Each season unsigned adds to their own bias, on the
        # reading that a player with nothing else to do works at it.
        #
        # ⚠️ Self-limiting rather than tuned: it accrues ONLY while unsigned, and
        # signing resets `freeAgentYears` to 0. Capped so nobody trains their way into a
        # superstar from the pool — the road back is meant to be real, not a shortcut
        # that beats being coached.
        years = int(getattr(player, 'freeAgentYears', 0) or 0)
        yearsBonus = min(years * FA_SELF_DEV_YEARS_BONUS, FA_SELF_DEV_YEARS_CAP)

        vals = [float(getattr(attrs, a, 0) or 0) for a in FA_SELF_DEV_ATTRS]
        vals = [v for v in vals if v > 0]
        if not vals:
            return max(FA_SELF_DEV_MIN, min(int(yearsBonus), FA_SELF_DEV_TOTAL_CAP))
        selfDrive = sum(vals) / len(vals)
        bias = round((selfDrive - 60) / 10 * FA_SELF_DEV_SCALE) + yearsBonus
        # Clamped to the best coach in the league. Without this the years term stacks on
        # top of self-drive and going unsigned outperforms being coached.
        bias = min(bias, FA_SELF_DEV_TOTAL_CAP)
        return max(FA_SELF_DEV_MIN, int(bias))

    @staticmethod
    def apply_offseason_training(player: Any, position_type: str = None,
                                 coachDevRating: int = None, fundingDevBonus: int = 0) -> Dict[str, Any]:
        """Apply one offseason's training to a player.

        coachDevRating (0-100): coach's playerDevelopment attribute.
        fundingDevBonus: Training Facility bonus (0..2.0, fractional per level).
        Together they form devBias, which accelerates a RISING player's climb (and
        skews prospect booms) but does NOT slow the aging decline.
        Returns a dict of development details for logging.
        """
        try:
            # devBias: coach (60→0, 80→+2, 100→+4) + Training Facility bonus.
            # The facility bonus is fractional per level (every level a real step);
            # resolve it to an integer probabilistically so devBias stays
            # randint-safe while each level still scales the EXPECTED bias
            # (e.g. 0.4 → +1 forty percent of the time).
            fb = float(fundingDevBonus or 0)
            fundingInt = int(fb // 1)
            frac = fb - fundingInt
            if frac > 0 and random.random() < frac:
                fundingInt += 1
            if coachDevRating is None:
                # UNROSTERED: no staff, so the player trains off their own
                # makeup. Floored at zero — being unsigned must never be worse
                # than having a bad coach, which is what the old default-50
                # fallback produced (devBias -1). No facility bonus either:
                # they have no facility.
                devBias = PlayerDevelopment.selfDevelopmentBias(player)
            else:
                devBias = round((coachDevRating - 60) / 10) + fundingInt

            PlayerDevelopment.update_intangible_attributes(player.attributes)

            # ⚠️ THE LATE BLOOM FIRES BEFORE THE SEASON'S GROWTH, so the new trueSkill is
            # the target this very offseason rather than one wasted year later.
            #
            # ⚠️ IT FIRES ON A ROLL, NOT ON THE FIRST DEVELOPMENT SEASON. Always-year-one
            # would make every bloomer identical and, worse, make the scouted band jump at
            # a predictable moment — a reader would learn that the season-one jump IS the
            # tell. A roll spreads it across the window.
            bloomed = 0
            if int(getattr(player, 'lateBloomPending', 0) or 0) > 0:
                from constants import LATE_BLOOM_FIRE_BASE, LATE_BLOOM_FIRE_PER_BIAS
                # ⚠️ THE ENVIRONMENT DECIDES THE ODDS (owner). `devBias` is the coach's
                # playerDevelopment plus the Training Facility bonus, already computed
                # above — so a well-run team develops the talent it drafted and a poorly-run
                # one can lose a player it never knew it had, since the bloom has to fire
                # inside the window or he walks.
                fire = LATE_BLOOM_FIRE_BASE + max(0, devBias) * LATE_BLOOM_FIRE_PER_BIAS
                if random.random() < fire:
                    bloomed = player.applyLateBloom()
                    if bloomed:
                        logger.info(
                            f"LATE BLOOM: {getattr(player, 'name', '?')} gains +{bloomed} "
                            f"on every trained attribute (dev bias {devBias}); "
                            f"nobody scouted this")

            ctx = PlayerDevelopment.careerContext(player, devBias)

            # Snapshot the trained attributes for change-logging.
            tracked = {
                "QB": ['armStrength', 'accuracy', 'agility'],
                "RB": ['speed', 'power', 'agility', 'reach'],
                "WR": ['speed', 'hands', 'agility', 'reach'],
                "TE": ['speed', 'hands', 'agility', 'reach'],
                "K":  ['legStrength', 'accuracy'],
            }.get(position_type, [])
            original_values = {a: getattr(player.attributes, a, 0) for a in tracked}

            if position_type == "QB":
                PlayerDevelopment.develop_quarterback_attributes(player.attributes, ctx)
            elif position_type in ("RB", "WR", "TE"):
                PlayerDevelopment.develop_skill_position_attributes(player.attributes, position_type, ctx)
            elif position_type == "K":
                PlayerDevelopment.develop_kicker_attributes(player.attributes, ctx)

            changes = {}
            for attr, original in original_values.items():
                new_value = getattr(player.attributes, attr, original)
                if new_value != original:
                    changes[attr] = {'from': original, 'to': new_value, 'change': new_value - original}

            logger.info(
                f"Player {getattr(player, 'name', '?')} dev "
                f"[{ctx.phase.value}{'/prospect' if ctx.isProspect else ''}"
                f"{f'/int{ctx.intensity}' if ctx.intensity else ''}, bias {devBias}]: {changes}"
            )

            return {
                'lateBloom': bloomed,
                'player_name': getattr(player, 'name', 'Unknown'),
                'position': position_type,
                'phase': ctx.phase.value,
                'is_prospect': ctx.isProspect,
                'dev_bias': devBias,
                'changes': changes,
            }

        except Exception as e:
            logger.error(f"Error in offseason training for player {getattr(player, 'name', 'Unknown')}: {e}")
            return {'player_name': getattr(player, 'name', 'Unknown'), 'error': str(e)}
