"""
Test the new game clock system by running a single game
and examining clock-related statistics
"""
import asyncio
import sys

async def test_clock_game():
    """Run multiple games and display full play-by-play with scoring/turnover markers"""
    
    # Import modules needed
    from service_container import initializeServices
    from managers.floosballApplication import FloosballApplication
    from config_manager import get_config
    
    print("="*60)
    print("GAME CLOCK & OVERTIME SYSTEM TEST")
    print("="*60)
    
    # Initialize services
    initializeServices()
    
    # Get config and set to fast timing
    config = get_config()
    config['timingMode'] = 'instant'
    config['numberOfSeasons'] = 0  # Don't run full seasons
    
    # Create application
    from service_container import container
    app = FloosballApplication(container)
    
    # Initialize league
    print("\nInitializing league system...")
    await app.initializeLeague(config, force_fresh=False)
    
    # Get team and league managers
    teamManager = container.getService('team_manager')
    leagueManager = container.getService('league_manager')
    
    # Get two teams for a test game
    teams = teamManager.teams
    if len(teams) < 2:
        print("ERROR: Not enough teams to run test game")
        return
    
    # Import game class
    import floosball_game as FloosGame
    from managers.timingManager import TimingManager, TimingMode
    
    # Run 3 games and display them all
    num_games = 3
    
    for game_num in range(num_games):
        homeTeam = teams[game_num % len(teams)]
        awayTeam = teams[(game_num + 1) % len(teams)]
        
        # Create game with fast timing (instant simulation)
        timing = TimingManager(TimingMode.FAST)
        game = FloosGame.Game(homeTeam, awayTeam, timing)
        game.isRegularSeasonGame = False
        
        # Play the game
        await game.playGame()
    
    # Print detailed results
    print(f"\n{'='*60}")
    print(f"GAME #{game_num + 1} FINAL")
    print(f"{'='*60}")
    print(f"{awayTeam.abbr}: {game.awayScore}")
    print(f"{homeTeam.abbr}: {game.homeScore}")
    print(f"\nTotal plays: {game.totalPlays}")
    print(f"Final quarter: Q{game.currentQuarter}")
    print(f"Time remaining: {game.formatTime(game.gameClockSeconds)}")
    
    print(f"\nQuarter Scores:")
    print(f"  Q1: {game.awayScoreQ1}-{game.homeScoreQ1}")
    print(f"  Q2: {game.awayScoreQ2}-{game.homeScoreQ2}")
    print(f"  Q3: {game.awayScoreQ3}-{game.homeScoreQ3}")
    print(f"  Q4: {game.awayScoreQ4}-{game.homeScoreQ4}")
    if game.isOvertime:
        print(f"  OT: {game.awayScoreOT}-{game.homeScoreOT}")
        print(f"\nOVERTIME ANALYSIS:")
        print(f"  Home had possession: {game.otHomeHadPos}")
        print(f"  Away had possession: {game.otAwayHadPos}")
        print(f"  Both teams had possession: {game.firstOtPossessionComplete}")
        print(f"  Clock remaining: {game.formatTime(game.gameClockSeconds)}")
    
    print(f"\nTimeouts Used:")
    print(f"  {homeTeam.abbr}: {3 - game.homeTimeoutsRemaining}/3")
    print(f"  {awayTeam.abbr}: {3 - game.awayTimeoutsRemaining}/3")
    
    # Show detailed play-by-play
    print(f"\n{'='*60}")
    print("DETAILED PLAY-BY-PLAY (ALL PLAYS):")
    print(f"{'='*60}")
    print(f"{'Q':<3} {'Time':<7} {'Down':<9} {'Poss':<4} {'Play Description'}")
    print(f"{'-'*110}")
    
    for i, entry in enumerate(game.gameFeed):
        if 'play' in entry:
            play = entry['play']
            quarter_str = f"Q{play.quarter}" if play.quarter != 5 else "OT"
            
            # Get possession team
            poss_team = play.offense.abbr if hasattr(play, 'offense') and play.offense else "???"
            
            # Format down and distance
            down_str = ""
            if hasattr(play, 'down') and play.down:
                down_names = {1: "1st", 2: "2nd", 3: "3rd", 4: "4th"}
                down_str = down_names.get(play.down, "")
                if hasattr(play, 'yardsTo1st') and play.yardsTo1st is not None:
                    if play.yardsTo1st == 'Goal':
                        down_str = f"{down_str} & Goal"
                    else:
                        down_str = f"{down_str} & {play.yardsTo1st}"
            
            # Check for scoring or turnover events
            marker = ""
            if hasattr(play, 'scoreChange') and play.scoreChange:
                marker = f"  *** SCORE: {game.homeTeam.abbr} {play.homeTeamScore} - {game.awayTeam.abbr} {play.awayTeamScore} ***"
            elif hasattr(play, 'isFumbleLost') and play.isFumbleLost:
                marker = "  >>> FUMBLE LOST <<<"
            elif hasattr(play, 'isInterception') and play.isInterception:
                marker = "  >>> INTERCEPTION <<<"
            
            print(f"{quarter_str:<3} {play.timeRemaining:>7} {down_str:<9} {poss_team:<4} {play.playText}")
            if marker:
                print(marker)
            
        elif 'event' in entry:
            event = entry['event']
            quarter = event.get('quarter', '?')
            time = event.get('timeRemaining', 'N/A')
            text = event['text']
            print(f"{quarter:<3} {time:>7} {'EVENT':<9} {'':<4} {text}")
    
    # Validation
    print(f"\n{'='*60}")
    print("VALIDATION:")
    print(f"{'='*60}")
    
    if game.totalPlays < 100:
        print(f"⚠️  Play count is low ({game.totalPlays}) - clock may be consuming time too quickly")
    elif game.totalPlays > 200:
        print(f"⚠️  Play count is high ({game.totalPlays}) - clock may not be consuming enough time")
    else:
        print(f"✓ Play count is realistic ({game.totalPlays} plays)")
    
    if game.gameClockSeconds == 0 or game.currentQuarter >= 4:
        print("✓ Game ended properly (clock expired or finished regulation)")
    else:
        print(f"⚠️  Game ended unexpectedly (Q{game.currentQuarter}, {game.formatTime(game.gameClockSeconds)} left)")
    
    # Check that quarters progressed
    quarters_with_scores = sum([
        1 if game.awayScoreQ1 + game.homeScoreQ1 > 0 else 0,
        1 if game.awayScoreQ2 + game.homeScoreQ2 > 0 else 0,
        1 if game.awayScoreQ3 + game.homeScoreQ3 > 0 else 0,
        1 if game.awayScoreQ4 + game.homeScoreQ4 > 0 else 0,
    ])
    
    if quarters_with_scores >= 3:
        print(f"✓ Multiple quarters played ({quarters_with_scores} quarters had scores)")
    else:
        print(f"⚠️  Few quarters played ({quarters_with_scores} quarters had scores)")
    
    print(f"\n{'='*60}")
    print("Clock System Test Complete!")
    print(f"{'='*60}\n")
    
    if game_num < num_games - 1:
        print("\n" + "="*60)
        print(f"STARTING GAME #{game_num + 2}")
        print("="*60 + "\n")

if __name__ == "__main__":
    asyncio.run(test_clock_game())
