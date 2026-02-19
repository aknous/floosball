import re

scores = []
pass_yards = []
rush_yards = []
total_yards = []
turnovers = []
sacks = []
field_goals = []
total_plays = []
shutouts = 0
total_games = 0

with open('logs/game_stats_season_1.txt', 'r') as f:
    lines = f.readlines()
    
    i = 0
    while i < len(lines):
        if "FINAL SCORE:" in lines[i]:
            # Parse score
            match = re.search(r'FINAL SCORE: \w+ (\d+) - \w+ (\d+)', lines[i])
            if match:
                total_games += 1
                score1, score2 = int(match.group(1)), int(match.group(2))
                scores.extend([score1, score2])
                
                if score1 == 0 or score2 == 0:
                    shutouts += 1
                
                # Find stats section
                for j in range(i, min(i+30, len(lines))):
                    if "Total Plays" in lines[j]:
                        parts = lines[j].split()
                        total_plays.extend([int(parts[-2]), int(parts[-1])])
                    elif "Turnovers" in lines[j]:
                        parts = lines[j].split()
                        turnovers.extend([int(parts[-2]), int(parts[-1])])
                    elif "Pass Yards" in lines[j]:
                        parts = lines[j].split()
                        pass_yards.extend([int(parts[-2]), int(parts[-1])])
                    elif "Rush Yards" in lines[j]:
                        parts = lines[j].split()
                        rush_yards.extend([int(parts[-2]), int(parts[-1])])
                    elif "Total Yards" in lines[j]:
                        parts = lines[j].split()
                        total_yards.extend([int(parts[-2]), int(parts[-1])])
                    elif "Field Goals" in lines[j]:
                        parts = lines[j].split()
                        field_goals.extend([int(parts[-2]), int(parts[-1])])
                    elif "Sacks" in lines[j]:
                        parts = lines[j].split()
                        sacks.extend([int(parts[-2]), int(parts[-1])])
        i += 1

print(f"=== SEASON 1 STATISTICS ANALYSIS ===\n")
print(f"Total Games: {total_games}")
print(f"Total Team Performances: {len(scores)}\n")

print(f"SCORING:")
print(f"  Average Points Per Team: {sum(scores)/len(scores):.1f}")
print(f"  Average Points Per Game: {sum(scores)/total_games:.1f}")
print(f"  Shutouts: {shutouts} of {total_games} ({shutouts/total_games*100:.1f}%)")
print(f"  Score Distribution:")
print(f"    0 pts: {scores.count(0)} ({scores.count(0)/len(scores)*100:.1f}%)")
print(f"    1-7 pts: {sum(1 for s in scores if 1 <= s <= 7)} ({sum(1 for s in scores if 1 <= s <= 7)/len(scores)*100:.1f}%)")
print(f"    8-14 pts: {sum(1 for s in scores if 8 <= s <= 14)} ({sum(1 for s in scores if 8 <= s <= 14)/len(scores)*100:.1f}%)")
print(f"    15-21 pts: {sum(1 for s in scores if 15 <= s <= 21)} ({sum(1 for s in scores if 15 <= s <= 21)/len(scores)*100:.1f}%)")
print(f"    22-28 pts: {sum(1 for s in scores if 22 <= s <= 28)} ({sum(1 for s in scores if 22 <= s <= 28)/len(scores)*100:.1f}%)")
print(f"    29+ pts: {sum(1 for s in scores if s >= 29)} ({sum(1 for s in scores if s >= 29)/len(scores)*100:.1f}%)")
print(f"  Highest Score: {max(scores)}")
print(f"  Lowest Score: {min(scores)}\n")

print(f"OFFENSE:")
print(f"  Avg Total Yards: {sum(total_yards)/len(total_yards):.1f}")
print(f"  Avg Pass Yards: {sum(pass_yards)/len(pass_yards):.1f}")
print(f"  Avg Rush Yards: {sum(rush_yards)/len(rush_yards):.1f}")
print(f"  Avg Total Plays: {sum(total_plays)/len(total_plays):.1f}")
print(f"  Avg Yards/Play: {sum(total_yards)/sum(total_plays):.2f}\n")

print(f"DEFENSE:")
print(f"  Avg Turnovers Per Team: {sum(turnovers)/len(turnovers):.2f}")
print(f"  Avg Sacks Per Team: {sum(sacks)/len(sacks):.2f}")
print(f"  Games with 0 sacks: {sacks.count(0)}")
print(f"  Games with 1-2 sacks: {sum(1 for s in sacks if 1 <= s <= 2)}")
print(f"  Games with 3-4 sacks: {sum(1 for s in sacks if 3 <= s <= 4)}")
print(f"  Games with 5+ sacks: {sum(1 for s in sacks if s >= 5)}\n")

print(f"FIELD GOALS:")
print(f"  Avg FGs Per Team: {sum(field_goals)/len(field_goals):.2f}")
print(f"  Teams with 0 FGs: {field_goals.count(0)} ({field_goals.count(0)/len(field_goals)*100:.1f}%)")
print(f"  Teams with 1+ FGs: {sum(1 for fg in field_goals if fg > 0)} ({sum(1 for fg in field_goals if fg > 0)/len(field_goals)*100:.1f}%)")

# Compare to NFL averages (for reference)
print(f"\n=== COMPARISON TO NFL AVERAGES ===")
print(f"NFL Avg Points/Team: ~22-23")
print(f"Your Avg Points/Team: {sum(scores)/len(scores):.1f}")
print(f"\nNFL Avg Yards/Game: ~340-350")
print(f"Your Avg Yards/Game: {sum(total_yards)/len(total_yards):.1f}")
print(f"\nNFL Avg Yards/Play: ~5.5-5.8")
print(f"Your Avg Yards/Play: {sum(total_yards)/sum(total_plays):.2f}")
print(f"\nNFL Shutout Rate: ~1-2%")
print(f"Your Shutout Rate: {shutouts/total_games*100:.1f}%")
