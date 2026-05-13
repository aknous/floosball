"""Per-Core signature equations — used during a Cracking.

Each active Core (the Conservator, the Pyre, Aris, Halverson) has its own
math shape that replaces the baseline `(R + ΣF) × (1 + Σ(M−1))` aggregator
while the Cracking is live. The Stenographer is meta-only and never takes
control, so it has no equation. The "broken simulation" framing is the
point: these equations are intentionally uncapped and produce outputs
many multiples above baseline.

Inputs (same three across all equations):
  R   = rosterFP (sum of fantasy points from the user's drafted players)
  F   = sum of flat-FP contributions from equipped cards
  M   = 1 + Σ(Mᵢ − 1) — the bonus-additive aggregate multiplier (≥ 1.0)

The caller is responsible for:
  * Detecting Cracking-active and resolving the controlling Core.
  * Subtracting raw rosterFP from the output when storing the
    card-bonus-only portion (mirrors how the baseline path does it).
"""

from __future__ import annotations

import math
from typing import List, Optional, Tuple


# Public list of Cores that can actually take control during a Cracking.
# Stenographer is excluded — per the design, it remains a meta-narrator.
CONTROLLING_CORES = ('the_conservator', 'the_pyre', 'aris', 'halverson')


def _bonusAdditiveMultiplier(multFactors: List[float]) -> float:
    """Match the baseline aggregator (cardEffectCalculator.aggregateMultFactors)
    so the Cracking equations operate on the same `M` the rest of the system
    sees on stable weeks. Duplicated here to avoid an import cycle."""
    return 1.0 + sum(max(0.0, f - 1.0) for f in multFactors)


def applyCoreEquation(
    coreKey: Optional[str],
    rosterFP: float,
    flatFPSum: float,
    multFactors: List[float],
) -> Tuple[float, str]:
    """Apply the active Core's signature equation. Returns (output, prettyEquation).

    `coreKey` is the Cores roster key (e.g. 'the_pyre'). Returns the baseline
    bonus-additive result if `coreKey` is None or unknown — this is the
    on-ramp for callers that always invoke this helper regardless of
    Cracking state.
    """
    R = float(rosterFP or 0.0)
    F = float(flatFPSum or 0.0)
    M = _bonusAdditiveMultiplier(multFactors)

    if coreKey == 'the_conservator':
        out = (R + F) * M * (M + 1.0)
        eqn = (
            f"(R + ΣF) × ΣM × (ΣM + 1)  "
            f"= ({R:.0f} + {F:.0f}) × {M:.2f} × {M + 1.0:.2f}  "
            f"= {out:.0f}"
        )
        return out, eqn

    if coreKey == 'the_pyre':
        # Cap exponent input so 32-bit math doesn't overflow on extreme stacks.
        # e^25 ≈ 7.2e10 — already absurd, beyond that just clamp.
        safeM = min(M, 25.0)
        out = (R + F) * math.exp(safeM)
        eqn = (
            f"(R + ΣF) × e^ΣM  "
            f"= ({R:.0f} + {F:.0f}) × e^{M:.2f}  "
            f"= {out:.0f}"
        )
        return out, eqn

    if coreKey == 'aris':
        # Γ(M+1) blows up past M≈170; cap at 50 so we still get insane numbers
        # but the math doesn't OverflowError.
        safeM = min(M, 50.0)
        gamma = math.gamma(safeM + 1.0)
        out = (R + F) * gamma + 4.0 * R
        eqn = (
            f"(R + ΣF) × Γ(ΣM + 1) + 4R  "
            f"= ({R:.0f} + {F:.0f}) × {gamma:.2f} + 4×{R:.0f}  "
            f"= {out:.0f}"
        )
        return out, eqn

    if coreKey == 'halverson':
        out = (R + F) * (M ** 2) + 6.0 * R
        eqn = (
            f"(R + ΣF) × ΣM² + 6R  "
            f"= ({R:.0f} + {F:.0f}) × {M ** 2:.2f} + 6×{R:.0f}  "
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

    When a Core is in control during a Cracking, returns its signature
    equation's output. Otherwise returns the compounding baseline that
    the rest of this branch uses today (matches the legacy aggregation
    so non-Cracking weeks behave unchanged).

    Callers should subtract rosterFP from the returned output if they're
    storing only the card-bonus portion (mirroring the existing flow).
    """
    if coreKey:
        return applyCoreEquation(coreKey, rosterFP, totalBonusFP, multFactors)
    # Compounding baseline. When next-season's bonus-additive change
    # merges in, this body becomes (R + F) × (1 + Σ(M−1)) — same
    # contract, same callers.
    multProduct = 1.0
    for f in multFactors:
        multProduct *= f
    output = (float(rosterFP or 0.0) + float(totalBonusFP or 0.0)) * multProduct
    equation = (
        f"(R + ΣF) × ∏(FPx)  "
        f"= ({rosterFP:.0f} + {totalBonusFP:.0f}) × {multProduct:.2f}  "
        f"= {output:.0f}"
    )
    return output, equation


def equationTemplate(coreKey: Optional[str]) -> str:
    """Return just the symbolic shape (no values substituted) for UI labels.

    Used to render the "current Core's formula" pill in the card breakdown
    UI without needing live numbers.
    """
    if coreKey == 'the_conservator':
        return "(R + ΣF) × ΣM × (ΣM + 1)"
    if coreKey == 'the_pyre':
        return "(R + ΣF) × e^ΣM"
    if coreKey == 'aris':
        return "(R + ΣF) × Γ(ΣM + 1) + 4R"
    if coreKey == 'halverson':
        return "(R + ΣF) × ΣM² + 6R"
    return "(R + ΣF) × ΣM"
