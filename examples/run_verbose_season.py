#!/usr/bin/env python3
"""Run a single season with verbose play-by-play logging for first 10 games"""

import asyncio
import sys
import os

# Just run the normal simulation - it will automatically log verbose for first 10 games
os.system("python3 floosball.py --refactored --timing=fast --fresh")

print("\n" + "=" * 80)
print("Season complete! Check logs/ directory for:")
print("  - game_stats_season_1.txt (summary stats)")  
print("  - play_by_play_season_1_game_*.txt (detailed play-by-play)")
print("=" * 80)

