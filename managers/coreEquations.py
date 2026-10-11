"""Per-Core signature equations — used during a Criticality.

Each active Core (Cassian, Pyre, Aris, Halverson) has its own equation that
replaces the baseline `(R + ΣF) × ΣM` aggregator while the Criticality is
live. Vera is meta-only and never takes control, so it has no equation.

Inputs (same three across all equations):
  R   = rosterFP (sum of fantasy points from the user's drafted players)
  F   = sum of flat-FP contributions from equipped cards
  M   = 1 + Σ(Mᵢ − 1) — the bonus-additive aggregate multiplier (≥ 1.0)

⚠️ EACH CORE AMPLIFIES A DIFFERENT TERM, BY THE SAME K (owner, 2026-10-07):
  Pyre       FPx            (R + ΣF) × (1 + K·(ΣM − 1))
  Cassian    card flat FP   (R + K·ΣF) × ΣM
  Halverson  roster FP      (K·R + ΣF) × ΣM
  Aris       all three      (∛K·R + ∛K·ΣF) × (1 + ∛K·(ΣM − 1))
K = CRITICALITY_AMPLIFICATION. A build specialized in a Core's term gains up to K
times its normal week. Aris is the week for everyone: every build gains between ∛K
(no FPx) and K^(2/3) (FPx-heavy), 1.6x-2.5x at K=4.

They used to be (R+F)·e^M (Pyre), Γ(M+1) (Aris), M·(M+1) (Cassian) and M² (Halverson),
which ALL amplified FPx, three of them super-linearly. Reported by a player and
confirmed on the prod snapshot: Criticality weeks (1-5 a season) supplied 55-99% of a
top-3 finisher's season total, one Pyre week ran 335x a normal week, and the
leaderboard reduced to "stack the most FPx and wait for Pyre". Replayed through these
equations at K=4, seasons 4-8: 13-43%.

The caller is responsible for:
  * Detecting Criticality-active and resolving the controlling Core.
  * Subtracting raw rosterFP from the output when storing the
    card-bonus-only portion (mirrors how the baseline path does it).
  * Neutralizing the weekly modifier on a Criticality week (`modifierInForce`).
"""

from __future__ import annotations

from typing import List, Optional, Tuple


# Public list of Cores that can actually take control during a Criticality.
# Stenographer is excluded — per the design, it remains a meta-narrator.
CONTROLLING_CORES = ('cassian', 'pyre', 'aris', 'halverson')


def _bonusAdditiveMultiplier(multFactors: List[float]) -> float:
    """Match the baseline aggregator (cardEffectCalculator.aggregateMultFactors)
    so the Criticality equations operate on the same `M` the rest of the system
    sees on stable weeks. Duplicated here to avoid an import cycle."""
    return 1.0 + sum(max(0.0, f - 1.0) for f in multFactors)


def applyCoreEquation(
    coreKey: Optional[str],
    rosterFP: float,
    flatFPSum: float,
    multFactors: List[float],
) -> Tuple[float, str]:
    """Apply the active Core's signature equation. Returns (output, prettyEquation).

    `coreKey` is the Cores roster key (e.g. 'pyre'). Returns the baseline
    bonus-additive result if `coreKey` is None or unknown — this is the
    on-ramp for callers that always invoke this helper regardless of
    Criticality state.
    """
    from constants import CRITICALITY_AMPLIFICATION as K
    R = float(rosterFP or 0.0)
    F = float(flatFPSum or 0.0)
    M = _bonusAdditiveMultiplier(multFactors)

    if coreKey == 'pyre':
        boosted = 1.0 + K * (M - 1.0)
        out = (R + F) * boosted
        eqn = (
            f"(R + ΣF) × (1 + {K:g}·(ΣM − 1))  "
            f"= ({R:.0f} + {F:.0f}) × {boosted:.2f}  "
            f"= {out:.0f}"
        )
        return out, eqn

    if coreKey == 'cassian':
        out = (R + K * F) * M
        eqn = (
            f"(R + {K:g}·ΣF) × ΣM  "
            f"= ({R:.0f} + {K:g}×{F:.0f}) × {M:.2f}  "
            f"= {out:.0f}"
        )
        return out, eqn

    if coreKey == 'halverson':
        out = (K * R + F) * M
        eqn = (
            f"({K:g}·R + ΣF) × ΣM  "
            f"= ({K:g}×{R:.0f} + {F:.0f}) × {M:.2f}  "
            f"= {out:.0f}"
        )
        return out, eqn

    if coreKey == 'aris':
        k = K ** (1.0 / 3.0)
        boosted = 1.0 + k * (M - 1.0)
        out = k * (R + F) * boosted
        eqn = (
            f"∛{K:g}·(R + ΣF) × (1 + ∛{K:g}·(ΣM − 1))  "
            f"= {k:.2f}×({R:.0f} + {F:.0f}) × {boosted:.2f}  "
            f"= {out:.0f}"
        )
        return out, eqn

    # Stable / unknown Core — baseline. Same as aggregateMultFactors would
    # produce when chained with the standard `(R+F) × M` calc.
    out = (R + F) * M
    eqn = (
        f"(R + ΣF) × ΣM  "
        f"= ({R:.0f} + {F:.0f}) × {M:.2f}  "
        f"= {out:.0f}"
    )
    return out, eqn


def computeFinalOutput(
    rosterFP: float,
    totalBonusFP: float,
    multFactors: List[float],
    coreKey: Optional[str] = None,
) -> Tuple[float, str]:
    """Top-level output helper for the card calc.

    When a Core is in control during a Criticality, returns its signature
    equation's output. Otherwise returns the compounding baseline that
    the rest of this branch uses today (matches the legacy aggregation
    so non-Criticality weeks behave unchanged).

    Callers should subtract rosterFP from the returned output if they're
    storing only the card-bonus portion (mirroring the existing flow).
    """
    if coreKey:
        return applyCoreEquation(coreKey, rosterFP, totalBonusFP, multFactors)
    # Bonus-additive baseline — matches next-season's aggregator.
    # Stacked FPx grows linearly, not geometrically; single-FPx hands
    # unchanged. See cardEffectCalculator.aggregateMultFactors.
    from managers.cardEffectCalculator import aggregateMultFactors
    multProduct = aggregateMultFactors(multFactors)
    output = (float(rosterFP or 0.0) + float(totalBonusFP or 0.0)) * multProduct
    equation = (
        f"(R + ΣF) × (1 + Σ(FPx−1))  "
        f"= ({rosterFP:.0f} + {totalBonusFP:.0f}) × {multProduct:.2f}  "
        f"= {output:.0f}"
    )
    return output, equation


def equationTemplate(coreKey: Optional[str]) -> str:
    """Return just the symbolic shape (no values substituted) for UI labels.

    Used to render the "current Core's formula" pill in the card breakdown
    UI without needing live numbers.
    """
    from constants import CRITICALITY_AMPLIFICATION as K
    if coreKey == 'pyre':
        return f"(R + ΣF) × (1 + {K:g}·(ΣM − 1))"
    if coreKey == 'cassian':
        return f"(R + {K:g}·ΣF) × ΣM"
    if coreKey == 'halverson':
        return f"({K:g}·R + ΣF) × ΣM"
    if coreKey == 'aris':
        return f"∛{K:g}·(R + ΣF) × (1 + ∛{K:g}·(ΣM − 1))"
    return "(R + ΣF) × ΣM"


def modifierInForce(modifier: str, season: int, week: int) -> str:
    """The weekly modifier that actually applies: 'steady' on a Criticality week.

    ⚠️ A CRITICALITY WEEK RUNS ON THE CORE'S EQUATION ALONE (owner, 2026-10-07). The
    modifiers used to stack on top of it, which is where the biggest swings came from:
    Amplify doubles every FPx delta, so Amplify + Pyre produced the 1.47M-point season
    in season 1, while Grounded zeroed FPx on three Criticality weeks. Every modifier is
    neutralized, not just those two, so the week reads as one rule. Every place that
    resolves a week's modifier for scoring must pass it through here."""
    if not modifier or modifier == 'steady':
        return modifier
    try:
        from managers.anomalyManager import getActiveCriticalityCore
        if getActiveCriticalityCore(season, week):
            return 'steady'
    except Exception:
        pass
    return modifier
