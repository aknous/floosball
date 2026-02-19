# Floosball.py Refactoring Plan

## Current State Analysis

**File Size**: 3,234 lines  
**Functions/Classes**: 24 (massive procedural chunks between)  
**Global Variables**: 50+ scattered throughout  
**Main Issues**:
- Mixed responsibilities (records, players, teams, leagues, seasons all in one file)
- Massive global state making testing impossible
- No clear organization or separation of concerns
- Hard to find specific functionality

## Recommended Class-Based Organization

### 1. **LeagueManager** (Core League Operations)
```python
class LeagueManager:
    """Manages league structure, teams, and overall organization"""
    
    def __init__(self, service_container):
        self.service_container = service_container
        self.leagues = []
        self.teams = []
    
    def create_leagues(self, config):
        """Create league structure from config"""
        pass
    
    def add_team(self, team):
        """Add team to appropriate league"""
        pass
    
    def get_standings(self):
        """Get current league standings"""
        pass
    
    def get_league_by_name(self, name):
        """Find league by name"""
        pass
```

### 2. **PlayerManager** (Player Lifecycle Management)
```python
class PlayerManager:
    """Manages player lifecycle, lists, and organization"""
    
    def __init__(self, service_container):
        self.service_container = service_container
        self.active_players = []
        self.free_agents = []
        self.retired_players = []
        self.hall_of_fame = []
        self.rookie_draft_list = []
        
        # Position-specific lists
        self.active_qbs = []
        self.active_rbs = []
        self.active_wrs = []
        self.active_tes = []
        self.active_ks = []
    
    def generate_players(self, config):
        """Generate initial player pool"""
        pass
    
    def draft_player(self, player, team):
        """Handle player draft"""
        pass
    
    def retire_player(self, player):
        """Move player to retirement"""
        pass
    
    def promote_to_hall_of_fame(self, player):
        """Promote retired player to HoF"""
        pass
    
    def sort_players_by_position(self):
        """Organize players into position lists"""
        pass
    
    def get_free_agents_by_position(self, position):
        """Get available free agents by position"""
        pass
```

### 3. **RecordsManager** (Statistics and Records Tracking)
```python
class RecordsManager:
    """Manages game records, statistics, and achievements"""
    
    def __init__(self, service_container):
        self.service_container = service_container
        self.game_records = {}
        self.season_records = {}
        self.career_records = {}
        self.team_records = {}
    
    def check_player_game_records(self, player, game_stats):
        """Check if player set any game records"""
        pass
    
    def check_season_records(self, season):
        """Check season-end records"""
        pass
    
    def check_career_records(self, player):
        """Check career milestone records"""
        pass
    
    def check_team_game_records(self, game):
        """Check team game records"""
        pass
    
    def update_record(self, category, subcategory, player, value):
        """Update a specific record"""
        pass
    
    def get_records_by_category(self, category):
        """Get all records in a category"""
        pass
```

### 4. **SeasonManager** (Season Simulation and Management)
```python
class SeasonManager:
    """Manages season simulation, scheduling, and progression"""
    
    def __init__(self, service_container, league_manager, player_manager, records_manager):
        self.service_container = service_container
        self.league_manager = league_manager
        self.player_manager = player_manager
        self.records_manager = records_manager
        
        self.current_season = None
        self.season_history = []
        self.schedule = []
    
    async def start_new_season(self):
        """Initialize and start a new season"""
        pass
    
    async def run_season_simulation(self):
        """Run full season simulation"""
        pass
    
    async def handle_offseason(self):
        """Handle offseason activities"""
        pass
    
    def create_schedule(self):
        """Generate season schedule"""
        pass
    
    def advance_to_next_season(self):
        """Move to next season"""
        pass
    
    def get_season_stats(self):
        """Get current season statistics"""
        pass
```

### 5. **ContractManager** (Player Contracts and Salary Cap)
```python
class ContractManager:
    """Manages player contracts, salary cap, and financial aspects"""
    
    def __init__(self, service_container):
        self.service_container = service_container
        self.salary_cap = 0
        self.free_agency_order = []
        self.contract_history = {}
    
    def set_salary_cap(self, cap):
        """Set league salary cap"""
        pass
    
    def calculate_player_contract(self, player):
        """Calculate appropriate contract for player"""
        pass
    
    def handle_free_agency(self):
        """Process free agency period"""
        pass
    
    def check_cap_compliance(self, team):
        """Verify team is under salary cap"""
        pass
    
    def get_player_contract_value(self, player):
        """Get player's contract value"""
        pass
```

### 6. **FloosballApplication** (Main Application Orchestrator)
```python
class FloosballApplication:
    """Main application class that orchestrates all components"""
    
    def __init__(self):
        # Initialize service container
        from service_container import initialize_services
        initialize_services()
        
        # Initialize managers
        self.league_manager = LeagueManager(self.service_container)
        self.player_manager = PlayerManager(self.service_container)
        self.records_manager = RecordsManager(self.service_container)
        self.contract_manager = ContractManager(self.service_container)
        self.season_manager = SeasonManager(
            self.service_container,
            self.league_manager,
            self.player_manager,
            self.records_manager
        )
    
    async def initialize_league(self, config):
        """Initialize the entire league system"""
        # Load configuration
        self.load_configuration(config)
        
        # Create leagues and teams
        self.league_manager.create_leagues(config)
        
        # Generate and draft players
        self.player_manager.generate_players(config)
        await self.player_manager.conduct_initial_draft()
        
        # Set up contracts
        self.contract_manager.set_salary_cap(config['salary_cap'])
        
        # Initialize first season
        await self.season_manager.start_new_season()
    
    async def run_simulation(self):
        """Run the main league simulation"""
        seasons_to_run = self.service_container.get_game_state('totalSeasons', 0)
        seasons_played = self.service_container.get_game_state('seasonsPlayed', 0)
        
        while seasons_played < seasons_to_run:
            await self.season_manager.run_season_simulation()
            await self.season_manager.handle_offseason()
            seasons_played += 1
            self.service_container.set_game_state('seasonsPlayed', seasons_played)
    
    def get_league_state(self):
        """Get current state of the entire league"""
        return {
            'leagues': self.league_manager.leagues,
            'active_players': self.player_manager.active_players,
            'current_season': self.season_manager.current_season,
            'records': self.records_manager.get_all_records()
        }
```

## Implementation Strategy (Gradual Refactoring)

### **Phase 1: Extract Managers (Week 1-2)**
1. Create empty manager classes
2. Move global variables into appropriate managers
3. Move related functions into manager methods
4. Update imports and references

### **Phase 2: Dependency Injection (Week 3)**
1. Wire up manager dependencies 
2. Create FloosballApplication orchestrator
3. Update main entry point

### **Phase 3: Testing & Validation (Week 4)**
1. Add unit tests for each manager
2. Verify functionality is preserved
3. Performance testing

## Refactoring Benefits

### **Improved Organization**
- **Clear responsibilities**: Each manager has a specific purpose
- **Easy navigation**: Find player functionality in PlayerManager, etc.
- **Logical grouping**: Related functions are grouped together

### **Better Maintainability**
- **Smaller, focused classes**: Instead of 3,234-line monolith
- **Clear interfaces**: Well-defined methods for each responsibility
- **Easier testing**: Mock individual managers for unit tests

### **Enhanced Extensibility**
- **Plugin-friendly**: Managers can be extended or replaced
- **Event integration**: Managers can publish/subscribe to events
- **Service container integration**: Uses existing dependency injection

## File Structure After Refactoring

```
floosball/
├── floosball.py (main entry point - ~100 lines)
├── managers/
│   ├── __init__.py
│   ├── league_manager.py (~300 lines)
│   ├── player_manager.py (~400 lines)
│   ├── records_manager.py (~200 lines)
│   ├── season_manager.py (~500 lines)
│   ├── contract_manager.py (~200 lines)
│   └── floosball_application.py (~300 lines)
├── models/ (existing)
│   ├── floosball_game.py
│   ├── floosball_player.py
│   └── floosball_team.py
└── services/ (existing)
    ├── service_container.py
    ├── rating_cache.py
    └── ...
```

## Migration Path (Backward Compatibility)

To maintain backward compatibility during refactoring:

```python
# floosball.py (compatibility layer)
from managers.floosball_application import FloosballApplication

# Initialize application
_app = FloosballApplication()

# Expose global variables for backward compatibility (temporary)
def get_active_player_list():
    return _app.player_manager.active_players

def get_team_list():
    return _app.league_manager.teams

# Global variables (deprecated, will be removed)
activePlayerList = property(get_active_player_list)
teamList = property(get_team_list)
# ... other backward compatibility shims

# Main entry point
async def startLeague():
    config = FloosMethods.getConfig()
    await _app.initialize_league(config)
    await _app.run_simulation()
```

## Conclusion

This refactoring transforms a 3,234-line monolith into:
- **6 focused classes** (~300 lines each)
- **Clear separation of concerns**
- **Testable components**
- **Maintainable architecture**

The gradual approach ensures:
- **No functionality loss**
- **Backward compatibility**
- **Safe incremental progress**
- **Easy rollback if needed**

**Recommendation**: Start with Phase 1 (extracting managers) since it provides immediate organizational benefits with minimal risk.