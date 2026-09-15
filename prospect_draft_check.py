"""Prospect-draft harness — does the restored draft actually work end to end?

⚠️ HEADLESS ON PURPOSE, and it is not a substitute for `run_api.py --fresh` — it is the
instrument that found why that could not run at all. A fresh start died in
`startNewSeason` with `database is locked`; running the same managers with NO API server
and no second process reproduced it exactly, which is what isolated the cause to the
shared session (a zero-row bulk update holding the write lock, fixed in cf73189) rather
than to startup contention. Keeping the drive headless also means a failure here is
about the draft and never about two writers.

Runs N seasons and reports, per season:

  * the CLASS      — generated at season start, one per club, debuting below true skill
  * the DRAFT      — worst-first, pipelines filled, nobody stranded holding the flag
  * the SCOUTING   — two clubs disagreeing about the same prospect, band narrowing
  * the ORDERING   — a washout released IN TIME for that offseason's FA draft
  * the CULL       — never-rostered players removed, everyone with a record spared
  * POPULATION     — the number the cull exists to hold flat

  .venv/bin/python prospect_draft_check.py --seasons 3
"""
import argparse
import asyncio
import logging
import os
import shutil
import sys
import tempfile

tmp = tempfile.mkdtemp(prefix='floos_draft_')
os.environ['DATABASE_DIR'] = tmp
os.environ.setdefault('TIMING_MODE', 'fast')
logging.disable(logging.INFO)
# ...except the cull, whose whole finding is WHY it did or did not fire.
_CULL_LOG = logging.getLogger('floosball.playerManager')


async def boot():
    from database.connection import init_db
    from service_container import container
    from config_manager import get_config
    from managers.floosballApplication import FloosballApplication
    init_db()
    config = get_config()
    config['timingMode'] = 'fast'
    config['scheduleGap'] = 0
    app = FloosballApplication(container)
    await app.initializeLeague(config, force_fresh=True)
    return container, app


def classOf(pm):
    return [p for p in pm.activePlayers if getattr(p, 'is_upcoming_rookie', False)]


def pipelines(tm):
    return {t.name: list(getattr(t, 'prospects', []) or []) for t in tm.teams}


def rosteredRatings(tm):
    return [p.playerRating for t in tm.teams
            for p in (t.rosterDict or {}).values() if p is not None]


def report(label, ok, detail=''):
    mark = 'PASS' if ok else 'FAIL'
    print(f"  [{mark}] {label}{(' — ' + detail) if detail else ''}")
    return ok


async def main(seasons):
    container, app = await boot()
    logging.disable(logging.NOTSET)
    logging.getLogger().setLevel(logging.WARNING)
    _CULL_LOG.setLevel(logging.INFO)
    _h = logging.StreamHandler(sys.stdout)
    _h.setFormatter(logging.Formatter('        %(message)s'))
    _h.addFilter(lambda r: r.getMessage().startswith('Cull:'))
    logging.getLogger().addHandler(logging.NullHandler())
    _CULL_LOG.addHandler(_h)
    sm, pm = app.seasonManager, app.playerManager
    tm = container.getService('team_manager')
    from constants import PROSPECT_ENTRY_DISCOUNT, PROSPECT_DEVELOPMENT_WINDOW
    from managers.frontOfficeBrain import FrontOfficeBrain
    import prospect_scouting as ps

    allOk = True
    trajectory = []
    for season in range(1, seasons + 1):
        print(f"\n=== SEASON {season} " + "=" * 50)
        await sm.startNewSeason()

        # ---- the class -------------------------------------------------
        klass = classOf(pm)
        allOk &= report("class generated at season start",
                        len(klass) == len(tm.teams),
                        f"{len(klass)} rookies for {len(tm.teams)} clubs")
        if klass:
            gaps = [p.computeCeilingRating() - p.playerRating for p in klass]
            best = max(klass, key=lambda p: p.computeCeilingRating())
            # ⚠️ `min(gaps) > 0` IS TOO STRICT and fails about one class in ten.
            # `POTENTIAL_HEADROOM` is randint(0, 15), so a rookie can roll zero headroom;
            # and `applyEntryDiscount` cannot push a player below the generation floor of
            # 60, so a 60 comes out with his ceiling equal to his current rating. The
            # claim being tested is that the CLASS debuts below its ceiling, not that
            # every single member does.
            allOk &= report("rookies debut BELOW their ceiling (the entry discount)",
                            min(gaps) >= 0 and sum(gaps) / len(gaps) > 5,
                            f"headroom min {min(gaps):.0f} / mean {sum(gaps)/len(gaps):.1f} "
                            f"/ max {max(gaps):.0f}")
            print(f"        headliner: {best.name} ({best.position.name}) "
                  f"debuts {best.playerRating:.0f}, ceiling {best.computeCeilingRating()}")
            allOk &= report("nobody in the class is rostered or in the FA pool",
                            not any(r in pm.freeAgents for r in klass))

            # ---- scouting: two clubs, same prospect, different reads ----
            brain = FrontOfficeBrain(pm)
            brain.season, brain.week = season, 1
            reads = []
            for club in tm.teams[:8]:
                vision = brain.scoutingVision(getattr(club, 'coach', None), club)
                reads.append(ps.believedPotential(
                    best.computeCeilingRating(), club.id, best.id, season, vision, 1))
            allOk &= report("clubs DISAGREE about the same prospect",
                            len(set(round(r, 3) for r in reads)) > 1,
                            f"week-1 beliefs {min(reads):.0f}-{max(reads):.0f} on a "
                            f"true {best.computeCeilingRating()}")
            v = brain.scoutingVision(getattr(tm.teams[0], 'coach', None), tm.teams[0])
            early, late = ps.bandWidth(v, 1), ps.bandWidth(v, 22)
            allOk &= report("the band NARROWS toward the deadline",
                            late < early or early == 0,
                            f"±{early:.1f} in week 1 -> ±{late:.1f} at week 22")

        poolBefore = len([p for p in pm.freeAgents])
        popBefore = len(pm.activePlayers)

        # ---- play the season and the offseason -------------------------
        await sm.runSeasonSimulation()
        preDraftPipelines = sum(len(v) for v in pipelines(tm).values())
        await sm.handleOffseason()

        # ---- the draft -------------------------------------------------
        after = pipelines(tm)
        drafted = sum(len(v) for v in after.values())
        picks = [t for t in sm._offseasonTransactions if t.get('type') == 'rookie_pick']
        skips = [t for t in sm._offseasonTransactions if t.get('type') == 'rookie_skip']
        stranded = len(classOf(pm))
        allOk &= report("the class is consumed — nobody left holding the flag",
                        stranded == 0, f"{stranded} stranded")
        # ⚠️ NOT "the pipeline grew". Once pipelines reach steady state the draft adds a
        # class while promotions and washouts take one out, so growth is the wrong
        # invariant — it holds for the first few seasons and then fails on a healthy
        # league. What must be true every season is that every club picked and the
        # pipelines are actually populated.
        # ⚠️ A SKIP IS CORRECT, NOT A FAILURE. `PROSPECT_SLOT_CAP_PER_POSITION` is 2, so
        # a club that has drafted the same position three years running has nowhere to
        # put a fourth and passes. The plan calls the cap "not binding" at one round a
        # season, and mostly it is not — but it binds occasionally, and forfeiting the
        # pick is the designed behaviour. What must hold is that every club was ASKED.
        allOk &= report("every club was on the clock",
                        len(picks) + len(skips) == len(tm.teams),
                        f"{len(picks)} picks, {len(skips)} skips")
        allOk &= report("pipelines are populated",
                        drafted > 0,
                        f"{preDraftPipelines} -> {drafted} prospects league-wide")
        withProspects = sum(1 for v in after.values() if v)
        print(f"        {withProspects}/{len(tm.teams)} clubs hold at least one prospect")
        print(f"        draft: {len(picks)} picks, {len(skips)} skips, "
              f"order length {len(getattr(sm.currentSeason, 'freeAgencyOrder', []) or [])}")
        if skips:
            from collections import Counter
            print(f"        skip reasons: {Counter(t.get('player') for t in skips)}")
        undraftedToFa = [p for p in pm.freeAgents
                         if getattr(p, 'is_undrafted', False)]
        print(f"        {len(undraftedToFa)} rookies went undrafted into the FA pool")
        # ⚠️ HOW MANY WERE PROMOTED THE SAME OFFSEASON THEY WERE DRAFTED? Promotion runs
        # at step 5.75, AFTER the draft and BEFORE free agency, so a rookie who beats
        # what is left in the pool fills the hole instead of a free agent. That is the
        # documented "best player available" rule working — but it means those players
        # never spend a day in a pipeline, and the worst club has the most holes, so it
        # lands hardest on exactly the headliner the feature exists to create.
        promos = [t for t in sm._offseasonTransactions if t.get('isPromotion')]
        pickedIds = {t.get('playerId') for t in picks}
        sameYear = [t for t in promos if t.get('playerId') in pickedIds]
        if picks:
            print(f"        {len(sameYear)}/{len(picks)} draftees promoted the SAME "
                  f"offseason (never entered a pipeline)")
            if sameYear:
                rs = sorted(t.get('rating', 0) for t in sameYear)
                print(f"        promoted-at-once ratings {rs[0]:.0f}-{rs[-1]:.0f}; "
                      f"class rating range "
                      f"{min(t['rating'] for t in picks):.0f}-"
                      f"{max(t['rating'] for t in picks):.0f}")
                top3 = {t['playerId'] for t in picks[:3]}
                print(f"        of the first 3 picks, "
                      f"{len(top3 & {t.get('playerId') for t in sameYear})} went straight up")

        # ---- rosters -----------------------------------------------------
        holes = [(t.name, slot) for t in tm.teams
                 for slot, p in (t.rosterDict or {}).items() if p is None]
        allOk &= report("every roster slot is filled after the FA draft",
                        not holes, f"{len(holes)} holes" if holes else "")

        # ---- do washouts AGE in the pool? --------------------------------
        # ⚠️ The cull's grace window is measured in `freeAgentYears`, so if a
        # never-rostered player never ages, the cull can never fire however long he
        # waits. Track a named cohort across seasons rather than inferring it.
        cohort = getattr(sm, '_probeCohort', None)
        if cohort:
            alive = {getattr(p, 'id', None): getattr(p, 'freeAgentYears', None)
                     for p in pm.freeAgents if getattr(p, 'id', None) in cohort}
            gone = len(cohort) - len(alive)
            print(f"        LAST SEASON'S washout cohort ({len(cohort)}): "
                  f"{len(alive)} still pooled with freeAgentYears "
                  f"{sorted(set(alive.values()))}, {gone} gone")
        sm._probeCohort = {t.get('playerId') for t in
                           [x for x in sm._offseasonTransactions
                            if x.get('type') == 'prospect_release']}

        # ---- the ordering fix -------------------------------------------
        released = [t for t in sm._offseasonTransactions if t.get('type') == 'prospect_release']
        faPicks = [t for t in sm._offseasonTransactions if t.get('type') == 'fa_pick']
        if released:
            names = {t.get('player') for t in released}
            signedSame = names & {t.get('player') for t in faPicks}
            print(f"        {len(released)} washout(s) released; "
                  f"{len(signedSame)} signed in the SAME offseason's FA draft")

        # ---- the cull ----------------------------------------------------
        # ⚠️ WHY the cull did or did not fire. "0 removed" is indistinguishable between
        # "the pool is healthy" and "the predicate never matches anything", and those
        # need opposite responses.
        from collections import Counter
        elig = Counter()
        pooled = [p for p in pm.freeAgents
                  if not getattr(p, 'is_prospect', False)
                  and not getattr(p, 'is_upcoming_rookie', False)]
        withRecord = pm._playersWithARecord([p.id for p in pooled])
        neverPlayed = [p for p in pooled if p.id not in withRecord]
        for p in neverPlayed:
            elig[getattr(p, 'freeAgentYears', 0) or 0] += 1
        rat = rosteredRatings(tm)
        from constants import CULL_RATING_FRACTION_OF_MEAN, CULL_MIN_POOL_SEASONS
        bar = (sum(rat) / len(rat)) * CULL_RATING_FRACTION_OF_MEAN
        ripe = [p for p in neverPlayed
                if (getattr(p, 'freeAgentYears', 0) or 0) >= CULL_MIN_POOL_SEASONS]
        print(f"        pool: {len(pm.freeAgents)} total, {len(neverPlayed)} never played, "
              f"freeAgentYears {dict(sorted(elig.items()))}")
        print(f"        cull bar {bar:.1f}; {len(ripe)} past the grace window, "
              f"{sum(1 for p in ripe if p.playerRating < bar)} of those under the bar")
        culled = [t for t in sm._offseasonTransactions if t.get('type') == 'pool_cull']
        survivors = {getattr(p, 'id', None) for p in pm.activePlayers}
        culledIds = {t.get('playerId') for t in culled}
        allOk &= report("culled players are really gone",
                        not (culledIds & survivors),
                        f"{len(culled)} removed")
        prospectIds = {getattr(p, 'id', None) for v in after.values() for p in v}
        allOk &= report("⚠️ the cull did NOT eat the class it just drafted",
                        not (culledIds & prospectIds))

        pop = len(pm.activePlayers)
        rat = rosteredRatings(tm)
        fourStar = sum(1 for r in rat if r >= 84) / max(1, len(rat))
        print(f"        population {popBefore} -> {pop} "
              f"(pool {poolBefore} -> {len(pm.freeAgents)}), "
              f"rostered mean {sum(rat)/len(rat):.1f}, 4-star share {fourStar:.0%}")

        trajectory.append((season, pop, len(pm.freeAgents), fourStar, len(culled)))
        sm.currentSeason.seasonNumber = season + 1

    print("\n  season  population  pool  4-star  culled")
    for row in trajectory:
        print(f"  {row[0]:>6}  {row[1]:>10}  {row[2]:>4}  {row[3]:>5.0%}  {row[4]:>6}")
    print("\n" + ("ALL CHECKS PASSED" if allOk else "SOME CHECKS FAILED"))
    return 0 if allOk else 1


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--seasons', type=int, default=2)
    args = ap.parse_args()
    try:
        code = asyncio.run(main(args.seasons))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    sys.exit(code)
