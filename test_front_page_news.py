"""The front page's news feed is cumulative, mixed, and led by something recent.

Three behaviours that are easy to regress and each of which was wrong at least once
while building it:

  * NO CATEGORY OWNS THE FEED. A whole slate of games resolves at once, so the newest N
    rows are just the last N things that happened — in practice six big games, with the
    clinch that landed thirty seconds earlier already gone. A first pass capped per
    category and then topped back up from the overflow, which quietly undid the cap.
  * THE LEAD NEEDS A FULL STRIP AND A RECENT TIMESTAMP. An item without four numbers
    renders as a headline over an empty strip; a three-week-old lead reads as a stuck page.
  * CORES LINES NEVER LEAD. They are voice, not report.

Run: .venv/bin/python test_front_page_news.py   (exits non-zero on any failure)
"""
import sys
sys.path.insert(0, '/Users/andrew/Projects/floosball')
import logging; logging.disable(logging.CRITICAL)
import json
from datetime import datetime, timedelta

import front_page

fails = []
def expect(d, c):
    print(f"  [{'OK' if c else 'FAIL'}] {d}")
    if not c: fails.append(d)


class Row:
    _n = 0
    def __init__(self, category, text, stats=None, ageHours=0, week=10, season=3):
        Row._n += 1
        self.id = Row._n
        self.category = category
        self.text = text
        self.week = week
        self.season = season
        self.team_id = None
        self.player_id = None
        self.core_display_name = 'Vera' if category == 'cores' else None
        self.stats_json = json.dumps(stats) if stats else None
        self.created_at = datetime.utcnow() - timedelta(hours=ageHours)


FOUR = [{'label': 'A', 'value': '1'}, {'label': 'B', 'value': '2'},
        {'label': 'C', 'value': '3'}, {'label': 'D', 'value': '4'}]


class FakeQuery:
    def __init__(self, rows): self._rows = rows
    def order_by(self, *a): return self
    def limit(self, n): self._rows = self._rows[:n]; return self
    def all(self): return self._rows


class FakeSession:
    def __init__(self, rows): self._rows = rows
    def query(self, *a): return FakeQuery(list(self._rows))


def build(rows, limit=10):
    return front_page.buildLeagueNews(None, FakeSession(rows), limit=limit)


print("\nA category cannot own the feed")
rows = [Row('big_game', f'big game {i}') for i in range(12)]
rows += [Row('upset', f'upset {i}') for i in range(4)]
rows += [Row('clinched', f'clinch {i}') for i in range(3)]
out = build(rows)
counts = {}
for i in out['items']:
    counts[i['rawCategory']] = counts.get(i['rawCategory'], 0) + 1
expect("no category exceeds the cap", all(v <= 3 for v in counts.values()))
expect("more than one category survives", len(counts) >= 3)
expect("big games do not fill it", counts.get('big_game', 0) <= 3)

print("\nThe cap is hard — no topping up from the overflow")
onlyBigGames = [Row('big_game', f'big game {i}') for i in range(20)]
out = build(onlyBigGames, limit=10)
expect("a single-category league gets a SHORT feed, not a padded one", len(out['items']) <= 3)
expect("...and the rows it does get are that category", all(i['rawCategory'] == 'big_game' for i in out['items']))

print("\nThe lead")
out = build([Row('big_game', 'no strip'), Row('upset', 'has a strip', stats=FOUR)])
expect("an item with four numbers leads", out['lead'] and out['lead']['text'] == 'has a strip')
expect("...and is not repeated as a row", all(i['text'] != 'has a strip' for i in out['items']))

out = build([Row('big_game', 'no strip at all'), Row('upset', 'three only', stats=FOUR[:3])])
expect("nothing leads when no item carries a full strip", out['lead'] is None)
expect("...and every item falls through to the rows", len(out['items']) == 2)

out = build([
    Row('upset', 'stale', stats=FOUR, ageHours=front_page.LEAD_MAX_AGE_HOURS + 5),
    Row('big_game', 'fresh', stats=FOUR, ageHours=1),
])
expect("a stale item cannot lead", out['lead'] and out['lead']['text'] == 'fresh')

# Published in the same breath (a clinch and a big game off the same finished game), so
# importance decides rather than which one's timestamp happened to land a millisecond later.
out = build([Row('big_game', 'a big game', stats=FOUR, ageHours=1),
             Row('clinched', 'a clinch', stats=FOUR, ageHours=1)])
expect("within one moment, priority decides", out['lead'] and out['lead']['text'] == 'a clinch')
out = build([Row('clinched', 'a clinch', stats=FOUR, ageHours=1),
             Row('big_game', 'a big game', stats=FOUR, ageHours=1)])
expect("...regardless of which was written first", out['lead'] and out['lead']['text'] == 'a clinch')

# The bug this replaced: only three categories carry a strip, a clinch happens once a
# season, and `upset` statically outranked `big_game` — so the headline was an upset
# essentially every time anyone looked.
out = build([Row('upset', 'an older upset', stats=FOUR, ageHours=6),
             Row('big_game', 'a newer big game', stats=FOUR, ageHours=1)])
expect("a NEWER lower-priority item beats an older higher-priority one",
       out['lead'] and out['lead']['text'] == 'a newer big game')

out = build([Row('big_game', 'an older big game', stats=FOUR, ageHours=6),
             Row('upset', 'a newer upset', stats=FOUR, ageHours=1)])
expect("...and it works the other way round too, so the lead actually varies",
       out['lead'] and out['lead']['text'] == 'a newer upset')

out = build([Row('cores', 'Vera muses', stats=FOUR), Row('upset', 'an upset', stats=FOUR)])
expect("a Cores line never leads, even carrying a strip", out['lead'] and out['lead']['text'] == 'an upset')

print("\nShape")
out = build([Row('upset', 'lead', stats=FOUR)] + [Row('record', f'r{i}') for i in range(9)], limit=10)
expect("a lead plus rows never exceeds the limit", 1 + len(out['items']) <= 10)
expect("an empty feed returns cleanly", build([]) == {'lead': None, 'items': []})

out = build([Row('cores', 'Vera speaks')])
expect("a Cores line is attributed inline", out['items'][0]['text'].startswith('Vera: '))

print("\nCategory labels reach the frontend intact")
out = build([Row('anomaly_transition', 'someone flickers'), Row('big_game', 'a line')])
raws = {i['rawCategory'] for i in out['items']}
expect("the raw category rides along for colour lookup", 'anomaly_transition' in raws)
expect("the display category is humanised", any(i['category'] == 'ANOMALY TRANSITION' for i in out['items']))

print()
if fails:
    print(f"FAIL — {len(fails)} check(s) failed:")
    for f in fails:
        print(f"  - {f}")
else:
    print("PASS — the feed stays mixed, and leads with something recent that has numbers.")
sys.exit(1 if fails else 0)
