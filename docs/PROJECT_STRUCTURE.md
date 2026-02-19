# Floosball Project Structure

## Directory Organization

```
floosball/
├── floosball.py                 # Main entry point
├── service_container.py         # Dependency injection container
├── stat_tracker.py              # Statistics tracking
│
├── Game Models (root level)     # Core game object models
│   ├── floosball_player.py      # Player class and logic
│   ├── floosball_team.py        # Team class and logic
│   ├── floosball_game.py        # Game class and logic
│   └── floosball_methods.py     # Game methods and utilities
│
├── Configuration & Utils        # Configuration and utilities
│   ├── config_manager.py        # Configuration management
│   ├── constants.py             # Game constants
│   ├── exceptions.py            # Custom exceptions
│   ├── logger_config.py         # Logging configuration
│   ├── rating_cache.py          # Rating calculations
│   ├── player_development.py    # Player progression
│   ├── stats_optimization.py    # Statistics optimization
│   └── random_batch.py          # Batch randomization
│
├── API & Validation             # API and data validation
│   ├── floosball_api.py         # API endpoints
│   ├── api_response_builders.py # Response formatters
│   ├── attribute_validator.py   # Attribute validation
│   ├── validators.py            # Data validators
│   └── serializers.py           # Data serializers
│
├── managers/                    # Business logic managers
│   ├── __init__.py
│   ├── playerManager.py         # Player lifecycle management
│   ├── teamManager.py           # Team management
│   ├── leagueManager.py         # League structure
│   ├── seasonManager.py         # Season management
│   ├── recordManager.py         # Records tracking
│   ├── timingManager.py         # Game timing
│   └── floosballApplication.py  # Application orchestration
│
├── database/                    # Database layer
│   ├── __init__.py
│   ├── models.py                # SQLAlchemy ORM models
│   ├── connection.py            # Database connection
│   ├── config.py                # Database configuration
│   └── repositories/            # Data access layer
│       ├── __init__.py
│       ├── player_repository.py
│       ├── team_repository.py
│       └── league_repository.py
│
├── tests/                       # Test files
│   ├── __init__.py
│   ├── test_helpers.py          # Test utilities
│   ├── test_player_manager_db.py
│   ├── test_team_manager_db.py
│   ├── test_database_integration.py
│   ├── test_passing_system.py
│   ├── test_running_system.py
│   ├── test_clock_system.py
│   └── ... (other tests)
│
├── examples/                    # Example code and demos
│   ├── __init__.py
│   ├── api_examples.py          # API usage examples
│   └── relationship_demo.py     # SQLAlchemy relationships demo
│
├── docs/                        # Documentation
│   ├── DATABASE_MIGRATION_PLAN.md
│   ├── REFACTORING_RECOMMENDATIONS.md
│   ├── GAME_MECHANICS_AUDIT.md
│   └── ... (other documentation)
│
├── legacy/                      # Legacy code (deprecated)
│   ├── floosball_old.py
│   └── floosball_legacy.py
│
├── data/                        # Data files
│   ├── floosball.db             # SQLite database
│   ├── config.json              # Game configuration
│   ├── timing_config_examples.json
│   ├── playerData/              # Player JSON files (legacy)
│   └── teamData/                # Team JSON files (legacy)
│
├── logs/                        # Log files
│   └── floosball.log.*
│
└── alembic/                     # Database migrations
    ├── env.py
    ├── alembic.ini
    └── versions/                # Migration files
```

## Key Organizational Principles

1. **Root Level**: Main entry point and core game models stay at root for easy imports
2. **tests/**: All test files organized in one directory
3. **examples/**: Demo and example code separate from main codebase  
4. **docs/**: All markdown documentation in one place
5. **managers/**: Business logic layer isolated
6. **database/**: Data persistence layer with repositories
7. **legacy/**: Old/deprecated code kept separate

## Running Tests

```bash
# Run a specific test
python tests/test_team_manager_db.py

# Run all tests with pytest
pytest tests/

# Run examples
python examples/api_examples.py
python examples/relationship_demo.py
```

## Benefits of This Structure

✅ **Clean Root**: Only essential files (floosball.py, service_container.py, stat_tracker.py)  
✅ **Organized Tests**: All tests in `tests/` directory  
✅ **Clear Documentation**: All docs in `docs/` directory  
✅ **Easy Examples**: Example code in `examples/` directory  
✅ **Preserved Imports**: Game models at root level keep existing imports working  
✅ **Isolated Legacy**: Old code in `legacy/` directory out of the way


## Import Conventions

With the new structure, imports should follow these patterns:

### Core Models
```python
from core.models.floosball_player import Player
from core.models.floosball_team import Team
from core.models.floosball_game import Game
```

### Core Utils
```python
from core.utils.constants import POSITION_NAMES, QB, RB, WR
from core.utils.exceptions import ValidationError
from core.utils.logger_config import setup_logger
```

### Managers
```python
from managers.playerManager import PlayerManager
from managers.teamManager import TeamManager
from managers.leagueManager import LeagueManager
```

### Database
```python
from database.models import Player as DBPlayer, Team as DBTeam
from database.connection import get_session
from database.repositories.player_repository import PlayerRepository
```

### API
```python
from api.floosball_api import FloosballAPI
from api.api_response_builders import build_team_response
```

## Running the Application

```bash
# Run main game
python floosball.py --refactored

# Run tests
python -m pytest tests/

# Run specific test
python tests/test_player_manager_db.py

# Run examples
python examples/api_examples.py
python examples/relationship_demo.py
```

## Development Workflow

1. **Core Logic**: Modify files in `core/` for game rules and objects
2. **Business Logic**: Update `managers/` for high-level operations
3. **Data Access**: Change `database/` for persistence layer
4. **API**: Edit `api/` for external interfaces
5. **Configuration**: Adjust `config/` for game mechanics tuning

## Testing

All tests are in `tests/` directory:
- `test_*_db.py` - Database integration tests
- `test_*_system.py` - System/feature tests
- `test_*_integration.py` - Integration tests

## Documentation

All markdown documentation is in `docs/`:
- Planning documents (DATABASE_MIGRATION_PLAN.md, etc.)
- Architecture decisions (ADVANCED_ARCHITECTURE_PATTERNS.md)
- Game mechanics (GAME_MECHANICS_AUDIT.md)
- Refactoring notes (REFACTORING_*.md)
