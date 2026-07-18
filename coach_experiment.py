"""Controlled coach A/B: does a better coach win more games with the same roster?

Uses REAL distinct teams (no cloning — the engine has id-value-dependent behavior
that makes deep-copied mirror matches unreliable). The SUBJECT team plays a
repeated round-robin against every OTHER team, home and away. Between arms, only
the SUBJECT coach changes; every opponent coach is pinned neutral (all attrs 80)
in every arm. So any win-rate difference across arms is the subject coach.

To keep the coach delta visible (not buried under a talent gap or pushed into a
win% ceiling), the subject is CALIBRATED: with a neutral coach it should win
~50% against the field. We scan candidate teams and pick the one closest to 50%.

Arms:
  - adaptability 60 / 80 / 100 (all other coach attrs = 80) -> isolates adaptability
  - all-65 (bad) / all-95 (elite)                            -> overall coach quality
(all-80 / adaptability-80 is the shared "average" reference.)

Usage: DATABASE_DIR=/tmp/floo_coachexp .venv/bin/python coach_experiment.py [roundsPerArm]
"""
import os, sys, asyncio, copy, multiprocessing as mp

os.environ.setdefault('DATABASE_DIR', '/tmp/floo_coachexp')
os.environ.setdefault('TIMING_MODE', 'fast')

import managers  # MUST precede any floosball_game import (resolves the circular import)

COACH_ATTRS = ('offensiveMind', 'defensiveMind', 'adaptability', 'aggressiveness',
               'clockManagement', 'playerDevelopment', 'scouting', 'attitude')

ARMS = [
    ('adaptability 60', {'adaptability': 60}),
    ('adaptability 80 (avg)', {'adaptability': 80}),
    ('adaptability 100', {'adaptability': 100}),
    ('bad all-65', {'base': 65}),
    ('elite all-95', {'base': 95}),
]


def _setCoach(coach, **overrides):
    base = overrides.pop('base', 80)
    for a in COACH_ATTRS:
        setattr(coach, a, base)
    for k, v in overrides.items():
        setattr(coach, k, v)


def _resetTeamState(team):
    team.pressureModifier = 1.0
    team.streakPressure = 0.0


def _teamStrength(team):
    r = [p.playerRating for p in team.rosterDict.values() if p is not None]
    return sum(r) / len(r) if r else 0.0


_APP = None


def _bootApp():
    global _APP
    if _APP is not None:
        return _APP
    from database.connection import init_db
    from service_container import container
    from config_manager import get_config
    from managers.floosballApplication import FloosballApplication
    init_db()
    cfg = get_config(); cfg['timingMode'] = 'fast'
    app = FloosballApplication(container)
    asyncio.run(app.initializeLeague(cfg, force_fresh=False))
    _APP = app
    return app


async def _playOne(home, away, rules):
    import floosball_game as fg
    _resetTeamState(home); _resetTeamState(away)
    g = fg.Game(home, away, gameRules=rules)
    await g.playGame()
    return g.homeScore, g.awayScore


async def _roundRobin(subject, opponents, rounds, rules):
    """subject vs every opponent, home and away, `rounds` times. Returns
    (wins, losses, ties, pointDiff, games)."""
    w = l = t = diff = games = 0
    for _ in range(rounds):
        for opp in opponents:
            hs, as_ = await _playOne(subject, opp, rules); games += 1
            diff += hs - as_
            if hs > as_: w += 1
            elif hs < as_: l += 1
            else: t += 1
            hs, as_ = await _playOne(opp, subject, rules); games += 1
            diff += as_ - hs
            if as_ > hs: w += 1
            elif as_ < hs: l += 1
            else: t += 1
    return w, l, t, diff, games


def _calibrateWorker(argsTuple):
    """Neutral-coach round-robin for one candidate subject; returns its win%."""
    name, rounds = argsTuple
    from game_rules import GameRules
    app = _bootApp()
    teams = app.teamManager.teams
    subject = next(x for x in teams if x.name == name)
    opponents = [x for x in teams if x is not subject]
    _setCoach(subject.coach)
    for o in opponents:
        _setCoach(o.coach)
    w, l, t, d, g = asyncio.run(_roundRobin(subject, opponents, rounds, GameRules()))
    return (name, w / g * 100, _teamStrength(subject))


def _armWorker(argsTuple):
    label, overrides, subjectName, rounds, seed = argsTuple
    import floosball_game as fg
    from game_rules import GameRules
    overrides = dict(overrides)
    # Control key: override the mid-game re-plan config for this arm. The halftime
    # adjustment (advanceQuarter's Q2->Q3 branch) is never affected by this.
    replanCfg = overrides.pop('_replanConfig', None)
    if replanCfg is not None:
        fg._REPLAN_CONFIG.update(replanCfg)
    fg._random.seed(seed)
    app = _bootApp()
    teams = app.teamManager.teams
    subject = next(x for x in teams if x.name == subjectName)
    opponents = [x for x in teams if x is not subject]
    _setCoach(subject.coach, **overrides)
    for o in opponents:
        _setCoach(o.coach)
    w, l, t, d, g = asyncio.run(_roundRobin(subject, opponents, rounds, GameRules()))
    return (label, w, l, t, d, g)


def _fmt(label, w, l, t, diff, n):
    wr = w / n * 100
    se = (wr * (100 - wr) / n) ** 0.5
    return (f"  {label:<24} {w:>5}-{l:<5}{('-'+str(t)) if t else '     '}  "
            f"win% {wr:5.1f} ±{se:.1f}   avg margin {diff/n:+6.2f}")


def _calibrateSubject(rounds=8):
    """Boot, scan candidate teams, return the name of the one whose neutral-coach
    win% is closest to 50%, plus the full calibration table. The strength->win
    curve is steep, so ~50% sits well below the roster-rating median; scan a
    lower band at enough rounds to beat the calibration noise."""
    procs = min(8, max(1, (os.cpu_count() or 2) - 1))
    app = _bootApp()
    teams = sorted(app.teamManager.teams, key=_teamStrength)
    idxs = sorted(set(int(len(teams) * p) for p in (0.05, 0.15, 0.25, 0.35, 0.45)))
    candidates = [teams[i].name for i in idxs]
    with mp.Pool(processes=min(procs, len(candidates))) as pool:
        cal = pool.map(_calibrateWorker, [(name, rounds) for name in candidates])
    cal.sort(key=lambda r: abs(r[1] - 50))
    return cal[0][0], cal, len(teams)


def mainReplan():
    """Isolate ONLY the mid-game re-plan feature: adaptability 100 with the
    feature ON vs OFF (halftime adjustment identical in both). The gap is the
    pure win contribution of _maybeReadjustGameplans."""
    rounds = int(sys.argv[2]) if len(sys.argv) > 2 else 100
    subjectName, cal, nTeams = _calibrateSubject()
    print("Calibration (neutral coach, win% vs field):")
    for name, wr, strg in sorted(cal, key=lambda r: r[2]):
        mark = '  <- subject' if name == subjectName else ''
        print(f"  {name:<14} strength {strg:5.1f}   neutral win% {wr:5.1f}{mark}")
    n = rounds * (nTeams - 1) * 2
    print(f"\nTUNE THE MID-GAME RE-PLAN — subject '{subjectName}', adaptability 100 in every arm.")
    print(f"Round-robin vs {nTeams-1} teams, home+away, {rounds}x ({n} games/arm). Same seed (paired).")
    print(f"Halftime adjustment identical in all arms; only the mid-game re-plan config differs.\n")
    # All at adaptability 100. Variants of the mid-game re-plan:
    arms = [
        ('OFF (no mid-game replan)', {'_replanConfig': {'enabled': False}}),
        ('OLD (both, unconditional)', {'_replanConfig': {'enabled': True, 'fire_q1q2': True, 'fire_q3q4': True, 'sample_aware': False}}),
        ('NEW (sample-aware, both)',  {'_replanConfig': {'enabled': True, 'fire_q1q2': True, 'fire_q3q4': True, 'sample_aware': True}}),
        ('Q3Q4-only (sample-aware)',  {'_replanConfig': {'enabled': True, 'fire_q1q2': False, 'fire_q3q4': True, 'sample_aware': True}}),
    ]
    jobs = [(label, {'adaptability': 100, **ov}, subjectName, rounds, 4242) for label, ov in arms]
    with mp.Pool(processes=len(jobs)) as pool:
        results = pool.map(_armWorker, jobs)
    byLabel = {r[0]: r for r in results}
    off = byLabel['OFF (no mid-game replan)']
    offWinPct = off[1] / off[5] * 100
    for label, _ in arms:
        _, w, l, t, d, g = byLabel[label]
        line = _fmt(label, w, l, t, d, g)
        if label != 'OFF (no mid-game replan)':
            dWin = w / g * 100 - offWinPct
            line += f"   vs OFF: {dWin:+.2f} pts"
        print(line)
    print("\n  Each arm's 'vs OFF' = wins that variant adds beyond turning the mid-game re-plan off.")
    print("  A variant is worth keeping only if it's reliably positive (> ~2x its ± error).")
    return 0


def _multiSubjectWorker(argsTuple):
    """Run OFF / OLD / NEW on ONE subject (one app boot). Returns the subject's
    per-variant win% and the vs-OFF deltas."""
    subjectName, rounds, seed = argsTuple
    import floosball_game as fg
    from game_rules import GameRules
    app = _bootApp()
    teams = app.teamManager.teams
    subject = next(x for x in teams if x.name == subjectName)
    opponents = [x for x in teams if x is not subject]
    variants = [
        ('OFF', {'enabled': False}),
        ('OLD', {'enabled': True, 'fire_q1q2': True, 'fire_q3q4': True, 'sample_aware': False}),
        ('NEW', {'enabled': True, 'fire_q1q2': True, 'fire_q3q4': True, 'sample_aware': True}),
    ]
    out = {}
    for name, cfg in variants:
        fg._REPLAN_CONFIG.update({'enabled': True, 'fire_q1q2': True, 'fire_q3q4': True, 'sample_aware': True})
        fg._REPLAN_CONFIG.update(cfg)
        fg._random.seed(seed)
        _setCoach(subject.coach, adaptability=100)
        for o in opponents:
            _setCoach(o.coach)
        w, l, t, d, g = asyncio.run(_roundRobin(subject, opponents, rounds, GameRules()))
        out[name] = w / g * 100
    return (subjectName, out['OFF'], out['OLD'], out['NEW'],
            out['OLD'] - out['OFF'], out['NEW'] - out['OFF'])


def mainReplanMulti():
    """Average the mid-game re-plan's win effect ACROSS many subjects — the
    per-subject effect is roster-dependent and noisy, so the population mean is
    the real answer to 'does it add wins?'."""
    rounds = int(sys.argv[2]) if len(sys.argv) > 2 else 30
    procs = min(8, max(1, (os.cpu_count() or 2) - 1))
    app = _bootApp()
    teams = sorted(app.teamManager.teams, key=_teamStrength)
    # spread subjects across the league (skip the extremes where win% saturates)
    picks = [teams[int(len(teams) * p)].name for p in (0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80)]
    n = rounds * (len(teams) - 1) * 2
    print(f"MULTI-SUBJECT — {len(picks)} subjects, adaptability 100, {n} games/arm/subject.")
    print("Each subject played OFF / OLD (unconditional) / NEW (sample-aware) mid-game re-plan.\n")
    jobs = [(name, rounds, 3000 + i) for i, name in enumerate(picks)]
    with mp.Pool(processes=min(procs, len(jobs))) as pool:
        rows = pool.map(_multiSubjectWorker, jobs)
    print(f"  {'subject':<12} {'OFF':>6} {'OLD':>6} {'NEW':>6}   {'OLD-OFF':>8} {'NEW-OFF':>8}")
    oldD, newD = [], []
    for name, off, old, new, dOld, dNew in sorted(rows, key=lambda r: r[0]):
        oldD.append(dOld); newD.append(dNew)
        print(f"  {name:<12} {off:6.1f} {old:6.1f} {new:6.1f}   {dOld:+8.2f} {dNew:+8.2f}")

    def meanSe(xs):
        m = sum(xs) / len(xs)
        var = sum((x - m) ** 2 for x in xs) / (len(xs) - 1) if len(xs) > 1 else 0.0
        return m, (var / len(xs)) ** 0.5
    mOld, seOld = meanSe(oldD); mNew, seNew = meanSe(newD)
    print(f"\n  MEAN vs OFF across subjects:  OLD {mOld:+.2f} ±{seOld:.2f} pts   NEW {mNew:+.2f} ±{seNew:.2f} pts")
    print("  (mean ± standard error across subjects; reliably positive means the feature adds wins on average.)")
    return 0


async def _pointsRoundRobin(subject, opponents, rounds, rules):
    """Round-robin, returning per-game SUBJECT scoring split by half:
    (subjFirstHalf, subjSecondHalf, oppFirstHalf, oppSecondHalf). Second half
    includes OT."""
    import floosball_game as fg
    games = []
    for _ in range(rounds):
        for opp in opponents:
            for subjectHome in (True, False):
                home, away = (subject, opp) if subjectHome else (opp, subject)
                _resetTeamState(home); _resetTeamState(away)
                g = fg.Game(home, away, gameRules=rules); await g.playGame()
                hFH = g.homeScoreQ1 + g.homeScoreQ2; hSH = g.homeScoreQ3 + g.homeScoreQ4 + g.homeScoreOT
                aFH = g.awayScoreQ1 + g.awayScoreQ2; aSH = g.awayScoreQ3 + g.awayScoreQ4 + g.awayScoreOT
                if subjectHome:
                    games.append((hFH, hSH, aFH, aSH))
                else:
                    games.append((aFH, aSH, hFH, hSH))
    return games


def _pointsWorker(argsTuple):
    """One arm. `static` -> the SUBJECT's coach never re-plans (halftime + mid-game
    adaptation both suppressed for that coach only; opponents adapt normally in
    BOTH arms). Returns the per-game half-score records."""
    label, static, subjectName, rounds, seed = argsTuple
    import floosball_game as fg
    from game_rules import GameRules
    # Guard the adjust functions so ONLY a coach tagged _noAdapt is frozen — this
    # covers both the halftime call and the mid-game re-plan, which share these.
    realO, realD = fg.adjustOffensiveGameplan, fg.adjustDefensiveGameplan
    def guardO(plan, coach, stats, **kw):
        if getattr(coach, '_noAdapt', False): return
        realO(plan, coach, stats, **kw)
    def guardD(plan, coach, stats, **kw):
        if getattr(coach, '_noAdapt', False): return
        realD(plan, coach, stats, **kw)
    fg.adjustOffensiveGameplan = guardO
    fg.adjustDefensiveGameplan = guardD
    fg._random.seed(seed)
    app = _bootApp()
    teams = app.teamManager.teams
    subject = next(x for x in teams if x.name == subjectName)
    opponents = [x for x in teams if x is not subject]
    # High offensiveMind so the struggling-offense branch (quick-game shift) fires
    # at strength — it's gated on offensiveMind. Both arms get the same coach; only
    # adaptation on/off differs.
    _setCoach(subject.coach, adaptability=100, offensiveMind=100)
    subject.coach._noAdapt = bool(static)
    for o in opponents:
        _setCoach(o.coach)
        o.coach._noAdapt = False
    games = asyncio.run(_pointsRoundRobin(subject, opponents, rounds, GameRules()))
    return (label, games)


def _meanSe(xs):
    if not xs:
        return 0.0, 0.0
    m = sum(xs) / len(xs)
    if len(xs) < 2:
        return m, 0.0
    var = sum((x - m) ** 2 for x in xs) / (len(xs) - 1)
    return m, (var / len(xs)) ** 0.5


def mainPoints():
    """Does a coach that ADAPTS the gameplan mid-game outscore one that runs a
    FIXED plan? Points (continuous) is a cleaner signal than wins, and the key
    scenario — 'the plan clearly isn't working' — is testable directly as
    second-half scoring after a slow first half."""
    rounds = int(sys.argv[2]) if len(sys.argv) > 2 else 45
    subjectName, cal, nTeams = _calibrateSubject()
    print("Calibration (neutral coach, win% vs field):")
    for name, wr, strg in sorted(cal, key=lambda r: r[2]):
        print(f"  {name:<14} strength {strg:5.1f}   neutral win% {wr:5.1f}" + ('  <- subject' if name == subjectName else ''))
    n = rounds * (nTeams - 1) * 2
    print(f"\nADAPTS vs FIXED gameplan — subject '{subjectName}', adaptability 100 both arms, {n} games/arm.")
    print("STATIC = subject's plan never changes after kickoff; ADAPTS = halftime + mid-game re-plan.")
    print("Opponents adapt identically in both arms. Metric: SUBJECT points scored.\n")

    jobs = [('STATIC', True, subjectName, rounds, 7000),
            ('ADAPTS', False, subjectName, rounds, 7000)]
    with mp.Pool(processes=2) as pool:
        results = dict(pool.map(_pointsWorker, jobs))

    def report(games):
        total = [f + s for f, s, of, os_ in games]
        sh = [s for f, s, of, os_ in games]
        fh = [f for f, s, of, os_ in games]
        # Split by halftime game state. Quick-game (rhythm) should help when the
        # game is CLOSE; when behind 2+ scores the offense (correctly) presses deep.
        close = [(f, s, of, os_) for f, s, of, os_ in games if abs(f - of) <= 8]
        behind = [(f, s, of, os_) for f, s, of, os_ in games if of - f >= 9]  # 2+ scores down
        return {
            'total': _meanSe(total), 'fh': _meanSe(fh), 'sh': _meanSe(sh),
            'closeFrac': len(close) / len(games) * 100, 'closeSH': _meanSe([s for f, s, of, os_ in close]),
            'behindFrac': len(behind) / len(games) * 100, 'behindSH': _meanSe([s for f, s, of, os_ in behind]),
        }
    st = report(results['STATIC'])
    ad = report(results['ADAPTS'])

    def row(label, key, unit='pts/gm'):
        (ms, ss), (ma, sa) = st[key], ad[key]
        return f"  {label:<36} STATIC {ms:5.2f} ±{ss:.2f}   ADAPTS {ma:5.2f} ±{sa:.2f}   Δ {ma-ms:+5.2f} {unit}"

    print(row('Total points / game', 'total'))
    print(row('First-half points / game', 'fh'))
    print(row('Second-half points / game', 'sh'))
    print(f"\n  CLOSE at half (within one score — where quick-game should help; "
          f"{st['closeFrac']:.0f}% of games):")
    print(row('  2nd-half points | close at half', 'closeSH'))
    print(f"\n  Behind 2+ scores at half (catch-up mode — quick-game suppressed, "
          f"{st['behindFrac']:.0f}% of games):")
    print(row('  2nd-half points | behind 2+ at half', 'behindSH'))
    print(f"\n  Quick-game should lift 2H scoring in CLOSE games without hurting catch-up games.")
    print(f"  2H delta overall {ad['sh'][0]-st['sh'][0]:+.2f}; close {ad['closeSH'][0]-st['closeSH'][0]:+.2f}; "
          f"behind-2+ {ad['behindSH'][0]-st['behindSH'][0]:+.2f} pts/game.")
    return 0


def _passDepthWorker(argsTuple):
    """One subject: run passDepth OFF vs ON (both fully adapting, same coach, same
    seed), return per-subject total pts and close-game 2nd-half pts for each."""
    subjectName, rounds, seed = argsTuple
    import floosball_game as fg
    from game_rules import GameRules
    app = _bootApp()
    teams = app.teamManager.teams
    subject = next(x for x in teams if x.name == subjectName)
    opponents = [x for x in teams if x is not subject]

    def closeSH(games):
        xs = [s for f, s, of, os_ in games if abs(f - of) <= 8]
        return sum(xs) / len(xs) if xs else 0.0

    def totalPts(games):
        xs = [f + s for f, s, of, os_ in games]
        return sum(xs) / len(xs)

    res = {}
    for enabled in (False, True):
        fg._PASSDEPTH_ENABLED = enabled
        fg._random.seed(seed)  # same stream both arms -> paired within subject
        _setCoach(subject.coach, adaptability=100, offensiveMind=100)
        for o in opponents:
            _setCoach(o.coach)
        games = asyncio.run(_pointsRoundRobin(subject, opponents, rounds, GameRules()))
        res[enabled] = (totalPts(games), closeSH(games))
    return (subjectName, res[False][0], res[True][0], res[False][1], res[True][1])


def mainPassDepth():
    """Isolate the quick-game (passDepthBias) lever: full adaptation in both arms,
    toggling ONLY passDepth. Paired per subject (cancels subject strength), then
    averaged across subjects."""
    rounds = int(sys.argv[2]) if len(sys.argv) > 2 else 22
    procs = min(3, max(1, (os.cpu_count() or 2) - 1))  # throttled — keep machine load modest
    app = _bootApp()
    teams = sorted(app.teamManager.teams, key=_teamStrength)
    picks = [teams[int(len(teams) * p)].name for p in (0.25, 0.35, 0.45, 0.55, 0.65, 0.75)]
    n = rounds * (len(teams) - 1) * 2
    print(f"ISOLATE QUICK-GAME (passDepthBias) — {len(picks)} subjects, {n} games/arm/subject, {procs} procs.")
    print("Both arms fully adapt (adapt+offMind 100); only the pass-depth lever toggles OFF vs ON.")
    print("Δ = ON - OFF, paired within each subject (subject strength cancels).\n")
    jobs = [(name, rounds, 5000 + i) for i, name in enumerate(picks)]
    with mp.Pool(processes=procs) as pool:
        rows = pool.map(_passDepthWorker, jobs)
    print(f"  {'subject':<12} {'total OFF':>9} {'total ON':>9} {'Δtot':>6}   {'closeSH OFF':>11} {'closeSH ON':>10} {'ΔcloseSH':>8}")
    dTot, dClose = [], []
    for name, tOff, tOn, cOff, cOn in sorted(rows, key=lambda r: r[0]):
        dTot.append(tOn - tOff); dClose.append(cOn - cOff)
        print(f"  {name:<12} {tOff:9.2f} {tOn:9.2f} {tOn-tOff:+6.2f}   {cOff:11.2f} {cOn:10.2f} {cOn-cOff:+8.2f}")
    def meanSe(xs):
        m = sum(xs) / len(xs)
        var = sum((x - m) ** 2 for x in xs) / (len(xs) - 1) if len(xs) > 1 else 0.0
        return m, (var / len(xs)) ** 0.5
    mt, st_ = meanSe(dTot); mc, sc = meanSe(dClose)
    print(f"\n  MEAN Δ (ON - OFF) across subjects:  total {mt:+.2f} ±{st_:.2f}   close-game 2H {mc:+.2f} ±{sc:.2f} pts/game")
    print("  Quick-game lever is worth keeping if close-game 2H is reliably >= 0 (helps rhythm without hurting).")
    return 0


def _gameplanABWorker(argsTuple):
    """One subject with a STRONG coach: run all gameplan wiring OFF vs ON (paired,
    same seed). A good coach should gain edge vs the neutral field when its
    gameplan decisions actually reach the engine. Returns win% and avg margin for
    each arm."""
    subjectName, coachBase, rounds, seed = argsTuple
    import floosball_game as fg
    import gameplan
    from game_rules import GameRules
    app = _bootApp()
    teams = app.teamManager.teams
    subject = next(x for x in teams if x.name == subjectName)
    opponents = [x for x in teams if x is not subject]
    res = {}
    for enabled in (False, True):
        gameplan.WIRING_ENABLED = enabled  # master: offensive weight mods + defensive scheme
        fg._random.seed(seed)
        _setCoach(subject.coach, base=coachBase)  # strong coach exercises every lever
        for o in opponents:
            _setCoach(o.coach)                     # neutral 80 field
        w, l, t, d, g = asyncio.run(_roundRobin(subject, opponents, rounds, GameRules()))
        res[enabled] = (w / g * 100, d / g)
    return (subjectName, res[False][0], res[True][0], res[False][1], res[True][1])


def mainGameplanAB():
    """Combined effectiveness test: ALL gameplan wiring OFF vs ON. Subject gets a
    strong coach (all attrs high) so every wired lever fires; measures whether that
    coach gains edge vs a neutral field when the wiring is live. Paired per subject
    (strength cancels), averaged across subjects."""
    rounds = int(sys.argv[2]) if len(sys.argv) > 2 else 40
    coachBase = int(sys.argv[3]) if len(sys.argv) > 3 else 92
    procs = min(3, max(1, (os.cpu_count() or 2) - 1))  # throttled
    app = _bootApp()
    teams = sorted(app.teamManager.teams, key=_teamStrength)
    picks = [teams[int(len(teams) * p)].name for p in (0.25, 0.35, 0.45, 0.55, 0.65, 0.75)]
    n = rounds * (len(teams) - 1) * 2
    print(f"GAMEPLAN WIRING A/B — {len(picks)} subjects w/ a strong coach (all attrs {coachBase}), "
          f"{n} games/arm/subject, {procs} procs.")
    print("All gameplan wiring OFF (pre-initiative, display-only) vs ON. Field = neutral-80 coaches.")
    print("Δ = ON - OFF, paired within subject. A good coach should gain when its gameplan is wired.\n")
    jobs = [(name, coachBase, rounds, 6000 + i) for i, name in enumerate(picks)]
    with mp.Pool(processes=procs) as pool:
        rows = pool.map(_gameplanABWorker, jobs)
    print(f"  {'subject':<12} {'win% OFF':>8} {'win% ON':>8} {'Δwin':>6}   {'margin OFF':>10} {'margin ON':>9} {'Δmargin':>8}")
    dWin, dMargin = [], []
    for name, wOff, wOn, mOff, mOn in sorted(rows, key=lambda r: r[0]):
        dWin.append(wOn - wOff); dMargin.append(mOn - mOff)
        print(f"  {name:<12} {wOff:8.1f} {wOn:8.1f} {wOn-wOff:+6.1f}   {mOff:10.2f} {mOn:9.2f} {mOn-mOff:+8.2f}")
    def meanSe(xs):
        m = sum(xs) / len(xs)
        var = sum((x - m) ** 2 for x in xs) / (len(xs) - 1) if len(xs) > 1 else 0.0
        return m, (var / len(xs)) ** 0.5
    mw, sw = meanSe(dWin); mm, sm = meanSe(dMargin)
    print(f"\n  MEAN Δ (ON - OFF) across subjects:  win% {mw:+.2f} ±{sw:.2f}   margin {mm:+.2f} ±{sm:.2f} pts/game")
    print("  Positive = wiring the gameplan makes a good coach measurably more effective.")
    return 0


def main():
    rounds = int(sys.argv[1]) if len(sys.argv) > 1 else 60
    procs = min(8, max(1, (os.cpu_count() or 2) - 1))

    # --- calibrate: pick the subject whose NEUTRAL win% is closest to 50% ---
    app = _bootApp()
    teams = sorted(app.teamManager.teams, key=_teamStrength)
    # candidates spanning the middle-lower strength band (steep strength->win curve
    # means ~50% sits below the roster-rating median)
    idxs = sorted(set(int(len(teams) * p) for p in (0.15, 0.25, 0.35, 0.45, 0.55)))
    candidates = [teams[i].name for i in idxs]
    calJobs = [(name, 3) for name in candidates]
    with mp.Pool(processes=min(procs, len(calJobs))) as pool:
        cal = pool.map(_calibrateWorker, calJobs)
    cal.sort(key=lambda r: abs(r[1] - 50))
    subjectName = cal[0][0]
    print("Calibration (neutral coach, win% vs field):")
    for name, wr, strg in sorted(cal, key=lambda r: r[2]):
        mark = '  <- subject' if name == subjectName else ''
        print(f"  {name:<14} strength {strg:5.1f}   neutral win% {wr:5.1f}{mark}")

    n = rounds * (len(teams) - 1) * 2
    print(f"\nSUBJECT '{subjectName}' — round-robin vs the other {len(teams)-1} teams, home+away, {rounds}x  ({n} games/arm).")
    print("Only the SUBJECT coach changes between arms; opponent coaches pinned neutral 80.\n")

    # Common random numbers: same seed for every arm, so all arms face the SAME
    # sequence of game RNG and diverge only where the coach decides differently.
    # This is a paired comparison — far lower variance on the arm-to-arm delta.
    jobs = [(label, ov, subjectName, rounds, 4242) for label, ov in ARMS]
    with mp.Pool(processes=min(procs, len(jobs))) as pool:
        results = pool.map(_armWorker, jobs)
    byLabel = {r[0]: r for r in results}

    print("Isolate ADAPTABILITY (all other coach attrs = 80):")
    for label in ('adaptability 60', 'adaptability 80 (avg)', 'adaptability 100'):
        _, w, l, t, d, g = byLabel[label]
        print(_fmt(label, w, l, t, d, g))

    print("\nOverall coach QUALITY (all 8 attrs together):")
    for label in ('bad all-65', 'adaptability 80 (avg)', 'elite all-95'):
        _, w, l, t, d, g = byLabel[label]
        print(_fmt(label.replace('adaptability 80 (avg)', 'average all-80'), w, l, t, d, g))
    return 0


if __name__ == '__main__':
    mp.set_start_method('spawn', force=True)
    if len(sys.argv) > 1 and sys.argv[1] == 'replan':
        raise SystemExit(mainReplan())
    if len(sys.argv) > 1 and sys.argv[1] == 'replan-multi':
        raise SystemExit(mainReplanMulti())
    if len(sys.argv) > 1 and sys.argv[1] == 'points':
        raise SystemExit(mainPoints())
    if len(sys.argv) > 1 and sys.argv[1] == 'passdepth':
        raise SystemExit(mainPassDepth())
    if len(sys.argv) > 1 and sys.argv[1] == 'gameplan-ab':
        raise SystemExit(mainGameplanAB())
    raise SystemExit(main())
