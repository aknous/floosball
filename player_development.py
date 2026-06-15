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
    DEV_ATTRIBUTE_FLOOR,
)
from logger_config import get_logger

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
    def careerContext(player: Any, devBias: int) -> DevContext:
        """Resolve the player's current arc phase + decline steepening."""
        seasons = getattr(player, 'seasonsPlayed', 0) or 0
        attrs = getattr(player, 'attributes', None)
        longevity = getattr(attrs, 'longevity', 6) if attrs else 6
        peak = PlayerDevelopment.peakSeason(player)
        isProspect = (
            bool(getattr(player, 'is_prospect', False))
            or seasons <= DEV_PROSPECT_SEASONS
        )

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
                          isProspect=isProspect, devBias=devBias)

    @staticmethod
    def developAttribute(current: int, potential: int, ctx: DevContext) -> int:
        """Apply one offseason's change to a single trained attribute.

        Phase sets the base direction; devBias accelerates the climb (rising
        only); prospects get a boom/bust spread; positive growth is capped at the
        attribute's potential ceiling; decline can fade below MIN_ATTRIBUTE_VALUE
        down to DEV_ATTRIBUTE_FLOOR.
        """
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

        change = randint(lo, hi)
        # Positive growth is capped by the player's potential ceiling (so the
        # climb tapers as they approach it — realized peak height). Decline is
        # uncapped on the downside (to the floor).
        if change > 0:
            change = min(change, max(0, potential - current))

        return max(DEV_ATTRIBUTE_FLOOR, min(MAX_ATTRIBUTE_VALUE, current + change))

    @staticmethod
    def update_intangible_attributes(attributes: Any) -> None:
        """Update attitude and discipline with small random changes."""
        attributes.attitude = max(0, min(100, attributes.attitude + randint(-5, 5)))
        attributes.discipline = max(0, min(100, attributes.discipline + randint(-5, 5)))
        if hasattr(attributes, 'calculateIntangibles'):
            attributes.calculateIntangibles()

    @staticmethod
    def _dev(attributes: Any, attrName: str, potentialName: str, ctx: DevContext) -> None:
        """Develop one named attribute in place against its potential ceiling."""
        current = getattr(attributes, attrName, 0)
        potential = getattr(attributes, potentialName, MAX_ATTRIBUTE_VALUE)
        setattr(attributes, attrName,
                PlayerDevelopment.developAttribute(current, potential, ctx))

    @staticmethod
    def develop_quarterback_attributes(attributes: Any, ctx: DevContext) -> None:
        PlayerDevelopment._dev(attributes, 'armStrength', 'potentialArmStrength', ctx)
        PlayerDevelopment._dev(attributes, 'accuracy', 'potentialAccuracy', ctx)
        PlayerDevelopment._dev(attributes, 'agility', 'potentialAgility', ctx)

    @staticmethod
    def develop_skill_position_attributes(attributes: Any, position_type: str, ctx: DevContext) -> None:
        PlayerDevelopment._dev(attributes, 'speed', 'potentialSpeed', ctx)
        if position_type == "RB":
            PlayerDevelopment._dev(attributes, 'power', 'potentialPower', ctx)
        else:  # WR / TE
            PlayerDevelopment._dev(attributes, 'hands', 'potentialHands', ctx)
        PlayerDevelopment._dev(attributes, 'agility', 'potentialAgility', ctx)
        PlayerDevelopment._dev(attributes, 'reach', 'potentialReach', ctx)

    @staticmethod
    def develop_kicker_attributes(attributes: Any, ctx: DevContext) -> None:
        PlayerDevelopment._dev(attributes, 'legStrength', 'potentialLegStrength', ctx)
        PlayerDevelopment._dev(attributes, 'accuracy', 'potentialAccuracy', ctx)

    @staticmethod
    def apply_offseason_training(player: Any, position_type: str = None,
                                 coachDevRating: int = 50, fundingDevBonus: int = 0) -> Dict[str, Any]:
        """Apply one offseason's training to a player.

        coachDevRating (0-100): coach's playerDevelopment attribute.
        fundingDevBonus: market-tier bonus (-1..+1). Together they form devBias,
        which accelerates a RISING player's climb (and skews prospect booms) but
        does NOT slow the aging decline.
        Returns a dict of development details for logging.
        """
        try:
            # devBias: coach (60→0, 80→+2, 100→+4) + funding tier (-1..+1).
            devBias = round((coachDevRating - 60) / 10) + fundingDevBonus

            PlayerDevelopment.update_intangible_attributes(player.attributes)

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
