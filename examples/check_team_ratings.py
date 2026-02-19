import json
import statistics

# Load all teams and check offensive ratings
offense_ratings = []
defense_ratings = []
for i in range(1, 11):
    try:
        with open(f'data/teamData/team{i}.json', 'r') as f:
            team = json.load(f)
            off_rating = team.get('offenseRating', 0)
            def_run = team.get('defenseRunCoverageRating', 0)
            def_pass = team.get('defensePassCoverageRating', 0)
            if off_rating > 0:
                offense_ratings.append(off_rating)
                defense_ratings.append((def_run + def_pass) / 2)
                print(f'Team {i}: Offense={off_rating}, Defense Pass={def_pass}, Defense Run={def_run}')
    except FileNotFoundError:
        break

if offense_ratings:
    print(f'\n=== Offense Rating Stats ===')
    print(f'Mean: {statistics.mean(offense_ratings):.1f}')
    print(f'Min: {min(offense_ratings)}')
    print(f'Max: {max(offense_ratings)}')
    print(f'StdDev: {statistics.stdev(offense_ratings):.1f}')
    
if defense_ratings:
    print(f'\n=== Defense Rating Stats ===')
    print(f'Mean: {statistics.mean(defense_ratings):.1f}')
    print(f'Min: {min(defense_ratings):.1f}')
    print(f'Max: {max(defense_ratings):.1f}')
    print(f'StdDev: {statistics.stdev(defense_ratings):.1f}')
