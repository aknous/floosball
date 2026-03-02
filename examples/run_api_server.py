"""
Run Floosball API Server with Game Broadcasting
Demonstrates how to start the API with the refactored manager system
"""

import asyncio
import uvicorn
from service_container import ServiceContainer
from managers.floosballApplication import FloosballApplication
from api.main import app, set_floosball_app
from api import websocket_manager, broadcaster
from config_manager import loadConfigJson
from logger_config import get_logger

logger = get_logger("floosball.api_server")


async def initialize_application(force_fresh: bool = False):
    """Initialize the FloosballApplication"""
    logger.info("Initializing Floosball application...")
    
    # Create service container
    service_container = ServiceContainer()
    
    # Create and initialize application
    floosball_app = FloosballApplication(service_container)
    
    # Load configuration
    config = loadConfigJson()
    
    # Initialize league system
    await floosball_app.initializeLeague(config, force_fresh=force_fresh)
    
    # Set the app reference in the API
    set_floosball_app(floosball_app)
    
    # Enable game broadcasting for real-time updates
    broadcaster.enable(websocket_manager)
    logger.info("Game broadcasting ENABLED")
    
    logger.info("Application initialized successfully!")
    
    return floosball_app


async def start_season_simulation(floosball_app: FloosballApplication):
    """Start simulating the season in the background"""
    logger.info("Starting season simulation...")
    
    try:
        # Start season (this runs in background)
        await floosball_app.startSeason()
        
        logger.info("Season simulation started!")
    
    except Exception as e:
        logger.error(f"Error during season simulation: {e}")
        import traceback
        traceback.print_exc()


def run_api_server(host: str = "0.0.0.0", port: int = 8000, fresh: bool = False, simulate: bool = False):
    """
    Run the Floosball API server
    
    Args:
        host: Host to bind to (default: 0.0.0.0 for all interfaces)
        port: Port to bind to (default: 8000)
        fresh: Start with fresh database (default: False)
        simulate: Automatically start season simulation (default: False)
    """
    
    async def startup():
        """Startup tasks"""
        logger.info(f"Starting Floosball API server on {host}:{port}")
        
        # Initialize application
        floosball_app = await initialize_application(force_fresh=fresh)
        
        # Optionally start simulation
        if simulate:
            # Run simulation in background
            asyncio.create_task(start_season_simulation(floosball_app))
        else:
            logger.info("Season simulation NOT started (use --simulate flag to auto-start)")
            logger.info("You can start simulation manually through the API or application")
    
    # Register startup handler
    @app.on_event("startup")
    async def on_startup():
        await startup()
    
    # Run the server
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info"
    )


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Run Floosball API Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind to (default: 8000)")
    parser.add_argument("--fresh", action="store_true", help="Start with fresh database")
    parser.add_argument("--simulate", action="store_true", help="Automatically start season simulation")
    
    args = parser.parse_args()
    
    print("=" * 80)
    print("Floosball API Server")
    print("=" * 80)
    print(f"\nConfiguration:")
    print(f"  Host: {args.host}")
    print(f"  Port: {args.port}")
    print(f"  Fresh DB: {args.fresh}")
    print(f"  Auto-simulate: {args.simulate}")
    print(f"\nEndpoints:")
    print(f"  REST API: http://{args.host if args.host != '0.0.0.0' else 'localhost'}:{args.port}/docs")
    print(f"  Health: http://{args.host if args.host != '0.0.0.0' else 'localhost'}:{args.port}/health")
    print(f"  WebSocket: ws://{args.host if args.host != '0.0.0.0' else 'localhost'}:{args.port}/ws/game/<id>")
    print("=" * 80)
    print()
    
    run_api_server(
        host=args.host,
        port=args.port,
        fresh=args.fresh,
        simulate=args.simulate
    )
