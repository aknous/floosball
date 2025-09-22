"""
Floosball - Football Simulation Game (Refactored Version)

This is the main entry point for the refactored floosball application.
The original monolithic implementation has been replaced with a clean
manager-based architecture.

For backward compatibility, both the original and refactored versions
can be run from this file.
"""

import asyncio
import datetime
from logger_config import mainLogger as main_logger
from config_manager import get_config

__version__ = '0.9.0_alpha'

# Date/time utilities (still needed by some components)
dateNow = datetime.datetime.now()
dateNowUtc = datetime.datetime.now(datetime.timezone.utc)
if dateNow.day == dateNowUtc.day:
    utcOffset = dateNowUtc.hour - dateNow.hour
elif dateNowUtc.day > dateNow.day:
    utcOffset = (dateNowUtc.hour + 24) - dateNow.hour
else:
    utcOffset = dateNowUtc.hour - (dateNow.hour + 24)


# Legacy function kept for compatibility (used by some game components)
def setNewElo():
    """Initialize ELO ratings for new season"""
    # This function updates team ELO ratings at season start
    # Implementation moved to TeamManager but keeping stub for compatibility
    pass


def getPlayerTerm(tier):
    """Get contract term for player tier (legacy compatibility function)"""
    import floosball_player as FloosPlayer
    
    tier_terms = {
        FloosPlayer.PlayerTier.TierD: 1,
        FloosPlayer.PlayerTier.TierC: 2,
        FloosPlayer.PlayerTier.TierB: 3,
        FloosPlayer.PlayerTier.TierA: 3,
        FloosPlayer.PlayerTier.TierS: 4
    }
    
    return tier_terms.get(tier, 2)


def getPerformanceRating(week):
    """Calculate performance rating for given week"""
    # Simple performance calculation - could be enhanced
    base_performance = 80
    week_modifier = max(0, min(20, (week - 14) * 2))  # Peaks mid-season
    import random
    random_factor = random.uniform(-10, 10)
    
    return max(50, min(100, base_performance + week_modifier + random_factor))


# Refactored main entry point using manager architecture
async def startLeagueRefactored():
    """New refactored main entry point using the manager architecture"""
    from service_container import initializeServices, getService
    from managers.floosballApplication import FloosballApplication
    
    main_logger.info(f'Floosball v{__version__} (Refactored)')
    
    # Initialize service container
    initializeServices()
    
    # Get configuration
    config = get_config()
    
    # Add timing mode from command line if available
    import sys
    timing_mode = 'fast'  # default
    for arg in sys.argv:
        if arg.startswith('--timing='):
            timing_mode = arg.split('=')[1].lower()
        elif arg in ['--timing-scheduled', '--timing-sequential', '--timing-fast']:
            timing_mode = arg.replace('--timing-', '')
    
    # Add timing configuration to config
    config['timingMode'] = timing_mode
    
    # Create application instance - pass the service container itself
    from service_container import container
    app = FloosballApplication(container)
    
    # Initialize league system
    await app.initializeLeague(config)
    
    # Run simulation
    await app.runSimulation()
    
    main_logger.info('Refactored league simulation complete!')


# Legacy entry point (imports and runs original implementation)
async def startLeagueLegacy():
    """Original implementation entry point (for backward compatibility)"""
    main_logger.info(f'Floosball v{__version__} (Legacy)')
    main_logger.warning('Running legacy implementation - consider using --refactored flag')
    
    # Import and run the original implementation from floosball_legacy.py
    try:
        import floosball_legacy
        await floosball_legacy.startLeague()
    except ImportError:
        main_logger.error('Legacy implementation not available (floosball_legacy.py not found).')
        main_logger.info('Usage: python floosball.py --refactored [--timing=fast|sequential|scheduled]')
        return
    except Exception as e:
        main_logger.error(f'Error running legacy implementation: {e}')
        return
    
    main_logger.info('Legacy league simulation complete!')


def print_help():
    """Print usage help"""
    print(f"""
Floosball v{__version__} - Football Simulation Game

Usage:
    python floosball.py [options]

Options:
    --refactored                Use the new manager-based architecture (recommended)
    --legacy                    Use the original monolithic implementation
    
    --timing=MODE               Set timing mode (fast/sequential/scheduled)
    --timing-fast              Fast mode - no delays (default)
    --timing-sequential        Sequential mode - fixed delays between events  
    --timing-scheduled         Scheduled mode - real-time scheduling
    
    --help                     Show this help message

Timing Modes:
    fast        : No delays, instant simulation (development/testing)
    sequential  : Fixed delays between events (demos/presentations)
    scheduled   : Real-time scheduling at specific times (live simulation)

Examples:
    python floosball.py --refactored
    python floosball.py --refactored --timing=sequential
    python floosball.py --refactored --timing=scheduled
    python floosball.py --legacy

For more timing configuration options, see timing_config_examples.json
""")


if __name__ == '__main__':
    import sys
    
    # Handle help
    if '--help' in sys.argv or '-h' in sys.argv:
        print_help()
        sys.exit(0)
    
    # Determine which version to run
    if '--refactored' in sys.argv:
        # Extract timing mode info for logging
        timing_mode = 'fast'
        for arg in sys.argv:
            if arg.startswith('--timing='):
                timing_mode = arg.split('=')[1].lower()
            elif arg in ['--timing-scheduled', '--timing-sequential', '--timing-fast']:
                timing_mode = arg.replace('--timing-', '')
        
        main_logger.info(f'Starting refactored Floosball with timing mode: {timing_mode}')
        asyncio.run(startLeagueRefactored())
        
    elif '--legacy' in sys.argv:
        # Explicitly run legacy version
        asyncio.run(startLeagueLegacy())
        
    else:
        # Default behavior: recommend refactored version
        print(f"""
Floosball v{__version__}

No execution mode specified. Please choose:

  --refactored    Use new manager architecture (recommended)
  --legacy        Use original implementation
  --help          Show detailed help

Example: python floosball.py --refactored --timing=fast
""")
        sys.exit(1)