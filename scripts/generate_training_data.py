"""
Generate synthetic play-calling situations for ML model training.

Produces three situation types (separated by 'situationType' field):
  - 'play_call'    : in-drive decisions, downs 1-4
  - 'post_td'      : extra point vs 2-point conversion
  - 'kickoff'      : normal kickoff vs onside kick

Outputs: floosball/data/coaching_situations.json
"""

import json
import random
from pathlib import Path

OUTPUT_PATH = Path(__file__).parent.parent / 'data' / 'coaching_situations.json'


# ---------------------------------------------------------------------------
# In-drive play-call situations (downs 1-4)
# ---------------------------------------------------------------------------

def randomPlayCall():
    return {
        'situationType': 'play_call',
        'down': random.randint(1, 4),
        'yardsToGo': random.randint(1, 25),
        'fieldPos': random.randint(1, 99),
        'scoreDiff': random.randint(-35, 35),
        'quarter': random.randint(1, 4),
        'clockSeconds': random.randint(0, 900),
        'ownOffenseRating': random.randint(55, 99),
        'oppDefRunRating': random.randint(55, 99),
        'oppDefPassRating': random.randint(55, 99),
        'coachAggressiveness': random.randint(60, 100),
        'coachOffensiveMind': random.randint(60, 100),
        'timeoutsLeft': random.randint(0, 3),
        'clockRunning': random.randint(0, 1),
        'kickerRating': random.randint(55, 99),
    }


def spikeSituation():
    """Trailing late, no timeouts, clock running — spike to stop it."""
    return {**randomPlayCall(),
        'situationType': 'play_call',
        'down': random.randint(1, 3),
        'fieldPos': random.randint(40, 85),
        'scoreDiff': random.randint(-8, -1),
        'quarter': 4,
        'clockSeconds': random.randint(5, 30),
        'timeoutsLeft': 0,
        'clockRunning': 1,
    }


def kneelSituation():
    """Leading late — drain the clock."""
    return {**randomPlayCall(),
        'situationType': 'play_call',
        'down': random.randint(1, 3),
        'fieldPos': random.randint(1, 50),
        'scoreDiff': random.randint(1, 28),
        'quarter': 4,
        'clockSeconds': random.randint(5, 75),
        'clockRunning': random.randint(0, 1),
    }


def callTimeoutSituation():
    """Trailing late, clock running, timeouts available."""
    return {**randomPlayCall(),
        'situationType': 'play_call',
        'down': random.randint(1, 3),
        'fieldPos': random.randint(20, 85),
        'scoreDiff': random.randint(-16, -1),
        'quarter': 4,
        'clockSeconds': random.randint(31, 90),
        'timeoutsLeft': random.randint(1, 3),
        'clockRunning': 1,
    }


def noRunLateSituation():
    """Trailing, 0 timeouts, clock running — never run."""
    return {**randomPlayCall(),
        'situationType': 'play_call',
        'down': random.randint(1, 3),
        'fieldPos': random.randint(20, 80),
        'scoreDiff': random.randint(-16, -1),
        'quarter': 4,
        'clockSeconds': random.randint(31, 120),
        'timeoutsLeft': 0,
        'clockRunning': 1,
    }


def fourthDownSituation():
    """4th down — punt, kick_fg, or go for it."""
    return {**randomPlayCall(),
        'situationType': 'play_call',
        'down': 4,
        'yardsToGo': random.randint(1, 15),
        'fieldPos': random.randint(15, 90),
        'scoreDiff': random.randint(-21, 21),
        'quarter': random.randint(1, 4),
        'clockSeconds': random.randint(30, 900),
        'kickerRating': random.randint(55, 99),
    }


def criticalSituation():
    """3rd & long, red zone, 2-minute drill."""
    t = random.choice(['third_long', 'red_zone', 'two_minute'])
    base = randomPlayCall()
    if t == 'third_long':
        base.update({'down': 3, 'yardsToGo': random.randint(8, 20),
                     'fieldPos': random.randint(20, 75),
                     'clockSeconds': random.randint(120, 900)})
    elif t == 'red_zone':
        base.update({'down': random.randint(1, 3), 'yardsToGo': random.randint(1, 15),
                     'fieldPos': random.randint(75, 98), 'clockSeconds': random.randint(60, 900)})
    else:
        base.update({'down': random.randint(1, 3), 'yardsToGo': random.randint(1, 15),
                     'fieldPos': random.randint(30, 75),
                     'scoreDiff': random.randint(-14, 14),
                     'quarter': random.choice([2, 4]),
                     'clockSeconds': random.randint(60, 120)})
    return base


# ---------------------------------------------------------------------------
# Post-TD situations: extra_point vs two_point_conversion
# ---------------------------------------------------------------------------

def postTdSituation():
    """
    After a touchdown — choose extra point or go for 2.
    scoreDiff here is AFTER the TD but BEFORE the XP/2pt.
    Features: scoreDiff, quarter, clockSeconds, timeoutsLeft, coachAggressiveness
    """
    return {
        'situationType': 'post_td',
        'scoreDiff': random.randint(-20, 20),   # after TD, before conversion
        'quarter': random.randint(1, 4),
        'clockSeconds': random.randint(0, 900),
        'timeoutsLeft': random.randint(0, 3),
        'coachAggressiveness': random.randint(60, 100),
        'ownOffenseRating': random.randint(55, 99),
    }


def criticalPostTdSituation():
    """Situations where 2-pt conversion is strategically correct."""
    scoreDiffs = [
        # Trailing by 2 after TD (now leading by 5 after TD → need 2pt to lead by 7 safely, or trailing by 8 → after TD trailing by 2, need 2pt to tie)
        -2, -5, -8, -14,
    ]
    scoreDiff = random.choice(scoreDiffs)
    return {
        'situationType': 'post_td',
        'scoreDiff': scoreDiff,
        'quarter': random.choice([3, 4]),
        'clockSeconds': random.randint(0, 600),
        'timeoutsLeft': random.randint(0, 3),
        'coachAggressiveness': random.randint(60, 100),
        'ownOffenseRating': random.randint(55, 99),
    }


# ---------------------------------------------------------------------------
# Kickoff situations: normal_kickoff vs onside_kick
# ---------------------------------------------------------------------------

def kickoffSituation():
    """
    After a score — normal kickoff or attempt onside kick.
    Features: scoreDiff (after score), quarter, clockSeconds, timeoutsLeft, coachAggressiveness
    """
    return {
        'situationType': 'kickoff',
        'scoreDiff': random.randint(-35, 35),
        'quarter': random.randint(1, 4),
        'clockSeconds': random.randint(0, 900),
        'timeoutsLeft': random.randint(0, 3),
        'coachAggressiveness': random.randint(60, 100),
    }


def onsideKickSituation():
    """Trailing late — onside kick is a real option."""
    return {
        'situationType': 'kickoff',
        'scoreDiff': random.randint(-16, -1),
        'quarter': 4,
        'clockSeconds': random.randint(0, 180),
        'timeoutsLeft': random.randint(0, 3),
        'coachAggressiveness': random.randint(60, 100),
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    situations = []

    # --- In-drive play-call ---
    for _ in range(10000):
        situations.append(randomPlayCall())
    for _ in range(2000):
        situations.append(criticalSituation())
    for _ in range(2000):
        situations.append(fourthDownSituation())
    for _ in range(1500):
        situations.append(spikeSituation())
    for _ in range(1500):
        situations.append(kneelSituation())
    for _ in range(1500):
        situations.append(callTimeoutSituation())
    for _ in range(1500):
        situations.append(noRunLateSituation())

    # --- Post-TD ---
    for _ in range(2500):
        situations.append(postTdSituation())
    for _ in range(500):
        situations.append(criticalPostTdSituation())

    # --- Kickoff ---
    for _ in range(2000):
        situations.append(kickoffSituation())
    for _ in range(500):
        situations.append(onsideKickSituation())

    random.shuffle(situations)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, 'w') as f:
        json.dump(situations, f, indent=2)

    playCallCount = sum(1 for s in situations if s['situationType'] == 'play_call')
    postTdCount = sum(1 for s in situations if s['situationType'] == 'post_td')
    kickoffCount = sum(1 for s in situations if s['situationType'] == 'kickoff')

    print(f'Generated {len(situations)} total situations → {OUTPUT_PATH}')
    print(f'  play_call: {playCallCount}')
    print(f'  post_td:   {postTdCount}')
    print(f'  kickoff:   {kickoffCount}')


if __name__ == '__main__':
    main()
