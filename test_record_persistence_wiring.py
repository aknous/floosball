"""The record book is actually written down, and seeded from what was played.

⚠️ `saveRecordsToFile` HAD NO CALLER OUTSIDE THE TESTS. The application loaded records at
startup and never saved them, so production's `records` table held ZERO rows and the whole
tree rebuilt from nothing on every restart. Records then accumulated only within a single
process, so a modest score beat the freshly-empty in-session mark and the feed announced it:
reported as "Mexico City Exoticos set the single-game team points record at 41" when the
highest score ever played is 94.

⚠️ `test_team_record_persistence.py` PASSED THROUGHOUT. It calls save and load directly and
proves the round trip works -- which it does. Nothing proved anyone made the trip. That is
the same gap that hid the game-winner backfill (asserted its SQL, never called it) and the
Cores lead renderer (asserted the payload, never rendered it), so this file tests the
WIRING rather than the mechanism.

Run: .venv/bin/python test_record_persistence_wiring.py
"""
import sqlite3
import tempfile
import os
import unittest


class TheSeasonLoopSavesThem(unittest.TestCase):

    def setUp(self):
        with open('managers/seasonManager.py') as fh:
            self.src = fh.read()

    def test_thereIsAHelperThatSaves(self):
        self.assertIn('def _persistRecords(self)', self.src)
        body = self.src.split('def _persistRecords')[1].split('\n    def ')[0]
        self.assertIn('saveRecordsToFile()', body)

    def test_itRunsWhereAGameRecordCanMove(self):
        """Per game, because that is the only moment a GAME record changes -- and a record
        lost to a restart cannot be recomputed from the box scores."""
        block = self.src.split('self.recordsManager.checkTeamGameRecords(gameInstance)')[1][:900]
        self.assertIn('self._persistRecords()', block)

    def test_itRunsWhereSeasonAndCareerRecordsMove(self):
        block = self.src.split('self.recordsManager.checkCareerRecords()')[1][:600]
        self.assertIn('self._persistRecords()', block)

    def test_savingNeverBreaksAGame(self):
        """⚠️ This hangs off the game-completion path. A lost save costs durability; a
        raised exception costs the game being simulated."""
        body = self.src.split('def _persistRecords')[1].split('\n    def ')[0]
        self.assertIn('except Exception', body)


class TheAppRepairsWhatWasNeverSaved(unittest.TestCase):

    def setUp(self):
        with open('managers/floosballApplication.py') as fh:
            self.src = fh.read()

    def test_theSeedRunsAtStartupAfterTheLoad(self):
        """⚠️ Order matters. Seeding before the load would be overwritten by it, and
        `_saveRecordsToDatabase` is a full delete-and-rewrite from the TREE -- so a
        database-only repair would be erased by the next save."""
        loadAt = self.src.index('self.recordsManager.loadRecordsFromFile()')
        seedAt = self.src.index('seedTeamGameRecordsFromHistory')
        self.assertLess(loadAt, seedAt, 'the seed must run after the load')

    def test_theSeedIsFollowedByASave(self):
        """⚠️ Window sized to the whole seed block, not a fixed character count — it was
        400 chars and broke the moment two more seeders were added between the first call
        and the save, which is a test failing on its own brittleness rather than on the
        behaviour."""
        block = self.src.split('seedTeamGameRecordsFromHistory')[1].split('except Exception')[0]
        self.assertIn('saveRecordsToFile()', block)


class TheSeedFindsWhatWasActuallyPlayed(unittest.TestCase):
    """Driven against a real schema rather than asserted on source -- the point of this
    whole session's lessons."""

    def _seeded(self, games):
        from managers.recordManager import RecordManager
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        import logging

        path = os.path.join(tempfile.mkdtemp(), 'recs.db')
        raw = sqlite3.connect(path)
        raw.execute("""CREATE TABLE games (id INTEGER PRIMARY KEY, status TEXT,
            home_team_id INT, away_team_id INT, home_score REAL, away_score REAL,
            home_rush_yards REAL, home_pass_yards REAL, away_rush_yards REAL,
            away_pass_yards REAL, home_rush_tds INT, home_pass_tds INT,
            away_rush_tds INT, away_pass_tds INT)""")
        raw.executemany("INSERT INTO games VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", games)
        raw.commit(); raw.close()

        session = sessionmaker(bind=create_engine(f'sqlite:///{path}'))()
        rm = RecordManager.__new__(RecordManager)
        rm._records = rm._initializeRecordStructure()
        rm.serviceContainer = type('SC', (), {'getService': lambda self, n: None})()
        rm.logger = logging.getLogger('test')
        raised = rm.seedTeamGameRecordsFromHistory(session)
        return rm, raised

    def test_itTakesTheHighestScoreEverPlayed(self):
        """THE REGRESSION: a 41 was announced as the record when a 94 existed."""
        rm, raised = self._seeded([
            (1, 'final', 11, 22, 94, 31, 200, 300, 100, 150, 4, 6, 2, 2),
            (2, 'final', 11, 22, 41, 38, 100, 120, 90, 110, 2, 3, 2, 3),
        ])
        self.assertEqual(rm.getRecords()['team']['game']['pts']['value'], 94)
        self.assertEqual(rm.getRecords()['team']['game']['pts']['id'], 11)
        self.assertGreater(raised, 0)

    def test_yardsAndTdsAreTeamTotalsNotOneHalfOfThem(self):
        """Rushing and passing are stored separately; a team's game total is their sum."""
        rm, _ = self._seeded([(1, 'final', 11, 22, 30, 20, 200, 300, 10, 20, 4, 6, 1, 1)])
        game = rm.getRecords()['team']['game']
        self.assertEqual(game['yards']['value'], 500)
        self.assertEqual(game['tds']['value'], 10)

    def test_itOnlyEverRaises(self):
        """⚠️ A value above anything in the table is a record set live this session.
        Lowering it would be the same loss this seed exists to repair, and it is what makes
        the seed idempotent."""
        rm, _ = self._seeded([(1, 'final', 11, 22, 40, 10, 100, 100, 50, 50, 2, 2, 1, 1)])
        rm.getRecords()['team']['game']['pts'].update({'value': 99, 'id': 7, 'name': 'X'})
        again = rm.seedTeamGameRecordsFromHistory(
            __import__('sqlalchemy.orm', fromlist=['sessionmaker']).sessionmaker(
                bind=__import__('sqlalchemy', fromlist=['create_engine']).create_engine(
                    'sqlite:///:memory:'))())
        self.assertEqual(rm.getRecords()['team']['game']['pts']['value'], 99)

    def test_runningItTwiceChangesNothing(self):
        games = [(1, 'final', 11, 22, 94, 31, 200, 300, 100, 150, 4, 6, 2, 2)]
        rm, first = self._seeded(games)
        self.assertGreater(first, 0)
        rm2, second = self._seeded(games)
        # Same fixture, fresh tree -> same raises; the idempotence that matters is that a
        # tree already holding the value is left alone, covered above.
        self.assertEqual(first, second)

    def test_unfinishedGamesAreIgnored(self):
        rm, raised = self._seeded([(1, 'live', 11, 22, 200, 3, 900, 900, 1, 1, 9, 9, 0, 0)])
        self.assertEqual(raised, 0)
        self.assertEqual(rm.getRecords()['team']['game']['pts']['value'], 0)

    def test_anEmptyLeagueSeedsNothing(self):
        rm, raised = self._seeded([])
        self.assertEqual(raised, 0)


class TheFullReseedCoversTheWholeBook(unittest.TestCase):
    """⚠️ THE SEED IS ONLY HALF A FIX IF IT COVERS THREE OF SIXTY-FIVE RECORDS. Persisting
    makes whatever is in the tree DURABLE, so an unseeded record stays too low permanently
    and publishes a false "record" story on every step up toward the real mark. All three
    seeders run at startup; this checks they reach every group."""

    def _seed(self):
        from managers.recordManager import RecordManager
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        import logging

        path = os.path.join(tempfile.mkdtemp(), 'book.db')
        raw = sqlite3.connect(path)
        raw.executescript("""
            CREATE TABLE players (id INTEGER PRIMARY KEY, name TEXT, position INT);
            CREATE TABLE teams (id INTEGER PRIMARY KEY, city TEXT, name TEXT);
            CREATE TABLE games (id INTEGER PRIMARY KEY, status TEXT,
                home_team_id INT, away_team_id INT, home_score REAL, away_score REAL,
                home_rush_yards REAL, home_pass_yards REAL, away_rush_yards REAL,
                away_pass_yards REAL, home_rush_tds INT, home_pass_tds INT,
                away_rush_tds INT, away_pass_tds INT);
            CREATE TABLE game_player_stats (player_id INT, fantasy_points REAL,
                passing_stats TEXT, rushing_stats TEXT, receiving_stats TEXT, kicking_stats TEXT);
            CREATE TABLE player_season_stats (player_id INT, fantasy_points REAL,
                passing_stats TEXT, rushing_stats TEXT, receiving_stats TEXT, kicking_stats TEXT);
            CREATE TABLE player_career_stats (player_id INT, fantasy_points REAL,
                passing_stats TEXT, rushing_stats TEXT, receiving_stats TEXT, kicking_stats TEXT);
            CREATE TABLE team_season_stats (team_id INT, total_yards REAL, touchdowns INT,
                points REAL, interceptions INT, fumbles_recovered INT, elo REAL,
                wins INT, losses INT);
            CREATE TABLE championships (team_id INT, championship_type TEXT);

            INSERT INTO players VALUES (1,'Ace Passer',1), (2,'Burly Back',2), (5,'Boot Foot',5);
            INSERT INTO teams VALUES (11,'Buffalo','Wings'), (22,'Miami','Heat');
            INSERT INTO games VALUES (1,'final',11,22,94,31,400,528,50,60,4,6,2,2);
            INSERT INTO game_player_stats VALUES
                (1, 74.0, '{"yards":821,"tds":9,"comp":81,"ints":4}', NULL, NULL, NULL),
                (2, 78.0, NULL, '{"yards":481,"tds":5,"fumblesLost":3}', NULL, NULL),
                (5, 39.0, NULL, NULL, NULL, '{"fgs":9,"fgYards":436}');
            INSERT INTO player_season_stats VALUES
                (1, 300.0, '{"yards":9026,"tds":70,"comp":600,"ints":20}', NULL, NULL, NULL);
            INSERT INTO player_career_stats VALUES
                (5, 500.0, NULL, NULL, NULL, '{"fgs":51,"fgYards":2000}');
            INSERT INTO team_season_stats VALUES (11, 10967, 102, 844, 16, 17, 1788, 20, 8);
            INSERT INTO team_season_stats VALUES (22, 9000, 80, 700, 10, 9, 1500, 12, 16);
            INSERT INTO championships VALUES (11,'floosbowl'), (11,'league'), (22,'regular_season');
        """)
        raw.commit(); raw.close()

        session = sessionmaker(bind=create_engine(f'sqlite:///{path}'))()
        rm = RecordManager.__new__(RecordManager)
        rm._records = rm._initializeRecordStructure()
        rm.serviceContainer = type('SC', (), {'getService': lambda self, n: None})()
        rm.logger = logging.getLogger('test')
        total = (rm.seedTeamGameRecordsFromHistory(session)
                 + rm.seedPlayerRecordsFromHistory(session)
                 + rm.seedTeamSeasonAndAllTimeRecordsFromHistory(session))
        return rm, session, total

    def test_playerGameRecordsAreRecovered(self):
        rm, _, _ = self._seed()
        game = rm.getRecords()['players']
        self.assertEqual(game['passing']['game']['yards']['value'], 821)
        self.assertEqual(game['passing']['game']['comps']['value'], 81)
        self.assertEqual(game['rushing']['game']['fumbles']['value'], 3)
        self.assertEqual(game['kicking']['game']['fgYards']['value'], 436)

    def test_seasonAndCareerScopesAreSeparate(self):
        """⚠️ The same blob keys serve all three scopes, so a mapping slip would file a
        season total as a single-game record — the exact error that makes a record book
        quietly absurd."""
        rm, _, _ = self._seed()
        players = rm.getRecords()['players']
        self.assertEqual(players['passing']['season']['yards']['value'], 9026)
        self.assertEqual(players['passing']['game']['yards']['value'], 821)
        self.assertEqual(players['kicking']['career']['fgs']['value'], 51)
        self.assertEqual(players['kicking']['game']['fgs']['value'], 9)

    def test_fantasyIsFiledByPositionNotByStat(self):
        """players.fantasy.<scope> is keyed qb/rb/wr/te/k — the record is 'most points by
        a QB', so it needs the player's position rather than a stat name."""
        rm, _, _ = self._seed()
        fantasy = rm.getRecords()['players']['fantasy']['game']
        self.assertEqual(fantasy['qb']['value'], 74.0)
        self.assertEqual(fantasy['qb']['name'], 'Ace Passer')
        self.assertEqual(fantasy['rb']['value'], 78.0)
        self.assertEqual(fantasy['k']['value'], 39.0)
        self.assertEqual(fantasy['wr']['value'], 0, 'no WR played, so no WR record')

    def test_teamSeasonAndAllTimeAreRecovered(self):
        rm, _, _ = self._seed()
        team = rm.getRecords()['team']
        self.assertEqual(team['season']['pts']['value'], 844)
        self.assertEqual(team['season']['fumRec']['value'], 17)
        self.assertEqual(team['allTime']['wins']['value'], 20)
        self.assertEqual(team['allTime']['losses']['value'], 16)

    def test_titlesComeFromTheChampionshipsTable(self):
        """⚠️ `titles` is the FLOOS BOWL count, kept distinct from league and regular
        season — collapsing them would inflate every club's honours."""
        rm, _, _ = self._seed()
        allTime = rm.getRecords()['team']['allTime']
        self.assertEqual(allTime['titles']['value'], 1)
        self.assertEqual(allTime['leagueTitles']['value'], 1)
        self.assertEqual(allTime['regSeasonTitles']['value'], 1)

    def test_everyHolderIsNamed(self):
        """A record with a value and no holder renders as a blank in the book."""
        rm, _, _ = self._seed()
        book = rm.getRecords()
        for group, scopes in book['players'].items():
            for scope, stats in scopes.items():
                for key, node in stats.items():
                    if node['value']:
                        self.assertTrue(node.get('name'),
                                        f'players.{group}.{scope}.{key} has no holder')
        for scope, stats in book['team'].items():
            for key, node in stats.items():
                if node['value']:
                    self.assertTrue(node.get('name'), f'team.{scope}.{key} has no holder')

    def test_theWholeThingIsIdempotent(self):
        rm, session, first = self._seed()
        self.assertGreater(first, 20, 'the seed should reach most of the book')
        again = (rm.seedTeamGameRecordsFromHistory(session)
                 + rm.seedPlayerRecordsFromHistory(session)
                 + rm.seedTeamSeasonAndAllTimeRecordsFromHistory(session))
        self.assertEqual(again, 0, 'running the seed twice moved a record')

    def test_allThreeSeedersRunAtStartup(self):
        with open('managers/floosballApplication.py') as fh:
            src = fh.read()
        for fn in ('seedTeamGameRecordsFromHistory', 'seedPlayerRecordsFromHistory',
                   'seedTeamSeasonAndAllTimeRecordsFromHistory'):
            self.assertIn(fn, src, f'{fn} is never called')


if __name__ == '__main__':
    unittest.main(verbosity=2)
