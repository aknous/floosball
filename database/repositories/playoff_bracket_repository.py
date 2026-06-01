"""Repository for the playoff bracket challenge — CRUD, stateless scoring, and
the frozen seed field. Scoring recomputes from final game results each call, so
it's idempotent and survives a mid-playoff restart."""
import json
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from database.models import PlayoffBracket, Game, Season, User
import playoff_bracket as pb


class PlayoffBracketRepository:
    def __init__(self, session: Session):
        self.session = session

    # ── Frozen seed field ────────────────────────────────────────────────
    def freezeSeeds(self, season: int, seedsDict: dict) -> None:
        """Persist the bracket field (called once when seeding locks)."""
        row = self.session.get(Season, season)
        if row is not None:
            row.playoff_seeds = json.dumps(seedsDict)
            self.session.flush()

    def getFrozenSeeds(self, season: int) -> Optional[dict]:
        row = self.session.get(Season, season)
        raw = getattr(row, 'playoff_seeds', None) if row else None
        if not raw:
            return None
        try:
            return json.loads(raw)
        except (ValueError, TypeError):
            return None

    # ── Submission lifecycle ─────────────────────────────────────────────
    def isOpen(self, season: int) -> bool:
        """Open for submission once seeds are frozen and no playoff game has
        started yet (locks at Round 1 kickoff). Stateless — derived from data."""
        if self.getFrozenSeeds(season) is None:
            return False
        started = (
            self.session.query(Game.id)
            .filter(Game.season == season,
                    Game.playoff_round.isnot(None),
                    Game.status != 'scheduled')
            .first()
        )
        return started is None

    def getUserBracket(self, userId: int, season: int) -> Optional[PlayoffBracket]:
        return (self.session.query(PlayoffBracket)
                .filter_by(user_id=userId, season=season).first())

    def submitPredictions(self, userId: int, season: int, predictions: dict) -> PlayoffBracket:
        b = self.getUserBracket(userId, season)
        if b is None:
            b = PlayoffBracket(user_id=userId, season=season,
                               predictions=json.dumps(predictions))
            self.session.add(b)
        else:
            b.predictions = json.dumps(predictions)
        self.session.flush()
        return b

    # ── Scoring ──────────────────────────────────────────────────────────
    def computeActualAdvancers(self, season: int) -> Tuple[Dict[str, List[int]], Optional[int]]:
        """From final playoff games: the winners that advanced past each round,
        keyed by round (round1 / round2 / league_championship / floosbowl), plus
        the Floos Bowl champion id."""
        games = (self.session.query(Game)
                 .filter(Game.season == season,
                         Game.playoff_round.isnot(None),
                         Game.status == 'final')
                 .all())
        advancers: Dict[str, List[int]] = {}
        championId = None
        for g in games:
            try:
                rnd = int(g.playoff_round)
            except (ValueError, TypeError):
                continue
            key = pb.ROUND_KEYS.get(rnd)
            if not key:
                continue
            winner = g.home_team_id if (g.home_score or 0) > (g.away_score or 0) else g.away_team_id
            advancers.setdefault(key, []).append(winner)
            if rnd == pb.ROUND_FLOOSBOWL:
                championId = winner
        return advancers, championId

    def getPlayoffGameResults(self, season: int) -> List[Dict]:
        """Final playoff games with scores, so the bracket UI can show the
        actual result of each matchup. The frontend keys these by the team
        pair (single-elimination, so a pair meets at most once)."""
        games = (self.session.query(Game)
                 .filter(Game.season == season,
                         Game.playoff_round.isnot(None),
                         Game.status == 'final')
                 .all())
        out: List[Dict] = []
        for g in games:
            try:
                rnd = int(g.playoff_round)
            except (ValueError, TypeError):
                continue
            out.append({
                "round": rnd,
                "homeTeamId": g.home_team_id,
                "awayTeamId": g.away_team_id,
                "homeScore": g.home_score or 0,
                "awayScore": g.away_score or 0,
            })
        return out

    def scoreAllBrackets(self, season: int) -> List[PlayoffBracket]:
        """Recompute every bracket's points from current results. Idempotent.
        Also flips `locked` on once scoring begins (playoffs have started)."""
        advancers, championId = self.computeActualAdvancers(season)
        brackets = self.session.query(PlayoffBracket).filter_by(season=season).all()
        for b in brackets:
            try:
                preds = json.loads(b.predictions or '{}')
            except (ValueError, TypeError):
                preds = {}
            res = pb.scoreBracket(preds, advancers, championId)
            b.points = res['points']
            b.correct_count = res['correctCount']
            b.locked = True
        self.session.flush()
        return brackets

    def getLeaderboard(self, season: int, limit: Optional[int] = None) -> List[PlayoffBracket]:
        q = (self.session.query(PlayoffBracket)
             .filter_by(season=season)
             .order_by(PlayoffBracket.points.desc(),
                       PlayoffBracket.correct_count.desc(),
                       PlayoffBracket.created_at.asc()))
        return q.limit(limit).all() if limit else q.all()
