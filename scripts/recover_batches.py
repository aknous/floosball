"""
Recover labels from already-submitted Anthropic batches.

Groups the most recent batches by start time — batches from the same run
are submitted within seconds of each other, so any gap > 10 minutes
signals the boundary between runs.

Usage:
    ANTHROPIC_API_KEY=... python scripts/recover_batches.py
    ANTHROPIC_API_KEY=... python scripts/recover_batches.py --limit 30
    ANTHROPIC_API_KEY=... python scripts/recover_batches.py --window 20
"""

import argparse
import json
import os
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import anthropic

DATA_DIR = Path(__file__).parent.parent / 'data'
SITUATIONS_PATH = DATA_DIR / 'coaching_situations.json'
OUTPUT_PATH = DATA_DIR / 'coaching_labels.json'

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


def parseLabel(text: str, situationType: str) -> str:
    valid = VALID_LABELS[situationType]
    text = text.strip().lower().rstrip('.')
    if text in valid:
        return text
    for label in valid:
        if label in text:
            return label
    return FALLBACKS[situationType]


def groupByRun(batches: list, windowMinutes: int) -> list[list]:
    """
    Sort batches newest-first, then split into runs wherever the gap between
    consecutive creation times exceeds windowMinutes. Return list of runs,
    each run being a list of batches (newest run first).
    """
    if not batches:
        return []

    sorted_batches = sorted(batches, key=lambda b: b.created_at, reverse=True)
    runs = []
    currentRun = [sorted_batches[0]]

    for prev, curr in zip(sorted_batches, sorted_batches[1:]):
        gapSeconds = (prev.created_at - curr.created_at).total_seconds()
        if gapSeconds > windowMinutes * 60:
            runs.append(currentRun)
            currentRun = []
        currentRun.append(curr)
    runs.append(currentRun)
    return runs


def waitForBatch(client: anthropic.Anthropic, batchId: str) -> list:
    pollInterval = 15
    while True:
        for attempt in range(3):
            try:
                batch = client.messages.batches.retrieve(batchId)
                break
            except Exception as e:
                if attempt == 2:
                    raise
                print(f'  Retrieve failed ({attempt + 1}/3): {e} — retrying in 10s...')
                time.sleep(10)

        counts = batch.request_counts
        print(f'  {batchId}: processing={counts.processing}, '
              f'succeeded={counts.succeeded}, errored={counts.errored}')

        if batch.processing_status == 'ended':
            break
        time.sleep(pollInterval)

    results = []
    for result in client.messages.batches.results(batchId):
        results.append(result)
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--limit', type=int, default=20,
                        help='How many recent batches to fetch from API (default: 20)')
    parser.add_argument('--window', type=int, default=10,
                        help='Max minutes between batches in same run (default: 10)')
    args = parser.parse_args()

    apiKey = os.environ.get('ANTHROPIC_API_KEY')
    if not apiKey:
        print('ERROR: ANTHROPIC_API_KEY not set')
        sys.exit(1)

    with open(SITUATIONS_PATH) as f:
        situations = json.load(f)
    print(f'Loaded {len(situations)} situations')

    client = anthropic.Anthropic(api_key=apiKey)

    print(f'\nFetching last {args.limit} batches...')
    allBatches = []
    for batch in client.messages.batches.list(limit=args.limit):
        allBatches.append(batch)

    if not allBatches:
        print('No batches found.')
        sys.exit(1)

    runs = groupByRun(allBatches, args.window)
    mostRecentRun = runs[0]

    print(f'Found {len(allBatches)} batches across {len(runs)} run(s).')
    print(f'Most recent run: {len(mostRecentRun)} batch(es)')
    for b in mostRecentRun:
        counts = b.request_counts
        print(f'  {b.id}  status={b.processing_status}  '
              f'succeeded={counts.succeeded}  errored={counts.errored}  '
              f'created={b.created_at.strftime("%Y-%m-%d %H:%M:%S UTC")}')

    activeBatches = [b for b in mostRecentRun
                     if b.processing_status in ('in_progress', 'ended')]

    if not activeBatches:
        print('\nNo active batches in most recent run. Re-run label_with_llm.py.')
        sys.exit(1)

    print(f'\nDownloading results from {len(activeBatches)} batch(es)...')
    allResults = []
    for batch in activeBatches:
        print(f'\nBatch {batch.id} (status={batch.processing_status}):')
        results = waitForBatch(client, batch.id)
        print(f'  Downloaded {len(results)} results')
        allResults.extend(results)

    print(f'\nTotal results collected: {len(allResults)}')

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

    covered = len(labelMap)
    print(f'Labels parsed: {covered} / {len(situations)}')
    if covered < len(situations):
        missing = len(situations) - covered
        print(f'  WARNING: {missing} situations uncovered — '
              f'some batches may be missing (try --limit {args.limit + 10})')

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
    playCallCounts = Counter(l['label'] for l in labels if l['situationType'] == 'play_call')
    postTdCounts = Counter(l['label'] for l in labels if l['situationType'] == 'post_td')
    kickoffCounts = Counter(l['label'] for l in labels if l['situationType'] == 'kickoff')

    print(f'\nWrote {len(labels)} labels → {OUTPUT_PATH}')
    if errCount:
        print(f'  API errors (used fallback): {errCount}')
    print('\nplay_call:')
    for label, count in sorted(playCallCounts.items()):
        print(f'  {label:20s}: {count:5d}  ({count / sum(playCallCounts.values()) * 100:.1f}%)')
    print('\npost_td:')
    for label, count in sorted(postTdCounts.items()):
        print(f'  {label:20s}: {count:5d}  ({count / sum(postTdCounts.values()) * 100:.1f}%)')
    print('\nkickoff:')
    for label, count in sorted(kickoffCounts.items()):
        print(f'  {label:20s}: {count:5d}  ({count / sum(kickoffCounts.values()) * 100:.1f}%)')


if __name__ == '__main__':
    main()
