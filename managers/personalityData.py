"""Personality static data — DEPRECATED.

The old archetype + demeanor + quirk model has been replaced by the
PersonalityReactionEngine which loads personality and quirk data directly
from data/templates/{vibe_reactions,quirk_reactions}.yaml.

This module is kept as a no-op shim in case any legacy import paths
still reference it. New code should use:
    from managers.personalityReactionEngine import PersonalityReactionEngine
"""

# All legacy tables removed. The engine owns personality/quirk data now.
