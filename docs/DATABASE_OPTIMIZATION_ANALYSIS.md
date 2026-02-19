# Database Schema Analysis & Optimization Recommendations

## Current Issues for Website Performance

### 1. **CRITICAL: JSON Fields Block Efficient Queries**

**Problem:** Key statistics stored in JSON cannot be queried efficiently for leaderboards and rankings.

**Affected Tables:**
- `Team.all_time_stats` (JSON) - Can't query "top teams by wins" or "top teams by yards"
- `TeamSeasonStats.offense_stats` (JSON) - Can't build offensive leaderboards
- `TeamSeasonStats.defense_stats` (JSON) - Can't build defensive leaderboards
- `PlayerCareerStats.{passing,rushing,receiving,kicking,defense}_stats` (JSON)
- `GamePlayerStats.*_stats` (JSON)

**Website Impact:**
- ❌ Can't efficiently query "Top 10 teams by all-time wins"
- ❌ Can't sort teams by total yards, TDs, etc.
- ❌ Can't build player leaderboards (passing yards, rushing TDs, etc.)
- ❌ Every stat query requires loading ALL records and parsing JSON in Python

**Recommended Fix:** Denormalize frequently-queried stats into columns

---

### 2. **Missing Indexes on Common Queries**

**Current Indexes:**
- ✅ Games: season+week, home_team, away_team
- ✅ TeamSeasonStats: team_id, season
- ✅ Player: team_id, position
- ❌ Games: Missing index on is_playoff (for playoff game queries)
- ❌ TeamSeasonStats: Missing index on wins, elo (for rankings)
- ❌ Team: Missing index on league_id
- ❌ Season: Missing index on champion_team_id

**Website Impact:**
- Slower queries when filtering playoff games
- Slower leaderboard generation
- Slower team-by-league queries

---

### 3. **Championships as JSON Arrays**

**Current:**
```python
league_championships: JSON = ['Season 1', 'Season 3']
floosbowl_championships: JSON = ['Season 2']
regular_season_champions: JSON = ['Season 1', 'Season 4']
```

**Problems:**
- Can't query "which teams won championships in Season 5"
- Can't count championships efficiently in SQL
- Requires Python-side filtering

**Better Alternative:** Separate Championship table with foreign keys

---

### 4. **All-Time Stats Denormalization**

**Current:** All-time stats stored as massive JSON blob on Team table

**Better Approach:** Calculate on-the-fly from TeamSeasonStats or cache specific fields

---

## Recommended Schema Changes

### Priority 1: Add Queryable Stat Columns to TeamSeasonStats

```python
class TeamSeasonStats(Base):
    # ... existing fields ...
    
    # Offensive stats (frequently queried)
    points: Mapped[int] = mapped_column(Integer, default=0, index=True)
    touchdowns: Mapped[int] = mapped_column(Integer, default=0)
    field_goals: Mapped[int] = mapped_column(Integer, default=0)
    total_yards: Mapped[int] = mapped_column(Integer, default=0, index=True)
    passing_yards: Mapped[int] = mapped_column(Integer, default=0)
    rushing_yards: Mapped[int] = mapped_column(Integer, default=0)
    passing_tds: Mapped[int] = mapped_column(Integer, default=0)
    rushing_tds: Mapped[int] = mapped_column(Integer, default=0)
    
    # Defensive stats (frequently queried)
    points_allowed: Mapped[int] = mapped_column(Integer, default=0)
    sacks: Mapped[int] = mapped_column(Integer, default=0)
    interceptions: Mapped[int] = mapped_column(Integer, default=0)
    fumbles_recovered: Mapped[int] = mapped_column(Integer, default=0)
    total_yards_allowed: Mapped[int] = mapped_column(Integer, default=0)
    
    # Keep JSON for less-common stats
    offense_stats: Mapped[Optional[dict]] = mapped_column(JSON)
    defense_stats: Mapped[Optional[dict]] = mapped_column(JSON)
```

### Priority 2: Add All-Time Stat Columns to Team

```python
class Team(Base):
    # ... existing fields ...
    
    # All-time queryable stats
    all_time_wins: Mapped[int] = mapped_column(Integer, default=0, index=True)
    all_time_losses: Mapped[int] = mapped_column(Integer, default=0)
    all_time_points: Mapped[int] = mapped_column(Integer, default=0)
    all_time_yards: Mapped[int] = mapped_column(Integer, default=0)
    all_time_touchdowns: Mapped[int] = mapped_column(Integer, default=0)
    
    # Keep JSON for detailed breakdown
    all_time_stats: Mapped[Optional[dict]] = mapped_column(JSON)
```

### Priority 3: Create Championship Table

```python
class Championship(Base):
    """Track team championships by season and type"""
    __tablename__ = "championships"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    team_id: Mapped[int] = mapped_column(Integer, ForeignKey("teams.id"), nullable=False)
    season: Mapped[int] = mapped_column(Integer, nullable=False)
    championship_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # 'regular_season', 'league', 'floosbowl'
    
    __table_args__ = (
        UniqueConstraint("team_id", "season", "championship_type"),
        Index("idx_championships_season", "season"),
        Index("idx_championships_type", "championship_type"),
    )
```

**Benefits:**
- ✅ Query "all Floosbowl champions" with one SQL query
- ✅ Count championships per team in SQL
- ✅ Find champions by season efficiently

### Priority 4: Add Missing Indexes

```python
# Games table
Index("idx_games_is_playoff", "is_playoff")
Index("idx_games_season_playoff", "season", "is_playoff")

# TeamSeasonStats table  
Index("idx_team_stats_wins", "wins")
Index("idx_team_stats_elo", "elo")
Index("idx_team_stats_playoffs", "made_playoffs")

# Team table
Index("idx_team_league", "league_id")

# Season table
Index("idx_season_champion", "champion_team_id")
```

### Priority 5: Player Career Stats (if needed for leaderboards)

```python
class PlayerCareerStats(Base):
    # ... existing fields ...
    
    # Queryable stats for leaderboards
    passing_yards: Mapped[int] = mapped_column(Integer, default=0, index=True)
    passing_tds: Mapped[int] = mapped_column(Integer, default=0, index=True)
    rushing_yards: Mapped[int] = mapped_column(Integer, default=0, index=True)
    rushing_tds: Mapped[int] = mapped_column(Integer, default=0)
    receiving_yards: Mapped[int] = mapped_column(Integer, default=0)
    receiving_tds: Mapped[int] = mapped_column(Integer, default=0)
    
    # Keep JSON for detailed breakdown
    passing_stats: Mapped[Optional[dict]] = mapped_column(JSON)
    rushing_stats: Mapped[Optional[dict]] = mapped_column(JSON)
    receiving_stats: Mapped[Optional[dict]] = mapped_column(JSON)
```

---

## Migration Strategy

### Phase 1: Add Columns (Non-Breaking)
1. Add new stat columns to existing tables (all nullable initially)
2. Keep existing JSON columns
3. Update save logic to populate both
4. Backfill data from existing JSON

### Phase 2: Add Indexes
1. Add recommended indexes
2. Test query performance

### Phase 3: Add Championship Table
1. Create Championship table
2. Migrate data from JSON arrays
3. Keep JSON for backwards compatibility initially

### Phase 4: Switch Queries
1. Update all queries to use new columns
2. Test website performance
3. Eventually drop JSON columns (optional)

---

## Sample Queries - Before vs After

### Team Leaderboard by Wins

**Before (JSON):**
```python
teams = session.query(Team).all()
sorted_teams = sorted(teams, 
    key=lambda t: t.all_time_stats.get('wins', 0) if t.all_time_stats else 0, 
    reverse=True)[:10]
```
- Loads ALL teams
- Parses JSON for every team
- Sorts in Python
- **Performance: O(n) where n = all teams**

**After (Columns):**
```sql
SELECT * FROM teams 
ORDER BY all_time_wins DESC 
LIMIT 10;
```
- Database handles sorting
- Only returns top 10
- Uses index
- **Performance: O(log n) with index**

### Find All Floosbowl Champions

**Before (JSON):**
```python
teams = session.query(Team).all()
champions = [t for t in teams if t.floosbowl_championships]
```
- Loads ALL teams
- Parses JSON arrays
- Filters in Python

**After (Championship table):**
```sql
SELECT t.*, c.season 
FROM teams t
JOIN championships c ON t.id = c.team_id
WHERE c.championship_type = 'floosbowl'
ORDER BY c.season DESC;
```
- Single SQL query
- Indexed lookup
- Sorted by database

### Season Offensive Leaders

**Before (JSON):**
```python
stats = session.query(TeamSeasonStats).filter_by(season=5).all()
sorted_stats = sorted(stats,
    key=lambda s: s.offense_stats.get('totalYards', 0) if s.offense_stats else 0,
    reverse=True)[:10]
```

**After (Columns):**
```sql
SELECT t.name, tss.total_yards, tss.touchdowns
FROM team_season_stats tss
JOIN teams t ON tss.team_id = t.id
WHERE tss.season = 5
ORDER BY tss.total_yards DESC
LIMIT 10;
```

---

## Current Schema Strengths

✅ **Good normalization** - Players, Teams, Games properly separated
✅ **Good relationships** - Foreign keys properly defined
✅ **Some indexes** - Basic indexes on common joins
✅ **Flexible** - JSON allows storing complex nested data

## Estimated Performance Improvements

With recommended changes:
- **Team leaderboards**: 100-1000x faster (n → log n)
- **Championship queries**: 50-100x faster (full scan → indexed lookup)
- **Season stat rankings**: 50-200x faster (Python sort → SQL ORDER BY)
- **Player leaderboards**: 100-500x faster with indexes

## Storage Trade-offs

**Additional storage per denormalized field:**
- Team all-time stats: ~40 bytes per team (24 teams = 960 bytes)
- Team season stats: ~80 bytes per team-season (24 teams × seasons)
- Championship table: ~30 bytes per championship

**Total overhead for 100 seasons:** ~200KB
**Query performance gain:** 50-1000x faster

**Conclusion:** Storage cost is negligible, performance gains are massive.
