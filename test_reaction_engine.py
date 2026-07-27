"""Smoke test for PersonalityReactionEngine.

Loads the engine, runs assignment over a synthetic player population,
and prints sample reactions/sidelines for every personality across every
event polarity. Verifies:
- YAML loads cleanly
- Every personality returns a reaction for positive/negative
- Every personality returns a sideline cutaway
- Quirk append works (eligibility + format)
- Mood-name lookup works
- OVR-tiered assignment produces sensible distributions
"""

import random
from collections import Counter

from managers.personalityReactionEngine import (
    PersonalityReactionEngine,
    BASE_VIBES, COMMON_VARIANTS, RARE_VARIANTS, BASE_VIBE_WEIGHTS,
)


def headerLine(text: str) -> str:
    return f"\n{'─' * 70}\n{text}\n{'─' * 70}"


def testReactions(engine: PersonalityReactionEngine):
    """Print sample reactions for every personality across event types."""
    eventKeys = ['scored_td', 'threw_td', 'made_fg', 'missed_fg',
                 'got_sacked', 'made_sack', 'threw_int', 'made_int',
                 'fumbled', 'recovered_fumble']
    polarityMap = {
        'scored_td': 'positive', 'threw_td': 'positive',
        'made_fg': 'positive', 'missed_fg': 'negative',
        'got_sacked': 'negative', 'made_sack': 'positive',
        'threw_int': 'negative', 'made_int': 'positive',
        'fumbled': 'negative', 'recovered_fumble': 'positive',
    }

    ctx = {
        'name': 'Player',
        'receiver': 'Receiver',
        'passer': 'QB',
        'sacker': 'Sacker',
        'fumbler': 'Fumbler',
    }

    print(headerLine("PERSONALITY REACTIONS"))
    for personality in sorted(engine.personalities.keys()):
        print(f"\n{personality}:")
        for event in eventKeys:
            polarity = polarityMap[event]
            line = engine.pickPersonalityLine(personality, event, polarity,
                                               {**ctx, 'name': personality.title()})
            print(f"  {event:18} ({polarity}) → {line}")


def testSidelines(engine: PersonalityReactionEngine):
    """Print sample sideline cutaways for every personality."""
    print(headerLine("SIDELINE CUTAWAYS"))
    for personality in sorted(engine.personalities.keys()):
        line = engine.pickSidelineCutaway(personality, None,
                                           ctx={'name': personality.title()})
        takesQuirks = engine.takesQuirks(personality)
        marker = '+q' if takesQuirks else '  '
        print(f"  {personality:18} {marker} → {line}")


def testCompositions(engine: PersonalityReactionEngine):
    """Test personality + quirk composed reactions."""
    print(headerLine("COMPOSED REACTIONS (personality + quirk)"))
    samples = [
        ('stoic', 'snacker', 'scored_td', 'positive'),
        ('lively', 'singer', 'made_int', 'positive'),
        ('cool', 'bling', 'made_sack', 'positive'),
        ('fiery', 'gym_rat', 'missed_fg', 'negative'),
        ('chill', 'transistor', 'fumbled', 'negative'),
        ('wholesome', 'hugger', 'threw_td', 'positive'),
        ('goofy', 'magician', 'recovered_fumble', 'positive'),
        ('paranoid', 'crime_show_watcher', 'made_int', 'positive'),
        ('cursed', 'sketcher', 'got_sacked', 'negative'),
        ('superstitious', 'whistler', 'missed_fg', 'negative'),
    ]
    for personality, quirk, event, polarity in samples:
        if not engine.isQuirkCompatible(personality, quirk):
            print(f"  {personality} + {quirk} INCOMPATIBLE")
            continue
        ctx = {'name': 'Player', 'passer': 'QB', 'receiver': 'WR'}
        # Force quirk append by setting chance to 1.0
        line = engine.composeReaction(personality, quirk, event, polarity, ctx,
                                       quirkAppendChance=1.0)
        print(f"  {personality:14} + {quirk:18} ({event}) →")
        print(f"     {line}")


def testMoodNames(engine: PersonalityReactionEngine):
    print(headerLine("MOOD NAMES (1=very bad → 5=very good)"))
    for personality in sorted(engine.personalities.keys()):
        moods = [engine.getMoodName(personality, i) for i in range(1, 6)]
        print(f"  {personality:18}: {' → '.join(str(m) for m in moods)}")


def testAssignment(engine: PersonalityReactionEngine, n: int = 1000):
    """Simulate assignment over n synthetic players, show distribution."""
    print(headerLine(f"ASSIGNMENT DISTRIBUTION (n={n} players)"))

    # Realistic OVR distribution skew (rough)
    def randomOvr() -> int:
        # Skew toward 60-80 OVR with a tail to 90+
        roll = random.random()
        if roll < 0.30:
            return random.randint(50, 69)
        elif roll < 0.60:
            return random.randint(70, 79)
        elif roll < 0.80:
            return random.randint(80, 84)
        elif roll < 0.92:
            return random.randint(85, 89)
        else:
            return random.randint(90, 99)

    counts = Counter()
    quirkCounts = Counter()
    quirkedTotal = 0
    perOvrTier = {'<70': Counter(), '70-79': Counter(), '80-84': Counter(),
                   '85-89': Counter(), '90+': Counter()}

    for _ in range(n):
        ovr = randomOvr()
        personality = engine.assignPersonality(ovr)
        quirk = engine.assignQuirk(personality)
        counts[personality] += 1
        if quirk:
            quirkCounts[quirk] += 1
            quirkedTotal += 1

        # Track by OVR tier
        if ovr < 70:
            tier = '<70'
        elif ovr < 80:
            tier = '70-79'
        elif ovr < 85:
            tier = '80-84'
        elif ovr < 90:
            tier = '85-89'
        else:
            tier = '90+'
        perOvrTier[tier][personality] += 1

    print("\nPersonality counts (sorted):")
    for p, c in counts.most_common():
        bucket = ('base' if p in BASE_VIBES
                  else 'common-variant' if p in COMMON_VARIANTS
                  else 'rare-variant')
        pct = 100.0 * c / n
        print(f"  {p:18} ({bucket:14}) {c:4}  {pct:5.1f}%")

    variantTotal = sum(c for p, c in counts.items() if p not in BASE_VIBES)
    print(f"\nTotal variants: {variantTotal} / {n} = {100.0 * variantTotal / n:.1f}%")
    print(f"Total quirked: {quirkedTotal} / {n} = {100.0 * quirkedTotal / n:.1f}%")

    print("\nVariants by OVR tier:")
    for tier, tcounts in perOvrTier.items():
        variantsInTier = sum(c for p, c in tcounts.items() if p not in BASE_VIBES)
        totalInTier = sum(tcounts.values())
        if totalInTier == 0:
            continue
        pct = 100.0 * variantsInTier / totalInTier
        print(f"  {tier:8}: {variantsInTier:3}/{totalInTier:4} = {pct:5.1f}% variants")


def testIncompatibility(engine: PersonalityReactionEngine):
    """Verify quirk incompatibility filtering."""
    print(headerLine("QUIRK ELIGIBILITY"))
    print(f"\n{'personality':18} | eligible quirks")
    for personality in sorted(engine.personalities.keys()):
        eligible = engine.getEligibleQuirks(personality)
        takesQuirks = engine.takesQuirks(personality)
        if not takesQuirks:
            print(f"  {personality:18} | (takes_quirks: false)")
        else:
            print(f"  {personality:18} | {len(eligible):2} quirks: {', '.join(eligible)}")


def main():
    engine = PersonalityReactionEngine()
    print(f"Engine loaded: {len(engine.personalities)} personalities, {len(engine.quirks)} quirks")

    testMoodNames(engine)
    testIncompatibility(engine)
    testReactions(engine)
    testSidelines(engine)
    testCompositions(engine)
    testAssignment(engine, n=2000)


if __name__ == '__main__':
    main()
