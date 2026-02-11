# Floosball Database Migration Plan

## Executive Summary
Migrate from JSON file-based storage to SQLite database for improved performance, data integrity, and query capabilities.

---

## 1. Database Architecture

### Technology Stack
- **Database**: SQLite 3
  - Reasons: Serverless, zero-config, file-based, built into Python
  - File location: `data/floosball.db`
  - Can migrate to PostgreSQL later if needed

- **ORM**: SQLAlchemy 2.0
  - Reasons: Industry standard, excellent documentation, migration support
  - Allows database-agnostic code

- **Migration Tool**: Alembic
  - Version control for database schema
  - Allows rollback if needed

### Database Design Principles
1. **Normalization**: Proper foreign keys, no data duplication
2. **Indexes**: On frequently queried fields (player.id, team.id, game.week)
3. **Relationships**: Proper one-to-many, many-to-many relationships
4. **JSON columns**: For flexible data like stats dictionaries (SQLite supports JSON)
5. **Versioning**: Track schema version for future migrations

---

## 2. Schema Design

### Core Tables

#### `players`
```sql
- id (INTEGER PRIMARY KEY)
- name (TEXT NOT NULL)
- current_number (INTEGER)
- preferred_number (INTEGER)
- tier (TEXT)  -- TierA, TierB, TierC
- team_id (INTEGER FK -> teams.id)
- position (INTEGER)  -- Enum: QB=0, RB=1, WR=2, TE=3, K=4
- seasons_played (INTEGER)
- term (INTEGER)
- term_remaining (INTEGER)
- cap_hit (INTEGER)
- player_rating (INTEGER)
- free_agent_years (INTEGER)
- service_time (TEXT)
- created_at (TIMESTAMP)
- updated_at (TIMESTAMP)
```

#### `player_attributes`
```sql
- player_id (INTEGER PRIMARY KEY FK -> players.id)
- overall_rating (INTEGER)
- speed, hands, agility, power (INTEGER)
- arm_strength, accuracy (INTEGER)
- leg_strength, skill_rating (INTEGER)
- potential_* fields (INTEGER)
- route_running, vision, blocking (INTEGER)
- discipline, attitude, focus (INTEGER)
- instinct, creativity, resilience (INTEGER)
- clutch_factor, pressure_handling (INTEGER)
- longevity, play_making_ability (INTEGER)
- x_factor (INTEGER)
- confidence_modifier, determination_modifier (INTEGER)
- luck_modifier (INTEGER)
```

#### `player_career_stats`
```sql
- player_id (INTEGER PRIMARY KEY FK -> players.id)
- season (INTEGER)
- games_played (INTEGER)
- fantasy_points (INTEGER)
- passing_stats (JSON)  -- att, comp, tds, ints, yards, etc.
- rushing_stats (JSON)  -- carries, yards, tds, fumbles, etc.
- receiving_stats (JSON)  -- targets, receptions, yards, tds, etc.
- kicking_stats (JSON)  -- fgAtt, fgs, longest, etc.
- defense_stats (JSON)  -- sacks, ints, fumRec, etc.
```

#### `teams`
```sql
- id (INTEGER PRIMARY KEY)
- name (TEXT NOT NULL)
- city (TEXT)
- abbr (TEXT UNIQUE)
- color (TEXT)
- offense_rating (INTEGER)
- defense_rating (INTEGER)
- overall_rating (INTEGER)
- league_id (INTEGER FK -> leagues.id)
- gm_score (INTEGER)
- defense_tier (INTEGER)
- created_at (TIMESTAMP)
- updated_at (TIMESTAMP)
```

#### `team_season_stats`
```sql
- id (INTEGER PRIMARY KEY AUTOINCREMENT)
- team_id (INTEGER FK -> teams.id)
- season (INTEGER)
- elo (INTEGER)
- wins, losses (INTEGER)
- win_percentage (REAL)
- streak (INTEGER)
- score_differential (INTEGER)
- made_playoffs (BOOLEAN)
- league_champion (BOOLEAN)
- floosball_champion (BOOLEAN)
- top_seed (BOOLEAN)
- offense_stats (JSON)  -- pts, yards, tds, etc.
- defense_stats (JSON)  -- sacks, ints, yards_allowed, etc.
- UNIQUE(team_id, season)
```

#### `games`
```sql
- id (INTEGER PRIMARY KEY AUTOINCREMENT)
- season (INTEGER)
- week (INTEGER)
- home_team_id (INTEGER FK -> teams.id)
- away_team_id (INTEGER FK -> teams.id)
- home_score (INTEGER)
- away_score (INTEGER)
- home_score_q1, home_score_q2, home_score_q3, home_score_q4 (INTEGER)
- home_score_ot (INTEGER)
- away_score_q1, away_score_q2, away_score_q3, away_score_q4 (INTEGER)
- away_score_ot (INTEGER)
- is_overtime (BOOLEAN)
- current_quarter (INTEGER)
- total_plays (INTEGER)
- game_date (TIMESTAMP)
- is_playoff (BOOLEAN)
- playoff_round (TEXT)  -- wildcard, divisional, conference, championship
- created_at (TIMESTAMP)
- INDEX idx_games_season_week (season, week)
- INDEX idx_games_teams (home_team_id, away_team_id)
```

#### `game_player_stats`
```sql
- id (INTEGER PRIMARY KEY AUTOINCREMENT)
- game_id (INTEGER FK -> games.id)
- player_id (INTEGER FK -> players.id)
- team_id (INTEGER FK -> teams.id)
- passing_stats (JSON)
- rushing_stats (JSON)
- receiving_stats (JSON)
- kicking_stats (JSON)
- defense_stats (JSON)
- fantasy_points (INTEGER)
- UNIQUE(game_id, player_id)
- INDEX idx_game_player_stats_game (game_id)
- INDEX idx_game_player_stats_player (player_id)
```

#### `plays`
```sql
- id (INTEGER PRIMARY KEY AUTOINCREMENT)
- game_id (INTEGER FK -> games.id)
- play_number (INTEGER)  -- Sequential within game
- quarter (INTEGER)
- time_remaining (TEXT)  -- "14:32"
- down (INTEGER)
- yards_to_first (INTEGER or TEXT)  -- 10 or "Goal"
- offense_team_id (INTEGER FK -> teams.id)
- defense_team_id (INTEGER FK -> teams.id)
- play_type (TEXT)  -- Run, Pass, FieldGoal, Punt
- play_result (TEXT)  -- FirstDown, Touchdown, etc.
- yards_gained (INTEGER)
- player_id (INTEGER FK -> players.id)  -- Primary player involved
- play_description (TEXT)
- is_score (BOOLEAN)
- is_turnover (BOOLEAN)
- is_touchdown (BOOLEAN)
- is_interception (BOOLEAN)
- is_fumble_lost (BOOLEAN)
- home_score_after (INTEGER)
- away_score_after (INTEGER)
- INDEX idx_plays_game (game_id)
```

#### `leagues`
```sql
- id (INTEGER PRIMARY KEY AUTOINCREMENT)
- name (TEXT NOT NULL)  -- "League 1", "League 2"
- created_at (TIMESTAMP)
```

#### `seasons`
```sql
- season_number (INTEGER PRIMARY KEY)
- start_date (TIMESTAMP)
- end_date (TIMESTAMP)
- current_week (INTEGER)
- playoffs_started (BOOLEAN)
- champion_team_id (INTEGER FK -> teams.id)
- created_at (TIMESTAMP)
```

#### `records`
```sql
- id (INTEGER PRIMARY KEY AUTOINCREMENT)
- record_type (TEXT)  -- "passing_yards_game", "rushing_tds_career", etc.
- category (TEXT)  -- "players", "teams"
- subcategory (TEXT)  -- "passing", "rushing", "receiving", "kicking"
- scope (TEXT)  -- "game", "season", "career"
- stat_name (TEXT)  -- "yards", "tds", "ints"
- player_id (INTEGER FK -> players.id, nullable)
- team_id (INTEGER FK -> teams.id, nullable)
- value (REAL)
- season (INTEGER, nullable)  -- For season records
- game_id (INTEGER FK -> games.id, nullable)  -- For game records
- INDEX idx_records_type (record_type)
```

#### `unused_names`
```sql
- id (INTEGER PRIMARY KEY AUTOINCREMENT)
- name (TEXT UNIQUE NOT NULL)
```

---

## 3. Migration Strategy

### Phase 1: Setup (Week 1)
**Goal**: Establish database infrastructure

1. **Install Dependencies**
   ```bash
   pip install sqlalchemy alembic
   ```

2. **Create Database Module Structure**
   ```
   database/
   ├── __init__.py
   ├── models.py          # SQLAlchemy models
   ├── connection.py      # Database connection/session
   ├── migration.py       # JSON -> DB migration scripts
   └── queries.py         # Common query helpers
   ```

3. **Setup Alembic**
   ```bash
   alembic init alembic
   ```

4. **Define SQLAlchemy Models**
   - Create all model classes
   - Define relationships
   - Add indexes

5. **Create Initial Migration**
   ```bash
   alembic revision --autogenerate -m "Initial schema"
   alembic upgrade head
   ```

### Phase 2: Data Migration (Week 1-2)
**Goal**: Migrate all existing JSON data to database

1. **Create Migration Script** (`database/migration.py`)
   - Read all JSON files
   - Transform to database records
   - Handle relationships (team_id, player_id)
   - Validate data integrity

2. **Migration Order** (to handle foreign keys):
   ```
   1. leagues
   2. teams
   3. players
   4. player_attributes
   5. player_career_stats
   6. team_season_stats
   7. games (if historical data exists)
   8. game_player_stats
   9. plays
   10. records
   11. unused_names
   ```

3. **Validation**
   - Count records (should match JSON file counts)
   - Spot-check random players/teams
   - Verify all relationships resolve
   - Check for NULL values in required fields

4. **Backup**
   - Keep all JSON files as backup
   - Don't delete until migration verified

### Phase 3: Repository Layer (Week 2)
**Goal**: Create data access layer to abstract database operations

1. **Create Repository Classes**
   ```
   database/
   └── repositories/
       ├── __init__.py
       ├── player_repository.py
       ├── team_repository.py
       ├── game_repository.py
       ├── season_repository.py
       └── record_repository.py
   ```

2. **Repository Pattern**
   - Each repository handles one entity
   - Provides CRUD operations
   - Hides SQL/ORM details
   - Returns domain objects (Player, Team, Game)

3. **Example Repository Methods**:
   ```python
   PlayerRepository:
     - get_by_id(player_id)
     - get_all()
     - get_by_team(team_id)
     - get_by_position(position)
     - save(player)
     - update_stats(player_id, stats)
   
   TeamRepository:
     - get_by_id(team_id)
     - get_all()
     - get_by_league(league_id)
     - save(team)
     - update_season_stats(team_id, season, stats)
   
   GameRepository:
     - get_by_id(game_id)
     - get_by_season_week(season, week)
     - get_by_team(team_id, season)
     - save(game)
     - save_play(game_id, play)
   ```

### Phase 4: Manager Integration (Week 2-3)
**Goal**: Replace JSON file operations with database calls

1. **Update Managers** (one at a time):
   - `playerManager.py` - Replace `readFiles()`, `saveData()`
   - `teamManager.py` - Replace team loading/saving
   - `leagueManager.py` - Use database for league data
   - `seasonManager.py` - Save games/schedules to database
   - `recordManager.py` - Use database for records

2. **Maintain Backward Compatibility**
   - Keep method signatures the same
   - Manager interfaces don't change
   - Only internal implementation changes

3. **Migration Order**:
   ```
   1. PlayerManager (most critical, heavily used)
   2. TeamManager (depends on players)
   3. LeagueManager (simple, low risk)
   4. RecordManager (independent)
   5. SeasonManager (complex, needs games)
   ```

### Phase 5: Game Data Integration (Week 3)
**Goal**: Save game results and play-by-play to database

1. **Update `Game.saveGameData()`**
   - Insert game record
   - Insert player stats for all players
   - Optionally save play-by-play (can be large)

2. **Play-by-Play Strategy**
   - **Option A**: Save all plays (full history, large DB)
   - **Option B**: Save only highlights (smaller, lose detail)
   - **Option C**: Save to separate table, archive old seasons
   - **Recommendation**: Start with Option B, upgrade to A if needed

3. **Performance Considerations**
   - Batch inserts for plays (don't insert one at a time)
   - Use transactions for game saves
   - Add indexes for common queries

### Phase 6: Testing & Validation (Week 3-4)
**Goal**: Ensure database system works correctly

1. **Unit Tests**
   - Test each repository
   - Test model relationships
   - Test data validation

2. **Integration Tests**
   - Test manager operations
   - Test full season simulation
   - Test game saving/loading

3. **Performance Tests**
   - Benchmark database queries
   - Compare to JSON file performance
   - Optimize slow queries

4. **Data Integrity Tests**
   - Verify foreign key constraints
   - Check for orphaned records
   - Validate stat calculations

### Phase 7: Deployment & Cleanup (Week 4)
**Goal**: Finalize migration and remove old code

1. **Final Migration**
   - Run migration on production data
   - Verify all data migrated correctly
   - Keep JSON backup for 1-2 weeks

2. **Remove JSON Code**
   - Remove `readFiles()` methods
   - Remove `saveData()` methods
   - Archive JSON files (don't delete immediately)

3. **Documentation**
   - Update README with database setup
   - Document schema
   - Document repository usage

---

## 4. Risk Mitigation

### Risks & Mitigation Strategies

| Risk | Impact | Mitigation |
|------|--------|------------|
| Data loss during migration | CRITICAL | Keep JSON backups, verify migration, test rollback |
| Performance degradation | MEDIUM | Benchmark, add indexes, optimize queries |
| Schema changes needed later | MEDIUM | Use Alembic migrations, plan for flexibility |
| Foreign key violations | HIGH | Validate relationships, use transactions |
| Incomplete migration | HIGH | Migration validation script, automated tests |
| Breaking existing code | HIGH | Repository pattern, maintain interfaces |

### Rollback Plan
1. Keep all JSON files until migration proven stable
2. Add feature flag: `USE_DATABASE = True/False`
3. Allow switching back to JSON if issues found
4. Keep both code paths for 1 release cycle

---

## 5. Implementation Phases - Detailed

### Phase 1.1: Database Setup
```bash
# Install dependencies
pip install sqlalchemy alembic psycopg2-binary  # psycopg2 for future PostgreSQL

# Create database directory
mkdir -p database/repositories

# Initialize Alembic
alembic init alembic
```

### Phase 1.2: Model Creation
Priority order:
1. League, Team (foundation)
2. Player, PlayerAttributes (core entities)
3. PlayerCareerStats, TeamSeasonStats (aggregates)
4. Game, GamePlayerStats (per-game data)
5. Plays (optional, can be added later)
6. Records, UnusedNames (simple lookup tables)

### Phase 2.1: Migration Script Structure
```python
# database/migration.py

class JSONToDBMigration:
    def __init__(self, db_session):
        self.session = db_session
    
    def migrate_all(self):
        """Run complete migration"""
        self.migrate_leagues()
        self.migrate_teams()
        self.migrate_players()
        self.migrate_player_attributes()
        self.migrate_player_stats()
        self.migrate_team_stats()
        self.migrate_records()
        self.migrate_unused_names()
        self.validate_migration()
    
    def validate_migration(self):
        """Verify migration completed correctly"""
        # Count checks
        # Relationship checks
        # Data integrity checks
```

### Phase 3.1: Repository Example
```python
# database/repositories/player_repository.py

class PlayerRepository:
    def __init__(self, session):
        self.session = session
    
    def get_by_id(self, player_id: int) -> Optional[Player]:
        return self.session.query(Player).filter_by(id=player_id).first()
    
    def get_all_active(self) -> List[Player]:
        return self.session.query(Player).filter(
            Player.team_id.isnot(None)
        ).all()
    
    def save(self, player: Player) -> Player:
        self.session.add(player)
        self.session.commit()
        return player
```

---

## 6. Success Criteria

✅ **Migration Complete When**:
1. All JSON data migrated to database
2. All managers using database instead of JSON
3. All tests passing
4. No performance regression
5. No data loss or corruption
6. Documentation updated

✅ **Performance Targets**:
- Player lookup: < 10ms
- Team lookup: < 5ms
- Game save: < 100ms
- Season simulation: No slower than current

✅ **Quality Targets**:
- 100% data migrated
- 0 foreign key violations
- 0 NULL values in required fields
- All existing functionality works

---

## 7. Future Enhancements (Post-Migration)

Once database is established, we can add:

1. **Advanced Queries**
   - Player career progression analysis
   - Team performance trends
   - Historical matchup statistics
   - League-wide statistics

2. **New Features**
   - Player trade history
   - Team draft history
   - Injury tracking
   - Contract management
   - Hall of Fame tracking

3. **Performance Optimizations**
   - Materialized views for common queries
   - Caching layer (Redis)
   - Read replicas for analytics

4. **Analytics**
   - Win probability models
   - Player value metrics
   - Team strength of schedule
   - Playoff probability calculators

---

## 8. Timeline Summary

| Phase | Duration | Deliverables |
|-------|----------|--------------|
| 1. Setup | 2-3 days | Database schema, models, migrations |
| 2. Migration | 3-4 days | All data in database, validated |
| 3. Repository | 2-3 days | Data access layer complete |
| 4. Manager Integration | 5-7 days | All managers using database |
| 5. Game Integration | 2-3 days | Games saving to database |
| 6. Testing | 3-5 days | All tests passing |
| 7. Deployment | 1-2 days | Production ready |
| **TOTAL** | **3-4 weeks** | Complete migration |

---

## 9. Next Steps

To begin implementation:

1. ✅ Review and approve this plan
2. 🔄 Create `database/` directory structure
3. 🔄 Define SQLAlchemy models
4. 🔄 Create initial Alembic migration
5. 🔄 Write migration script
6. 🔄 Run migration on test data
7. 🔄 Build repository layer
8. 🔄 Update first manager (PlayerManager)
9. 🔄 Iterate through remaining managers

---

## Questions to Decide

1. **Play-by-Play Storage**: Save all plays or just highlights?
2. **Historical Games**: Migrate past season games or start fresh?
3. **Schema Version**: How to handle future schema changes?
4. **Backup Strategy**: How often to backup database?
5. **Read Performance**: Do we need caching layer?

---

*Document Version: 1.0*  
*Last Updated: 2026-02-11*  
*Author: Migration Planning Team*
