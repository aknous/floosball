"""
Floosball API Server Entry Point

This script initializes the FloosballApplication and runs the API server
using the modern api/main.py implementation.

Usage:
    python run_api.py [--timing=MODE] [--fresh]
    python run_api.py [--fast|--slow|--turbo|--scheduled|--demo] [--fresh]

Timing Modes:
    --fast, --timing=fast           Fast mode - no delays (default)
    --turbo, --timing=turbo         Turbo mode - no in-game delays, pauses between games/weeks
    --slow, --timing=slow           Slow mode - fixed delays between all events
    --sequential, --timing=sequential   Same as slow mode
    --scheduled, --timing=scheduled     Real-time scheduling
    --demo, --timing=demo           Demo mode - fast games, visible offseason pick delays (UI testing)
    --test-scheduled                Compressed scheduled mode - real polling, minutes apart (no WS broadcast)
    --playoff-test                  Fast regular season + compressed scheduled playoffs (with broadcasting)
    --offseason-test                Fast regular season (no broadcast), interactive offseason (3 min FA window, live draft)
    --catchup, --timing=catchup     Backdate season to last Monday, catch up missed games, then switch to scheduled

Options:
    --fresh                         Clear database and start fresh
    --schedule-gap=N                Seconds between rounds in test-scheduled/playoff-test mode (default 60)

Production (Fly.io):
    TIMING_MODE env var             Set in fly.toml [env] (default: catchup)
    /data/.fresh flag file          Touch before deploy for one-shot fresh start:
                                      fly ssh console -C "touch /data/.fresh"
                                      fly deploy
                                    File is auto-deleted on boot — next restart is normal.

Examples:
    python run_api.py --fast
    python run_api.py --turbo --fresh
    python run_api.py --slow
    python run_api.py --fresh --fast
    python run_api.py --demo --fresh
    python run_api.py --fresh --test-scheduled
    python run_api.py --fresh --test-scheduled --schedule-gap=10
    python run_api.py --fresh --playoff-test --schedule-gap=45
"""

import os
import sys
import asyncio
import uvicorn
from dotenv import load_dotenv
from logger_config import get_logger

load_dotenv()  # Load .env file if present
from service_container import ServiceContainer
from managers.floosballApplication import FloosballApplication
from managers.timingManager import TimingMode
from api.main import app, set_floosball_app
from api.game_broadcaster import broadcaster
from api.websocket_manager import manager as ws_manager
from database.connection import init_db, clear_db

logger = get_logger("floosball.api_server")


def _resolveTimingMode(modeStr: str) -> TimingMode:
    """Resolve a timing mode string to a TimingMode enum value."""
    modeStr = modeStr.lower().strip()
    modeMap = {
        'fast': TimingMode.FAST,
        'turbo': TimingMode.TURBO,
        'sequential': TimingMode.SEQUENTIAL,
        'slow': TimingMode.SEQUENTIAL,
        'scheduled': TimingMode.SCHEDULED,
        'demo': TimingMode.DEMO,
        'test-scheduled': TimingMode.TEST_SCHEDULED,
        'playoff-test': TimingMode.PLAYOFF_TEST,
        'offseason-test': TimingMode.OFFSEASON_TEST,
        'catchup': TimingMode.CATCHUP,
        'catch-up': TimingMode.CATCHUP,
        'fast-catchup': TimingMode.FAST_CATCHUP,
        'fast_catchup': TimingMode.FAST_CATCHUP,
    }
    return modeMap.get(modeStr, TimingMode.FAST)


def parse_args():
    """Parse command line arguments, with env var fallbacks for production."""
    # Start with env var defaults (for containerized deployment)
    envTiming = os.environ.get('TIMING_MODE', 'fast')
    envFresh = os.environ.get('FRESH_START', '').lower() in ('1', 'true', 'yes')
    envGap = int(os.environ.get('SCHEDULE_GAP', '60'))

    # Flag file on persistent volume — one-shot fresh start that self-clears
    freshFlagPath = os.path.join(os.environ.get('DATABASE_DIR', 'data'), '.fresh')
    if os.path.exists(freshFlagPath):
        logger.info(f"Fresh start flag file found at {freshFlagPath} — enabling fresh start")
        envFresh = True
        os.remove(freshFlagPath)
        logger.info("Flag file removed — next restart will boot normally")

    args = {
        'timing_mode': _resolveTimingMode(envTiming),
        'fresh_start': envFresh,
        'schedule_gap': envGap,
    }

    # CLI args override env vars
    for arg in sys.argv[1:]:
        if arg.startswith('--timing='):
            mode_str = arg.split('=')[1].lower()
            if mode_str == 'fast':
                args['timing_mode'] = TimingMode.FAST
            elif mode_str == 'turbo':
                args['timing_mode'] = TimingMode.TURBO
            elif mode_str in ['sequential', 'slow']:
                args['timing_mode'] = TimingMode.SEQUENTIAL
            elif mode_str == 'scheduled':
                args['timing_mode'] = TimingMode.SCHEDULED
            elif mode_str == 'demo':
                args['timing_mode'] = TimingMode.DEMO
            elif mode_str == 'test-scheduled':
                args['timing_mode'] = TimingMode.TEST_SCHEDULED
            elif mode_str == 'playoff-test':
                args['timing_mode'] = TimingMode.PLAYOFF_TEST
            elif mode_str == 'offseason-test':
                args['timing_mode'] = TimingMode.OFFSEASON_TEST
            elif mode_str in ('catchup', 'catch-up'):
                args['timing_mode'] = TimingMode.CATCHUP
            elif mode_str in ('fast-catchup', 'fast_catchup'):
                args['timing_mode'] = TimingMode.FAST_CATCHUP
        elif arg in ['--timing-fast', '--fast']:
            args['timing_mode'] = TimingMode.FAST
        elif arg in ['--timing-turbo', '--turbo']:
            args['timing_mode'] = TimingMode.TURBO
        elif arg in ['--timing-sequential', '--slow', '--sequential']:
            args['timing_mode'] = TimingMode.SEQUENTIAL
        elif arg in ['--timing-scheduled', '--scheduled']:
            args['timing_mode'] = TimingMode.SCHEDULED
        elif arg in ['--timing-demo', '--demo']:
            args['timing_mode'] = TimingMode.DEMO
        elif arg in ['--test-scheduled']:
            args['timing_mode'] = TimingMode.TEST_SCHEDULED
        elif arg in ['--playoff-test']:
            args['timing_mode'] = TimingMode.PLAYOFF_TEST
        elif arg in ['--offseason-test']:
            args['timing_mode'] = TimingMode.OFFSEASON_TEST
        elif arg in ['--catchup', '--catch-up']:
            args['timing_mode'] = TimingMode.CATCHUP
        elif arg == '--fast-catchup':
            args['timing_mode'] = TimingMode.FAST_CATCHUP
        elif arg == '--fresh':
            args['fresh_start'] = True
        elif arg.startswith('--schedule-gap='):
            args['schedule_gap'] = int(arg.split('=')[1])

    return args


async def initialize_application(timing_mode: TimingMode, fresh_start: bool, schedule_gap: int = 60):
    """Initialize the Floosball application"""
    logger.info("Initializing Floosball Application...")
    
    # Initialize or clear database based on fresh flag
    if fresh_start:
        logger.info("Fresh start requested - clearing database")
        clear_db()
    else:
        init_db()
    
    # Use global service container (has game_state and config_manager registered)
    from service_container import container as service_container
    from config_manager import get_config
    
    # Get configuration
    config = get_config()
    
    # Add timing configuration to config
    config['timingMode'] = timing_mode.value
    config['scheduleGap'] = schedule_gap

    # Create application (timing will be set via TimingManager in container)
    floosball_app = FloosballApplication(service_container)

    # Initialize league system (this handles fresh start via force_fresh)
    await floosball_app.initializeLeague(config, force_fresh=fresh_start)

    # Set reference in API
    set_floosball_app(floosball_app)

    # Enable broadcasting (skip in test-scheduled mode)
    if timing_mode not in (TimingMode.TEST_SCHEDULED, TimingMode.OFFSEASON_TEST):
        broadcaster.enable(ws_manager)
        logger.info("Game broadcasting enabled")
    else:
        logger.info(f"{timing_mode.value} mode: broadcasting disabled at startup")
    
    # Start the application in background
    asyncio.create_task(floosball_app.runSimulation())
    
    logger.info("FloosballApplication initialized successfully")
    return floosball_app


async def run_server():
    """Run the API server"""
    args = parse_args()
    
    logger.info("="*60)
    logger.info("Floosball API Server")
    logger.info("="*60)
    logger.info(f"Timing Mode: {args['timing_mode'].name}")
    logger.info(f"Fresh Start: {args['fresh_start']}")
    logger.info("="*60)
    
    # Initialize application
    floosball_app = await initialize_application(
        args['timing_mode'],
        args['fresh_start'],
        args['schedule_gap']
    )
    
    # Configure uvicorn
    port = int(os.environ.get('PORT', '8000'))
    config = uvicorn.Config(
        app,
        host="0.0.0.0",
        port=port,
        log_level="info",
        access_log=True
    )

    server = uvicorn.Server(config)

    logger.info(f"Starting API server on http://0.0.0.0:{port}")
    logger.info(f"API documentation: http://localhost:{port}/docs")
    logger.info("WebSocket endpoints:")
    logger.info("  - ws://localhost:8000/ws/game/{game_id}")
    logger.info("  - ws://localhost:8000/ws/season")
    logger.info("  - ws://localhost:8000/ws/standings")
    logger.info("="*60)
    
    await server.serve()


if __name__ == "__main__":
    try:
        asyncio.run(run_server())
    except KeyboardInterrupt:
        logger.info("\nShutting down API server...")
        sys.exit(0)
