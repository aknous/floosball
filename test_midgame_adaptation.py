"""Mid-game adaptation regression: adaptable coaches re-plan on the fly.

Coaching initiative #1. The universal halftime adjustment re-plans every team
once; `Game._maybeReadjustGameplans()` adds EXTRA re-planning at the Q2 and Q4
boundaries, gated by ADAPTABILITY (frequency) — the adjust functions already
scale the MAGNITUDE by adaptability. Intended behavior:

  - low-adaptability coaches (<= ~76) NEVER re-plan mid-game (ride one plan),
  - highly-adaptable coaches re-plan often,
  - a sputtering offense (yds/play < 4.5) makes an adaptable coach re-plan MORE
    (senses it isn't working), and
  - a fire actually mutates the REAL gameplan (runPassRatio shifts toward what
    worked), not just increments a counter.

This exercises the real method bound to a minimal Game stub, the real
`adjustOffensiveGameplan`/`adjustDefensiveGameplan`, and the real gameplan
objects — only the RNG is seeded and the adjust calls are wrapped to count fires
(the wrapper delegates, so the real mutation still happens).

Run: .venv/bin/python test_midgame_adaptation.py
"""
import managers  # resolve circular import
import floosball_game as fg
from gameplan import OffensiveGameplan, DefensiveGameplan


class StubCoach:
    def __init__(self, adaptability):
        self.adaptability = adaptability
        self.offensiveMind = 80
        self.defensiveMind = 80


class StubTeam:
    def __init__(self, coach):
        self.coach = coach


# Two half-stat profiles. Both are asymmetric (run beating pass) so a fire
# produces a detectable runPassRatio shift; they differ only in yds/play so one
# trips the "sputtering" boost and one doesn't.
CRUISING = dict(  # 20 plays, 115 yds -> 5.75 ypp (>= 4.5, no boost)
    runPlays=10, runYards=70, passAttempts=10, passYards=45, wr1Yards=25, wr2Yards=20)
STRUGGLING = dict(  # 20 plays, 78 yds -> 3.9 ypp (< 4.5, boost)
    runPlays=10, runYards=48, passAttempts=10, passYards=30, wr1Yards=18, wr2Yards=12)


def _makeGame(adaptability, profile):
    """A minimal Game carrying only what _maybeReadjustGameplans touches, with the
    real method bound and fresh real gameplan objects. HOME has the coach under
    test; AWAY has no coach (must never fire)."""
    g = fg.Game.__new__(fg.Game)
    g._maybeReadjustGameplans = fg.Game._maybeReadjustGameplans.__get__(g, fg.Game)
    g.homeTeam = StubTeam(StubCoach(adaptability))
    g.awayTeam = StubTeam(None)
    g.homeOffGameplan = OffensiveGameplan()
    g.homeDefGameplan = DefensiveGameplan()
    g.awayOffGameplan = OffensiveGameplan()
    g.awayDefGameplan = DefensiveGameplan()
    for side in ('home', 'away'):
        for k, v in profile.items():
            setattr(g, f'{side}Half{k[0].upper()}{k[1:]}', v)
    return g


def _fireRate(adaptability, profile, trials=600, seed=1234):
    """Fraction of trials in which the HOME (coached) team re-plans, counted by
    wrapping the real adjust fns. Returns (rate, awayFires, sampleShift)."""
    fg._random.seed(seed)
    realAdjO = fg.adjustOffensiveGameplan
    realAdjD = fg.adjustDefensiveGameplan
    homeFires = [0]
    awayFires = [0]
    sampleShift = [0.0]
    try:
        for _ in range(trials):
            g = _makeGame(adaptability, profile)
            baseline = g.homeOffGameplan.runPassRatio

            def wrapO(plan, coach, stats, **kw):
                if plan is g.homeOffGameplan:
                    homeFires[0] += 1
                elif plan is g.awayOffGameplan:
                    awayFires[0] += 1
                realAdjO(plan, coach, stats, **kw)
            fg.adjustOffensiveGameplan = wrapO
            fg.adjustDefensiveGameplan = realAdjD  # exercised, uncounted

            g._maybeReadjustGameplans()
            if g.homeOffGameplan.runPassRatio != baseline:
                sampleShift[0] = g.homeOffGameplan.runPassRatio - baseline
    finally:
        fg.adjustOffensiveGameplan = realAdjO
        fg.adjustDefensiveGameplan = realAdjD
    return homeFires[0] / trials, awayFires[0], sampleShift[0]


def main():
    fails = []

    def check(label, cond, detail=""):
        print(f"{label:<62}{'PASS' if cond else 'FAIL'}  {detail}")
        fails.append(not cond)

    print("Fire rate = fraction of Q-boundary calls where the coached team re-plans\n")

    r60, away60, _ = _fireRate(60, CRUISING)
    r76, _, _ = _fireRate(76, CRUISING)
    r88, _, _ = _fireRate(88, CRUISING)
    r100c, _, shift100 = _fireRate(100, CRUISING)
    r100s, _, _ = _fireRate(100, STRUGGLING)

    print(f"  adapt 60  cruising : {r60:.0%}")
    print(f"  adapt 76  cruising : {r76:.0%}")
    print(f"  adapt 88  cruising : {r88:.0%}")
    print(f"  adapt 100 cruising : {r100c:.0%}")
    print(f"  adapt 100 struggle : {r100s:.0%}\n")

    # 1. Below the adaptability gate (60, 76) a coach NEVER re-plans mid-game.
    check("adapt 60  -> never re-plans (0%)", r60 == 0.0, f"{r60:.0%}")
    check("adapt 76  -> never re-plans (0%)", r76 == 0.0, f"{r76:.0%}")

    # 2. An adaptable coach re-plans at a mid rate (design ~34% at 88).
    check("adapt 88  -> re-plans sometimes (0.20-0.50)", 0.20 <= r88 <= 0.50, f"{r88:.0%}")

    # 3. Max adaptability re-plans often (design ~69% cruising).
    check("adapt 100 -> re-plans often (0.55-0.82)", 0.55 <= r100c <= 0.82, f"{r100c:.0%}")

    # 4. Adaptability is monotonic: 76 < 88 < 100.
    check("higher adaptability -> higher rate (76<88<100)", r76 < r88 < r100c)

    # 5. A sputtering offense makes an adaptable coach re-plan MORE (1.6x boost,
    #    clamped at 1.0 -> should approach always).
    check("struggling offense re-plans more than cruising", r100s > r100c, f"{r100s:.0%} > {r100c:.0%}")
    check("struggling adapt 100 -> nearly always (>= 0.95)", r100s >= 0.95, f"{r100s:.0%}")

    # 6. A fire mutates the REAL plan (asymmetric run-beats-pass stats -> run lean).
    check("a fire actually shifts runPassRatio (real adjust ran)", shift100 > 0.0, f"+{shift100:.3f}")

    # 7. A coachless team never re-plans, regardless of stats.
    check("coachless team never re-plans", away60 == 0, f"{away60} fires")

    allPass = not any(fails)
    print("\nOVERALL:", "ALL PASS" if allPass else "SOME FAIL")
    return 0 if allPass else 1


if __name__ == '__main__':
    raise SystemExit(main())
