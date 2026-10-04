"""The admin can roll the next season over early (`/api/admin/season-rollover`, 2026-10-04).

Rolling over is `startNewSeason`: cards mint and the shop sells again, while games keep
their usual time. The request ends the between-season wait at its next poll. And the
shop's day-1 pack cap counts only this season's packs while the opening time is still
ahead (it used to count the whole last year, so an early rollover read "cycle limit
reached" for regular buyers until the opening time).
"""
import asyncio
import datetime as dt

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import managers.timingManager as tm
from managers.timingManager import TimingManager


def test_a_rollover_request_ends_the_between_season_wait(monkeypatch):
    t = TimingManager(tm.TimingMode.SCHEDULED)
    t.delays['daily_check'] = 0.01
    monkeypatch.setattr(TimingManager, '_nextSeasonAnchorUtc',
                        staticmethod(lambda: dt.datetime.utcnow() + dt.timedelta(days=3)))

    async def run():
        async def request():
            await asyncio.sleep(0.05)
            t.rolloverRequested = True
        asyncio.ensure_future(request())
        await asyncio.wait_for(t.waitBetweenSeasons(), timeout=2)

    asyncio.run(run())
    assert t.rolloverRequested is False, 'a used request must not carry into the next season'


def test_a_request_made_before_the_wait_rolls_over_at_once(monkeypatch):
    t = TimingManager(tm.TimingMode.SCHEDULED)
    t.delays['daily_check'] = 0.01
    monkeypatch.setattr(TimingManager, '_nextSeasonAnchorUtc',
                        staticmethod(lambda: dt.datetime.utcnow() + dt.timedelta(days=3)))
    t.rolloverRequested = True          # pressed during the offseason
    asyncio.run(asyncio.wait_for(t.waitBetweenSeasons(), timeout=1))


def _session():
    from database.models import Base
    engine = create_engine('sqlite://')
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_day_one_cap_counts_only_this_seasons_packs_before_opening():
    from database.models import Season, PackOpening, PackType
    from managers.cardManager import _countPacksThisCycle, _shopCycleStartDate
    s = _session()
    now = dt.datetime.utcnow()
    lastSeasonEnd = now - dt.timedelta(days=2)
    s.add(Season(season_number=8, start_date=now - dt.timedelta(days=9), end_date=lastSeasonEnd))
    s.add(Season(season_number=9, start_date=now + dt.timedelta(hours=8)))   # opens tonight
    s.add(PackType(id=1, name='grand', display_name='Grand', cost=70, cards_per_pack=5, cards_kept=3, rarity_weights='{}'))
    for days in (6, 5, 5, 4, 4, 3):                                          # last season's packs
        s.add(PackOpening(user_id=1, pack_type_id=1, cost=70, cards_received='[]', opened_at=now - dt.timedelta(days=days)))
    s.add(PackOpening(user_id=1, pack_type_id=1, cost=70, cards_received='[]', opened_at=now - dt.timedelta(minutes=10)))
    s.commit()
    assert _shopCycleStartDate(s, 9, 1) == lastSeasonEnd
    assert _countPacksThisCycle(s, 1, 9, 1) == 1


def test_status_reads_the_cycle(monkeypatch):
    import api.main as main

    class Season_:
        def __init__(self, n): self.seasonNumber = n

    class State:
        def __init__(self, played): self.played = played
        def getState(self, key, default=None): return self.played

    class Container:
        def __init__(self, played): self.state = State(played)
        def getService(self, name): return self.state

    class App:
        def __init__(self, current, played, offseason):
            self.serviceContainer = Container(played)
            self.seasonManager = type('SM', (), {})()
            self.seasonManager.currentSeason = current
            self.seasonManager.timingManager = TimingManager(tm.TimingMode.SCHEDULED)
            self._offseason = offseason
        def _loadSimulationState(self): return {'in_offseason': self._offseason}
        def getTimingMode(self): return 'scheduled'

    for current, played, offseason, phase in ((Season_(8), 7, True, 'offseason'),
                                              (Season_(8), 8, False, 'waiting'),
                                              (None, 8, False, 'waiting'),
                                              (Season_(9), 8, False, 'season')):
        monkeypatch.setattr(main, 'floosball_app', App(current, played, offseason))
        assert main._seasonRolloverStatus()['phase'] == phase, (current, played, offseason)
