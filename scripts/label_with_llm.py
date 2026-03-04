"""
Label coaching situations using Claude Haiku via the Messages Batches API.

Reads:  floosball/data/coaching_situations.json
Writes: floosball/data/coaching_labels.json

Each entry in coaching_labels.json:
  { "situationIndex": int, "situationType": str, "label": str }

Valid labels by situation type:
  play_call : run | short_pass | medium_pass | long_pass | spike | kneel | call_timeout | punt | kick_fg
  post_td   : extra_point | two_point_conversion
  kickoff   : normal_kickoff | onside_kick
"""

import json
import os
import sys
import time
from pathlib import Path

import anthropic

DATA_DIR = Path(__file__).parent.parent / 'data'
INPUT_PATH = DATA_DIR / 'coaching_situations.json'
OUTPUT_PATH = DATA_DIR / 'coaching_labels.json'

MODEL = 'claude-haiku-4-5-20251001'
MAX_TOKENS = 10

PLAY_CALL_LABELS = {'run', 'short_pass', 'medium_pass', 'long_pass', 'spike', 'kneel', 'call_timeout', 'punt', 'kick_fg'}
POST_TD_LABELS = {'extra_point', 'two_point_conversion'}
KICKOFF_LABELS = {'normal_kickoff', 'onside_kick'}

VALID_LABELS = {
    'play_call': PLAY_CALL_LABELS,
    'post_td': POST_TD_LABELS,
    'kickoff': KICKOFF_LABELS,
}

FALLBACKS = {
    'play_call': 'run',
    'post_td': 'extra_point',
    'kickoff': 'normal_kickoff',
}

# ---------------------------------------------------------------------------
# Prompt builders
# ---------------------------------------------------------------------------

def formatClock(seconds: int) -> str:
    m, s = divmod(seconds, 60)
    return f'{m}:{s:02d}'


def estimateFgRange(kickerRating: int) -> int:
    """
    Estimate max kickable distance (yards from endzone) from kicker rating.
    Formula mirrors floosball_game.py: maxFgDistance = round(70 * legStrength / 100),
    then subtract 17 for the snap distance. We approximate legStrength ≈ kickerRating.
    """
    return round(70 * kickerRating / 100) - 17


def buildPlayCallPrompt(s: dict) -> str:
    scoreDiff = s['scoreDiff']
    if scoreDiff > 0:
        scoreText = f'leading by {scoreDiff}'
    elif scoreDiff < 0:
        scoreText = f'trailing by {abs(scoreDiff)}'
    else:
        scoreText = 'tied'

    clockRunningText = 'clock is running' if s['clockRunning'] else 'clock is stopped'
    fgRange = estimateFgRange(s['kickerRating'])
    yardsFromEndzone = 100 - s['fieldPos']
    inFgRange = yardsFromEndzone <= fgRange
    fgRangeText = f'YES ({yardsFromEndzone} yd from end zone, kicker max {fgRange} yd)' if inFgRange else f'NO ({yardsFromEndzone} yd from end zone, kicker max {fgRange} yd)'

    return f"""You are an NFL offensive coordinator. What is your SINGLE best action for this situation?

Down: {s['down']}, Yards to go: {s['yardsToGo']}
Field position: own {s['fieldPos']} yard line ({yardsFromEndzone} yards from end zone)
Score: {scoreText}
Quarter: {s['quarter']}, Clock: {formatClock(s['clockSeconds'])} ({clockRunningText})
Timeouts remaining: {s['timeoutsLeft']}
In field goal range: {fgRangeText}
Offense quality: {s['ownOffenseRating']}/100
Opponent run defense: {s['oppDefRunRating']}/100
Opponent pass defense: {s['oppDefPassRating']}/100
Coach aggressiveness: {s['coachAggressiveness']}/100
Coach offensive mind: {s['coachOffensiveMind']}/100

Decision rules — work down this list in order, stop at the FIRST rule that applies:

CLOCK MANAGEMENT (evaluate before any other decision):
1. kneel: Q4 ONLY, you are LEADING, fewer than 80 seconds remaining → kneel
2. spike: Q4 or Q2 only, clock is running, fewer than 15 seconds, no timeouts → spike
3. call_timeout: Q4 only (or Q2 final 2 min), trailing, clock RUNNING, timeouts ≥ 1, fewer than 120 seconds remaining → call_timeout

1ST DOWN — quarter determines priority:
4. Q1 or Q2: → run or short_pass; play your game plan; score difference is not critical yet
5. Q3: → run or short_pass; begin favoring passes over runs if trailing by 10+
6. Q4, leading or tied: → run (protect the lead, consume clock)
7. Q4, trailing 1-9 points: → run or short_pass (need points but stay balanced)
8. Q4, trailing 10+ points: → short_pass or medium_pass; use long_pass only if pass defense < 65 OR coach aggressiveness > 80

3RD DOWN — yards to go is the primary driver (Q1/Q2/Q3 default; Q4 modifiers below):
9. 3rd & ≤3 yards: → run (if run defense ≤ 75) or short_pass
10. 3rd & 4-5 yards: → short_pass (most reliable conversion) or run
11. 3rd & 6-12 yards: → medium_pass (DEFAULT — crossing routes, digs, and curls convert 3rd & medium). Do NOT use long_pass here.
12. 3rd & 13+ yards: → long_pass (need a chunk gain); short_pass is a safe check-down if conservative

2ND DOWN — yards to go is the primary driver (Q1/Q2/Q3 default; Q4 modifiers below):
13. 2nd & ≤4 yards: → run (strong position; pick up the first)
14. 2nd & 5-9 yards: → medium_pass (sets up a manageable 3rd down) or run (if run defense ≤ 70)
15. 2nd & 10+ yards: → medium_pass; use long_pass if trailing 7+ OR pass defense < 70

Q4 OVERRIDES for 2nd and 3rd down (apply these INSTEAD of rules 9-15 when in Q4):
- Q4, LEADING on 2nd or 3rd down with ≤6 yards to go: → run (keep clock moving, protect the lead)
- Q4, LEADING on 3rd & 13+: → short_pass or run (do not gamble with a long pass and risk a pick; accept the punt situation)
- Q4, TRAILING 14+, 3rd & 6-12, coach aggressiveness > 80: → long_pass acceptable (exception to rule 11)
- Q4, TRAILING 10+ on 2nd or 3rd down: → medium_pass or long_pass; use long_pass if pass defense < 65 OR coach aggressiveness > 80

4th down — follow this priority order, stop at the first rule that applies:
1. kick_fg — if "In field goal range" above says YES
2. Go for it (run / short_pass / medium_pass / long_pass) — ONLY if NOT in field goal range AND in opponent territory (field position past own 50) AND yards to go ≤ 4
3. punt — all other 4th down situations (own territory, long yardage, not in range)

NEVER use long_pass on 3rd & 6-12 yards — medium_pass is far more likely to convert.
NEVER use run when trailing in Q4 with clock running and 0 timeouts.

Reply with exactly one word from: run / short_pass / medium_pass / long_pass / spike / kneel / call_timeout / punt / kick_fg"""


def buildPostTdPrompt(s: dict) -> str:
    scoreDiff = s['scoreDiff']
    if scoreDiff > 0:
        scoreText = f'leading by {scoreDiff}'
    elif scoreDiff < 0:
        scoreText = f'trailing by {abs(scoreDiff)}'
    else:
        scoreText = 'tied'

    return f"""You are an NFL offensive coordinator. You just scored a touchdown. Choose your conversion.

Score after TD (before conversion): {scoreText}
Quarter: {s['quarter']}, Clock: {formatClock(s['clockSeconds'])}
Timeouts remaining: {s['timeoutsLeft']}
Offense quality: {s['ownOffenseRating']}/100
Coach aggressiveness: {s['coachAggressiveness']}/100

Decision rules:
- extra_point: the default choice in the vast majority of situations — reliable 1 point, low risk
- two_point_conversion: rare; only go for 2 when the score differential makes it strategically essential.
  The main situations where 2pt is correct (scoreDiff = score after TD, before conversion):
  * scoreDiff = -2: XP only cuts deficit to 1; 2pt ties the game
  * scoreDiff = -8: XP leaves deficit at 7 (still need 2pt next time); 2pt cuts to 6 (just a TD+XP away)
  * scoreDiff = -5: 2pt cuts to 3 (a field goal ties); XP leaves at 4 (harder to tie)
  * scoreDiff = -14: 2pt cuts to 12 (two TDs + 2pts ties); XP leaves at 13
  * Only attempt in Q3 or Q4. In Q1 and Q2, always kick the extra_point.
  * Extra_point is still correct in the majority of situations — only go for 2 when the score arithmetic clearly favors it.

Reply with exactly one word from: extra_point / two_point_conversion"""


def buildKickoffPrompt(s: dict) -> str:
    scoreDiff = s['scoreDiff']
    if scoreDiff > 0:
        scoreText = f'leading by {scoreDiff}'
    elif scoreDiff < 0:
        scoreText = f'trailing by {abs(scoreDiff)}'
    else:
        scoreText = 'tied'

    return f"""You are an NFL special teams coordinator. Choose your kickoff type.

Score after score: {scoreText}
Quarter: {s['quarter']}, Clock: {formatClock(s['clockSeconds'])}
Timeouts remaining: {s['timeoutsLeft']}
Coach aggressiveness: {s['coachAggressiveness']}/100

Decision rules:
- normal_kickoff: the default in nearly all situations — kick deep, force a return, play defense
- onside_kick: last-resort only; attempt ONLY when ALL of these are true:
  * it is Q4
  * trailing by 8 or more points
  * under 2 minutes on the clock
  * a normal kickoff would almost certainly end the game
  In all other situations — including being down by 1-7, or with more than 2 minutes left — kick normally.

Reply with exactly one word from: normal_kickoff / onside_kick"""


PROMPT_BUILDERS = {
    'play_call': buildPlayCallPrompt,
    'post_td': buildPostTdPrompt,
    'kickoff': buildKickoffPrompt,
}

# ---------------------------------------------------------------------------
# Batch submission
# ---------------------------------------------------------------------------

BATCH_SIZE = 2500    # Smaller batches to avoid connection drops on large payloads


def buildRequests(situations: list) -> list:
    requests = []
    for i, s in enumerate(situations):
        situationType = s['situationType']
        prompt = PROMPT_BUILDERS[situationType](s)
        requests.append({
            'custom_id': str(i),
            'params': {
                'model': MODEL,
                'max_tokens': MAX_TOKENS,
                'messages': [{'role': 'user', 'content': prompt}],
            },
        })
    return requests


def submitBatch(client: anthropic.Anthropic, requests: list) -> str:
    for attempt in range(3):
        try:
            batch = client.messages.batches.create(requests=requests)
            print(f'  Submitted batch {batch.id} with {len(requests)} requests')
            return batch.id
        except Exception as e:
            if attempt == 2:
                raise
            print(f'  Submit failed (attempt {attempt + 1}/3): {e} — retrying in 5s...')
            time.sleep(5)


def waitForBatch(client: anthropic.Anthropic, batchId: str) -> list:
    """Poll until the batch is complete, then return results."""
    pollInterval = 10
    while True:
        for attempt in range(3):
            try:
                batch = client.messages.batches.retrieve(batchId)
                break
            except Exception as e:
                if attempt == 2:
                    raise
                print(f'  Retrieve failed (attempt {attempt + 1}/3): {e} — retrying in 10s...')
                time.sleep(10)
        counts = batch.request_counts
        print(f'  Batch {batchId}: processing={counts.processing}, '
              f'succeeded={counts.succeeded}, errored={counts.errored}')
        if batch.processing_status == 'ended':
            break
        time.sleep(pollInterval)

    results = []
    for result in client.messages.batches.results(batchId):
        results.append(result)
    return results


def parseLabel(text: str, situationType: str) -> str:
    valid = VALID_LABELS[situationType]
    text = text.strip().lower().rstrip('.')
    if text in valid:
        return text
    # Try to find a valid label anywhere in the response
    for label in valid:
        if label in text:
            return label
    return FALLBACKS[situationType]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    apiKey = os.environ.get('ANTHROPIC_API_KEY')
    if not apiKey:
        print('ERROR: ANTHROPIC_API_KEY environment variable not set')
        sys.exit(1)

    with open(INPUT_PATH) as f:
        situations = json.load(f)

    print(f'Loaded {len(situations)} situations from {INPUT_PATH}')

    client = anthropic.Anthropic(api_key=apiKey)

    # Split into batches if needed (Batches API limit is 10k per batch)
    allRequests = buildRequests(situations)
    batches = [allRequests[i:i + BATCH_SIZE] for i in range(0, len(allRequests), BATCH_SIZE)]

    print(f'Submitting {len(batches)} batch(es)...')
    batchIds = []
    for idx, batchRequests in enumerate(batches):
        print(f'Batch {idx + 1}/{len(batches)}:')
        batchId = submitBatch(client, batchRequests)
        batchIds.append(batchId)

    # Wait for all batches
    allResults = []
    for idx, batchId in enumerate(batchIds):
        print(f'\nWaiting for batch {idx + 1}/{len(batches)} ({batchId})...')
        results = waitForBatch(client, batchId)
        allResults.extend(results)

    # Parse results
    labelMap = {}
    errCount = 0
    for result in allResults:
        idx = int(result.custom_id)
        if result.result.type == 'succeeded':
            rawText = result.result.message.content[0].text
            situationType = situations[idx]['situationType']
            label = parseLabel(rawText, situationType)
            labelMap[idx] = label
        else:
            errCount += 1
            situationType = situations[idx]['situationType']
            labelMap[idx] = FALLBACKS[situationType]

    # Build output
    labels = []
    for i, s in enumerate(situations):
        labels.append({
            'situationIndex': i,
            'situationType': s['situationType'],
            'label': labelMap.get(i, FALLBACKS[s['situationType']]),
        })

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, 'w') as f:
        json.dump(labels, f, indent=2)

    # Summary
    from collections import Counter
    playCallCounts = Counter(l['label'] for l in labels if l['situationType'] == 'play_call')
    postTdCounts = Counter(l['label'] for l in labels if l['situationType'] == 'post_td')
    kickoffCounts = Counter(l['label'] for l in labels if l['situationType'] == 'kickoff')

    print(f'\nLabeled {len(labels)} situations → {OUTPUT_PATH}')
    if errCount:
        print(f'  Errors (used fallback): {errCount}')
    print('\nplay_call label distribution:')
    for label, count in sorted(playCallCounts.items()):
        print(f'  {label:20s}: {count}')
    print('\npost_td label distribution:')
    for label, count in sorted(postTdCounts.items()):
        print(f'  {label:20s}: {count}')
    print('\nkickoff label distribution:')
    for label, count in sorted(kickoffCounts.items()):
        print(f'  {label:20s}: {count}')


if __name__ == '__main__':
    main()
