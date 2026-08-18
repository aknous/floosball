"""Tying a record is a different event from setting one, and the league could not say so.

⚠️ EVERY COMPARISON IN `recordManager` IS A STRICT `>`. A player who EQUALS the standing
mark therefore changes nothing: the records tree is byte-identical before and after, so the
before/after diff that finds breaks is blind to a tie by construction, and no feed item ever
fired. Measured on the production database, three game records are ALREADY shared and none
of the co-holders was ever mentioned anywhere:

    pass TDs        9  — 2 players
    rush TDs        5  — 2 players
    receiving TDs   6  — 3 players

while every yardage record is held outright. That is the expected shape: ties collect on
low-count scoring stats and essentially never on yardage.

⚠️ THE DETECTOR DOES NOT INSTRUMENT THE COMPARISON SITES. There are dozens of them across
five methods, and the break diff is deliberately generic so a record type added later cannot
silently skip the feed; instrumenting for ties would reintroduce exactly that risk. Instead
the REAL check methods are re-run over a scratch copy of the tree whose marks have each been
nudged down by an epsilon, so a stat that merely equals a record now clears the bar and
writes itself in. Equal on the way out = tied; higher = broken, and belongs to the diff.

⚠️ Owner call: NEWS ONLY. The Record Book still credits the original holder alone, so the
feed line is the only place a co-holder is named. The book answers "what is the record"; the
feed answers "what just happened".

Run: .venv/bin/python test_record_ties.py
"""
import copy
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from managers.recordManager import RecordManager


# ── A minimal league: one service container, real RecordManager ──────────────────

def mkPlayer(pid, name, passing=None, rushing=None, receiving=None):
    """A player whose stat dict is built from the CANONICAL template.

    ⚠️ Not hand-written. `_checkFantasyGameRecords` and friends read keys well outside the
    three groups this test cares about (`fantasyPoints` is top-level, for one), so a
    hand-rolled dict raises KeyError from inside the real check — and it would go stale
    again the moment a new stat group is added. `playerStatsDict` is the template the app
    itself merges defaults from.
    """
    import copy as _copy
    import floosball_player as _fp

    stats = _copy.deepcopy(_fp.playerStatsDict)
    stats['passing'].update(passing or {})
    stats['rushing'].update(rushing or {})
    stats['receiving'].update(receiving or {})
    # A real Position, because the fantasy check branches on it.
    return SimpleNamespace(id=pid, name=name, position=_fp.Position.QB,
                           gameStatsDict=stats)


class _Container:
    def __init__(self, players):
        self._players = players

    def getService(self, name):
        if name == 'player_manager':
            return SimpleNamespace(activePlayers=self._players, getPlayerById=lambda i: None)
        return None


def recordsWith(passYards=400, passTds=6):
    """A tree holding one standing passing record, set by player 1."""
    rm = RecordManager(_Container([]))
    tree = rm._initializeRecordStructure()
    game = tree['players']['passing']['game']
    game['yards'].update({'value': passYards, 'name': 'Vance Rodrigo', 'id': 1})
    game['tds'].update({'value': passTds, 'name': 'Vance Rodrigo', 'id': 1})
    return tree


class _Season:
    """The two `seasonManager` methods under test, lifted onto a stand-in so the test does
    not have to boot a league. They are taken from the real class, not reimplemented."""

    def __init__(self, rm, tree):
        from managers.seasonManager import SeasonManager
        self.recordsManager = rm
        self._tree = tree
        self._snapshotRecords = SeasonManager._snapshotRecords.__get__(self)
        self._detectRecordTies = SeasonManager._detectRecordTies.__get__(self)
        self._recordNode = SeasonManager._recordNode.__get__(self)
        self._TIE_EPSILON = SeasonManager._TIE_EPSILON


def run(players, tree, isRegularSeason=True):
    """Play out the real sequence: snapshot, run the real checks, detect ties."""
    rm = RecordManager(_Container(players))
    rm.setRecords(tree)
    season = _Season(rm, tree)
    before = season._snapshotRecords()
    game = SimpleNamespace(isRegularSeasonGame=isRegularSeason)
    rm.checkPlayerGameRecords()          # the real update pass
    with patch.object(RecordManager, 'checkTeamGameRecords'):   # needs a full Game object
        ties = season._detectRecordTies(game, before)
    return before, season._snapshotRecords(), ties


PATH = 'players.passing.game.yards'


class ATieIsDetected(unittest.TestCase):

    def test_matchingTheMarkIsReportedAsATie(self):
        """THE REGRESSION. 400 against a standing 400 changed nothing and said nothing."""
        _, after, ties = run([mkPlayer(2, 'Locust Clambake',
                                       passing={'att': 30, 'yards': 400})], recordsWith())
        self.assertIn(PATH, ties)
        value, name, holderId, prevName, _ = ties[PATH]
        self.assertEqual((value, name, holderId, prevName),
                         (400, 'Locust Clambake', 2, 'Vance Rodrigo'))

    def test_theTieLeavesTheRecordItselfUntouched(self):
        """⚠️ Owner call: news only. The original holder keeps the Record Book entry, so
        the detector must observe without changing anything."""
        before, after, _ = run([mkPlayer(2, 'Locust Clambake',
                                         passing={'att': 30, 'yards': 400})], recordsWith())
        self.assertEqual(after[PATH], before[PATH])
        self.assertEqual(after[PATH][1], 'Vance Rodrigo')

    def test_aBreakIsNotReportedAsATie(self):
        """A break already has its own story; reporting it twice would double-publish."""
        before, after, ties = run([mkPlayer(2, 'Locust Clambake',
                                            passing={'att': 30, 'yards': 401})], recordsWith())
        self.assertNotIn(PATH, ties)
        self.assertEqual(after[PATH][0], 401, 'the break should still have landed')

    def test_missingTheMarkIsNothing(self):
        _, _, ties = run([mkPlayer(2, 'Locust Clambake',
                                   passing={'att': 30, 'yards': 399})], recordsWith())
        self.assertEqual(ties, {})

    def test_theHolderReAchievingTheirOwnMarkIsNotNews(self):
        """⚠️ They already hold it. Reporting this would fire every time a record holder
        had another big day at exactly their own number."""
        _, _, ties = run([mkPlayer(1, 'Vance Rodrigo',
                                   passing={'att': 30, 'yards': 400})], recordsWith())
        self.assertEqual(ties, {})

    def test_anUnsetRecordIsNotTied(self):
        """⚠️ Every record starts at 0. Without this a fresh league would report a tie on
        every record nobody has set — the same trap the break path guards with `previous`."""
        tree = recordsWith()
        tree['players']['passing']['game']['yards'].update(
            {'value': 0, 'name': None, 'id': 0})
        _, _, ties = run([mkPlayer(2, 'Locust Clambake',
                                   passing={'att': 1, 'yards': 0})], tree)
        self.assertNotIn(PATH, ties)

    def test_aTieOnOneRecordDoesNotInventOneOnAnother(self):
        """The scratch pass nudges EVERY mark down at once, so an untouched record must
        come back untied rather than looking like it was matched."""
        _, _, ties = run([mkPlayer(2, 'Locust Clambake',
                                   passing={'att': 30, 'yards': 400, 'tds': 2})],
                         recordsWith())
        self.assertIn(PATH, ties)
        self.assertNotIn('players.passing.game.tds', ties)

    def test_twoRecordsCanBeTiedAtOnce(self):
        _, _, ties = run([mkPlayer(2, 'Locust Clambake',
                                   passing={'att': 30, 'yards': 400, 'tds': 6})],
                         recordsWith())
        self.assertIn(PATH, ties)
        self.assertIn('players.passing.game.tds', ties)


class TheScratchPassIsHarmless(unittest.TestCase):
    """⚠️ The detector re-runs the real check methods. That is only safe because they are
    pure with respect to the dict handed to them — if one ever grows a DB write or mutates
    a player, the second pass starts double-applying it."""

    def test_theCheckMethodsDoNotTouchThePlayer(self):
        player = mkPlayer(2, 'Locust Clambake', passing={'att': 30, 'yards': 400})
        snapshot = copy.deepcopy(player.gameStatsDict)
        run([player], recordsWith())
        self.assertEqual(player.gameStatsDict, snapshot,
                         'a check method mutated the player it was measuring')

    def test_theLiveTreeIsUnchangedByDetection(self):
        """The scratch copy must be a copy. Nudging the LIVE tree would lower every record
        in the league by an epsilon on every game."""
        rm = RecordManager(_Container([]))
        tree = recordsWith()
        rm.setRecords(tree)
        season = _Season(rm, tree)
        before = season._snapshotRecords()
        game = SimpleNamespace(isRegularSeasonGame=True)
        with patch.object(RecordManager, 'checkTeamGameRecords'):
            season._detectRecordTies(game, before)
        self.assertEqual(season._snapshotRecords(), before)


class TheFeedActuallyGetsALine(unittest.TestCase):
    """⚠️ END TO END, through the real `_publishGameNewsInner`. The detector working is not
    the same thing as the reader seeing a line -- this codebase has been bitten more than
    once by a correct engine change that never reached the surface that renders it."""

    def _publish(self, playerStats, standing=400):
        from managers.seasonManager import SeasonManager

        players = [mkPlayer(2, 'Locust Clambake', passing=playerStats)]
        rm = RecordManager(_Container(players))
        tree = recordsWith(passYards=standing)
        rm.setRecords(tree)

        sm = _Season(rm, tree)
        for name in ('_publishGameNewsInner', '_recordLabel', '_recordScope', '_leadWeight'):
            setattr(sm, name, getattr(SeasonManager, name).__get__(sm))
        for name in ('RECORD_SCOPE_WEIGHT', 'RECORD_SCOPES', 'RECORD_STATS',
                     'RECORD_GROUPS', 'LEAD_WEIGHT_REFERENCE'):
            setattr(sm, name, getattr(SeasonManager, name))
        sm.currentSeason = SimpleNamespace(seasonNumber=1, currentWeek=12)
        sm.db_session = None

        before = sm._snapshotRecords()
        rm.checkPlayerGameRecords()
        published = []
        game = SimpleNamespace(isRegularSeasonGame=True)
        with patch.object(RecordManager, 'checkTeamGameRecords'), \
             patch('league_news.publish', side_effect=lambda *a, **k: published.append(k)):
            sm._publishGameNewsInner(game, before)
        return published

    def test_aTiePublishesAStorySayingSo(self):
        items = [p for p in self._publish({'att': 30, 'yards': 400})
                 if p.get('category') == 'record']
        self.assertEqual(len(items), 1, f'expected exactly one record item, got {items}')
        item = items[0]
        self.assertIn('tied', item['text'])
        self.assertIn('Locust Clambake', item['text'])
        self.assertIn('400', item['text'])
        self.assertTrue(item['eventType'].endswith('.tie'),
                        'a tie needs its own event type, not the record path a break uses')

    def test_theWordingSeparatesATieFromASet(self):
        """THE WHOLE REQUEST. The two events must not read the same."""
        tie = [p for p in self._publish({'att': 30, 'yards': 400})
               if p.get('category') == 'record'][0]['text']
        broke = [p for p in self._publish({'att': 30, 'yards': 450})
                 if p.get('category') == 'record'][0]['text']
        self.assertIn('tied', tie)
        self.assertNotIn('tied', broke)
        self.assertIn('set', broke)

    def test_aTieCarriesNoBeatenByCell(self):
        """Nothing was beaten. The strip says what the mark is and whose company they just
        joined; a 'beaten by +0' cell would be a lie in a headline slot."""
        item = [p for p in self._publish({'att': 30, 'yards': 400})
                if p.get('category') == 'record'][0]
        labels = [s.get('label') for s in item['stats']]
        self.assertNotIn('BEATEN BY', labels)
        self.assertIn('MARK', labels)
        self.assertIn('SET BY', labels)

    def test_aTieCannotLead(self):
        """⚠️ Falls out rather than being special-cased: a tie's ratio is exactly 1.0, the
        floor for this category since any break is strictly greater, and with two cells it
        also sits under front_page.LEAD_MIN_STATS."""
        import front_page
        tie = [p for p in self._publish({'att': 30, 'yards': 400})
               if p.get('category') == 'record'][0]
        broke = [p for p in self._publish({'att': 30, 'yards': 450})
                 if p.get('category') == 'record'][0]
        self.assertLess(tie['leadWeight'], broke['leadWeight'])
        self.assertLess(len(tie['stats']), front_page.LEAD_MIN_STATS)
        self.assertNotIn('record', front_page.LEAD_WITHOUT_STATS)

    def test_aTieNamesThePlayerSoTheRowCanCarryTheirCrest(self):
        item = [p for p in self._publish({'att': 30, 'yards': 400})
                if p.get('category') == 'record'][0]
        self.assertEqual(item['playerId'], 2)
        self.assertEqual(item['playerName'], 'Locust Clambake')
        self.assertIsNone(item['teamId'], 'a player record fills its team in at read time')


class ItNeverBreaksAGame(unittest.TestCase):
    """⚠️ This hangs off the game-completion path. `_publishGameNews` wraps its whole body
    for exactly this reason — a news item is never worth a game."""

    def test_aBrokenRecordsManagerYieldsNoTiesRatherThanRaising(self):
        class Exploding:
            def getRecords(self):
                raise RuntimeError('boom')

        season = _Season(Exploding(), {})
        self.assertEqual(
            season._detectRecordTies(SimpleNamespace(isRegularSeasonGame=True), {}), {})


if __name__ == '__main__':
    unittest.main(verbosity=2)
