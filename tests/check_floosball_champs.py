#!/usr/bin/env python3
from database import get_session
from database.models import Team

session = get_session()
teams = session.query(Team).all()

print('=' * 70)
print('FLOOSBOWL CHAMPIONSHIP CHECK')
print('=' * 70)

floosball_champs = [t for t in teams if t.floosbowl_championships]
print(f'\nTeams with Floosbowl Championships: {len(floosball_champs)}')

if floosball_champs:
    for team in floosball_champs:
        print(f'   ✅ {team.name}: {team.floosbowl_championships}')
else:
    print('   ❌ None found')
    # Check if attribute exists
    sample = teams[0]
    print(f'\n   Checking team structure on {sample.name}:')
    print(f'      Has floosbowl_championships: {hasattr(sample, "floosbowl_championships")}')
    if hasattr(sample, 'floosbowl_championships'):
        print(f'      Value: {sample.floosbowl_championships}')

print('\n' + '=' * 70)
print('For comparison - League Championships (finalists):')
league_champs = [t for t in teams if t.league_championships]
print(f'Teams with League Championships: {len(league_champs)}')
for team in sorted(league_champs, key=lambda t: len(t.league_championships), reverse=True)[:5]:
    print(f'   {team.name}: {len(team.league_championships)} - {team.league_championships}')

session.close()
