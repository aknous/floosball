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
    def __init__(self, category, text, stats=None, ageHours=0, week=10, season=3, weight=None):
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
        self.lead_weight = weight
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

out = build([Row('big_game', 'no strip at all'), Row('upset', 'two only', stats=FOUR[:2])])
expect("nothing leads when no item carries enough numbers", out['lead'] is None)
expect("...and every item falls through to the rows", len(out['items']) == 2)

# A record's strip is three cells — old mark, new mark, gap — and requiring four locked
# every record out of the headline, which is a third of the interesting news in the feed.
out = build([Row('big_game', 'a big game', stats=FOUR), Row('record', 'a record fell', stats=FOUR[:3], weight=9.0)])
expect("three numbers is enough to lead, so records can headline",
       out['lead'] and out['lead']['text'] == 'a record fell')

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

print("\nSize decides inside a moment, not category")
# MEASURED over 546 real rows: ranking a simultaneous slate by a static category ladder
# gave `upset` 87% of reader views on 24% of the eligible items, and left `big_game` at
# 8% on 76% of them. A slate resolves in one instant, so the ladder was the sort.
out = build([Row('upset', 'a routine upset', stats=FOUR, weight=1.02),
             Row('big_game', 'a monstrous game', stats=FOUR, weight=2.40)])
expect("a huge big game beats a marginal upset, despite ranking below it",
       out['lead'] and out['lead']['text'] == 'a monstrous game')

out = build([Row('upset', 'a stunning upset', stats=FOUR, weight=2.40),
             Row('big_game', 'a routine big game', stats=FOUR, weight=1.02)])
expect("...and the reverse, so the headline actually turns over",
       out['lead'] and out['lead']['text'] == 'a stunning upset')

# Prod rows written before lead_weight existed carry none. Treating those as zero would
# make every one of them permanently unleadable.
out = build([Row('upset', 'an old row, no weight', stats=FOUR),
             Row('big_game', 'a weak new one', stats=FOUR, weight=0.4)])
expect("a weightless legacy row still ranks, at its own threshold",
       out['lead'] and out['lead']['text'] == 'an old row, no weight')

# Weight decides WITHIN a moment; it must never let an old story outrank a new one.
out = build([Row('upset', 'huge but stale', stats=FOUR, weight=9.0, ageHours=30),
             Row('big_game', 'small but now', stats=FOUR, weight=1.01, ageHours=0)])
expect("recency still outranks size across moments", out['lead'] and out['lead']['text'] == 'small but now')

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
