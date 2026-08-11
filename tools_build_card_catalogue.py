# -*- coding: utf-8 -*-
"""Merge the live card catalog (from code) with the planned new cards into the doc."""
import re, io, collections

src = io.open('managers/cardEffects.py', encoding='utf-8').read()


def tbl(name):
    m = re.search(name + r'\s*=\s*\{(.*?)\n\}', src, re.S)
    return dict(re.findall(r'"([a-z_]+)":\s*"((?:[^"\\]|\\.)*)"', m.group(1)))


names, tag = tbl('EFFECT_DISPLAY_NAMES'), tbl('EFFECT_TAGLINES')
tip, det = tbl('EFFECT_TOOLTIPS'), tbl('EFFECT_DETAIL_TEMPLATES')
tier = dict(re.findall(r'"([a-z_]+)":\s*"([a-z]+)"',
            re.search(r'EFFECT_EDITION_TIER = \{(.*?)\n\}', src, re.S).group(1)))
live = (set(re.findall(r'"([a-z_]+)"', re.sub(r'#.*', '', re.search(
            r'SHARED_EFFECT_POOL\s*=\s*\[(.*?)\n\]', src, re.S).group(1))))
        | set(re.findall(r'"([a-z_]+)"', re.sub(r'#.*', '', re.search(
            r'POSITION_EXCLUSIVE_POOLS = \{(.*?)\n\}', src, re.S).group(1)))))
out = dict(re.findall(r'"([a-z_]+)":\s*"(fp|fpx|floobits)"',
           re.search(r'EFFECT_OUTPUT_TYPE = \{(.*?)\n\}', src, re.S).group(1)))
cat = dict(re.findall(r'"([a-z_]+)":\s*"([a-z_]+)"',
           re.search(r'EFFECT_CATEGORY = \{(.*?)\n\}', src, re.S).group(1)))


def kind(e):
    if out.get(e) == 'fpx' or cat.get(e) == 'multiplier':
        return 'FPx'
    if out.get(e) == 'floobits' or cat.get(e) == 'floobits':
        return 'Floobits'
    if out.get(e) == 'fp':
        return 'FP'
    return 'Other'


# Cards whose behavior or name changes under this plan. value = note shown in the table.
CHANGED = {
    'gunslinger': 'CHANGED — re-pointed from pass yards to throw quality; needs the new '
                  '`goodThrows` counter. New copy below.',
    'stampede': 'RENAMED to **Trailblazer** — joins the rush-yards journey motif.',
    'safety_blanket': 'RETUNED — 5.3 to ~3.2 FP per reception. Measured 47.0 FP/week, '
                      'highest of any metallic card.',
    'three_pointer': 'RETUNED down — measured 39.0 FP/week, second highest at metallic.',
}
NEWCOPY = {
    'gunslinger': ('Puts it on a dime',
                   'Placement, not power. FP for every well-placed ball this player throws.',
                   '+{perGoodThrowFP} FP for every well-placed throw by this player'),
}

# (key, edition, kind, display, tagline, back of card, detail)
NEW = [
 # QB — completions, timekeeping
 ('cadence','metallic','FP','Cadence','Keep the chains moving',
  'Tick, tick, tick. FP for every completion this player makes.',
  '+{perCompletionFP} FP for every completion by this player'),
 ('rhythm','holographic','FPx','Rhythm','Finding a groove',
  'Once the rhythm arrives, everything comes easier. FPx on every completion, and more once past 20.',
  '+{per25Mult} FPx per 25 completions, +{bonusMult} more once past {threshold}'),
 ('clockwork','prismatic','FPx','Clockwork','Never misses a beat',
  'Same time every week. FP on every completion, plus a streak for every week past 25.',
  '+{per25Mult} FPx per 25 completions, plus a streak growing {growthPerTick} FPx per week past {threshold}'),
 # QB — pass yards, flight
 ('slipstream','metallic','FPx','Slipstream','Riding the air',
  'The ball hangs and the yards pile up. FPx scaling with passing yards.',
  '+{per100Mult} FPx per 100 passing yards by this player'),
 ('updraft','holographic','FP','Updraft','Catching a lift',
  'Some days the ball just carries. FP on every passing yard, with more at 200, 300 and 400.',
  '+{perYardFP} FP per passing yard, +{gate1}/{gate2}/{gate3} bonus at 200, 300 and 400'),
 ('stratosphere','prismatic','FPx','Stratosphere','Thin air up here',
  'Territory most passers never see. FPx on passing yards, plus a streak for every 300-yard week.',
  '+{per100Mult} FPx per 100 passing yards, plus a streak growing {growthPerTick} per week past {threshold}'),
 # QB — pass TDs, ordnance
 ('bombardier','metallic','FPx','Bombardier','Target acquired',
  'Precision from altitude. FPx for every passing touchdown.',
  '+{perTdMult} FPx for every passing TD by this player'),
 ('salvo','holographic','FP','Salvo','All at once',
  'One is a shot. Three is a salvo. FP on every passing TD, with a bonus at three.',
  '+{perTdFP} FP per passing TD, +{bonusFP} bonus at {threshold}+'),
 ('barrage','prismatic','FP','Barrage','Keep firing',
  'FP on every passing TD, and each one raises the odds the next pays out.',
  '+{perTdFP} FP per passing TD, plus escalating odds at {bonusFP} FP on each one'),
 # QB — throw quality, marksmanship
 ('marksman','holographic','FPx','Marksman','Nothing wasted',
  'FPx on every well-placed ball, and more for a week without a single bad throw.',
  '+{per5Mult} FPx per 5 well-placed throws, +{cleanSheetMult} more on 0 bad throws'),
 ('dead_eye','prismatic','FPx','Dead Eye','Never off target',
  'FP on every well-placed ball, plus a streak for every week with nothing off target.',
  '+{per5Mult} FPx per 5 well-placed throws, plus a streak growing {growthPerTick} FPx per clean sheet'),
 # RB — carries, labour
 ('beast_of_burden','holographic','FPx','Beast of Burden','Carrying the load',
  'FPx on every carry, and more once the workload passes 25.',
  '+{per25Mult} FPx per 25 carries, +{bonusMult} more once past {threshold}'),
 ('iron_man','prismatic','FPx','Iron Man','Never comes off the field',
  'FP on every carry, plus a streak for every week the load passes twenty.',
  '+{per25Mult} FPx per 25 carries, plus a streak growing {growthPerTick} FPx per week past {threshold}'),
 # RB — rush yards, journey
 ('odyssey','prismatic','FPx','Odyssey','The long road',
  'FP on every rushing yard, plus a streak for every hundred-yard week.',
  '+{per50Mult} FPx per 50 rushing yards, plus a streak growing {growthPerTick} FPx per week past {threshold}'),
 # RB — rush TDs, force
 ('battering_ram','metallic','FPx','Battering Ram','Straight through',
  'No finesse required. FPx for every rushing touchdown.',
  '+{perTdMult} FPx for every rushing TD by this player'),
 # RB — yards after contact, mass
 ('freight','metallic','FP','Freight','Hard to stop',
  "The first hit never finishes the job. FP for every yard gained after contact.",
  '+{perYardFP} FP per yard after contact by this player'),
 ('grinder','holographic','FPx','Grinder','Earning every inch',
  'FPx on every yard after contact, and more when those yards clear half the total.',
  '+{per50Mult} FPx per 50 yards after contact, +{ratioMult} more when they exceed half the total'),
 ('landslide','prismatic','FPx','Landslide','Gathering weight',
  'FP on every yard after contact, plus a streak for every hundred-yard week.',
  '+{per50Mult} FPx per 50 yards after contact, plus a streak growing {growthPerTick} FPx per week past {threshold}'),
 # WR/TE — receptions, custody
 ('custody','holographic','FPx','Custody','Safe hands',
  'FPx on every catch, and more once the count passes eight.',
  '+{per5Mult} FPx per 5 receptions, +{bonusMult} more once past {threshold}'),
 ('tenure','prismatic','FPx','Tenure','Long service',
  'FP on every catch, plus a streak for every week the count passes eight.',
  '+{per5Mult} FPx per 5 receptions, plus a streak growing {growthPerTick} FPx per week past {threshold}'),
 # WR/TE — receiving yards, territory
 ('frontier','metallic','FP','Frontier','Always pushing out',
  'Every yard is new ground. FP for every receiving yard.',
  '+{perYardFP} FP per receiving yard by this player'),
 ('territory','holographic','FPx','Territory','Claiming ground',
  'FPx on every receiving yard, with more at 75, 125 and 175.',
  '+{per50Mult} FPx per 50 receiving yards, +{gate1}/{gate2}/{gate3} more at 75, 125 and 175'),
 ('dominion','prismatic','FPx','Dominion','The whole field',
  'FP on every receiving yard, plus a streak for every hundred-yard week.',
  '+{per50Mult} FPx per 50 receiving yards, plus a streak growing {growthPerTick} FPx per week past {threshold}'),
 # WR/TE — receiving TDs, end zone
 ('paydirt','metallic','FPx','Paydirt','Cash in',
  'Cross the line, collect. FPx for every receiving touchdown.',
  '+{perTdMult} FPx for every receiving TD by this player'),
 ('end_zone','holographic','FP','End Zone','Where it counts',
  "One is good. Two is somebody else's problem. FP on every receiving TD, with a bonus at two.",
  '+{perTdFP} FP per receiving TD, +{bonusFP} bonus at {threshold}+'),
 ('promised_land','prismatic','FP','Promised Land','Getting there',
  'FP on every receiving TD, and each one raises the odds the next pays out.',
  '+{perTdFP} FP per receiving TD, plus escalating odds at {bonusFP} FP on each one'),
 # WR/TE — YAC, escape
 ('getaway','prismatic','FPx','Getaway','Gone',
  'FP on every yard after the catch, plus a streak for every forty-yard week.',
  '+{per10Mult} FPx per 10 YAC yards, plus a streak growing {growthPerTick} FPx per week past {threshold}'),
 # K — punting, burial
 ('pinpoint','metallic','FP','Pinpoint','Drop it on a dime',
  'Placement over power. FP for every punt downed inside the 20.',
  '+{perPuntFP} FP per punt downed inside the 20'),
 ('coffin_corner','holographic','FPx','Coffin Corner','Nowhere to go',
  'FPx on every punt downed inside the 20, and more for the ones inside the 10.',
  '+{perPuntMult} FPx per punt inside the 20, +{bonusMult} more for inside the 10'),
 ('undertaker','prismatic','FPx','Undertaker','Bury them',
  'FP on every punt downed inside the 20, plus a streak for every multi-pin week.',
  '+{perPuntMult} FPx per punt inside the 20, plus a streak growing {growthPerTick} FPx per week past {threshold}'),
 # K — returns, the runback
 ('runback','metallic','FP','Runback','Bring it out',
  'The play starts on the catch. FP for every punt return yard.',
  '+{perYardFP} FP per punt return yard by this player'),
 ('house_call','prismatic','FP','House Call','All the way',
  'FP on every return yard, and sometimes nobody gets a hand on it at all.',
  '+{perYardFP} FP per punt return yard, plus a chance at {bonusFP} FP on a return TD'),
 # One-offs
 ('attention','metallic','FPx','Attention','Feed the target',
  'The ball is coming down there, caught or not. FPx for every target.',
  '+{per5Mult} FPx per 5 targets by this player'),
 ('altitude','holographic','FP','Altitude','Throwing it deep',
  'Nothing underneath. FP scaling with average depth of target above 8 yards.',
  '+{perYardFP} FP per yard of average target depth above {threshold}'),
 ('haymaker','holographic','FP','Haymaker','Swinging big',
  'Twenty yards at a time. FP for passing yards, and a bonus on every throw that goes 20.',
  '+{perYardFP} FP per passing yard, +{bonusFP} for every 20+ yard completion by this player'),
 ('highpoint','holographic','FP','Highpoint','Above the crowd',
  'Two defenders on the ball and it still comes down. FP per catch, and a bonus for the ones taken in traffic.',
  '+{perReceptionFP} FP per reception, +{bonusFP} per contested catch by this player'),
 ('breakaway','holographic','FP','Breakaway','Gone in a blink',
  'One crease is all it takes. FP for rushing yards, and a bonus every time this player breaks one for 20.',
  '+{perYardFP} FP per rushing yard, +{bonusFP} for every 20+ yard run by this player'),
 ('houdini','prismatic','FP','Houdini',"Impossible to corner",
  "FP on every rushing yard, and a shot at more every time a tackle gets broken.",
  '+{perYardFP} FP per rushing yard, plus a chance at {bonusFP} FP filling from broken tackles'),
 ('custodian','prismatic','FP','Custodian','Cleaning up',
  'The throw was bad. The catch was made anyway. FP per catch, and a bonus for rescuing a bad ball.',
  '+{perReceptionFP} FP per reception, +{bonusFP} per bailout by this player'),
]

NEW_KEYS = {row[0] for row in NEW}

rows = collections.defaultdict(lambda: collections.defaultdict(list))
for e in sorted(live):
    ed = tier.get(e)
    if not ed:
        continue
    t, d, dd = tag.get(e, ''), tip.get(e, ''), det.get(e, '')
    if e in NEWCOPY:
        t, d, dd = NEWCOPY[e]
    label = names.get(e, e)
    if e == 'stampede':
        label = 'Trailblazer'
    note = CHANGED.get(e, '')
    rows[ed][kind(e)].append((label, t, d, dd, note, e in NEW_KEYS))

# NEW started life as a list of cards that existed only on paper, appended after the
# code-derived rows. Every one is now built, so appending them listed all 39 TWICE.
# The literal is kept for its copy (NEWCOPY reads it), but membership is what flags a
# row — so a card drops off the "new" list by being removed here, not by being built.
_unbuilt = sorted(NEW_KEYS - set(tier))
if _unbuilt:
    print(f"  NOTE: {len(_unbuilt)} card(s) in NEW are not in the code: {_unbuilt}")

buf = []
ORDER = ['metallic', 'holographic', 'prismatic', 'diamond']
KORDER = ['FP', 'FPx', 'Floobits', 'Other']
tot_new = tot_all = 0
for ed in ORDER:
    counts = {k: len(rows[ed].get(k, [])) for k in KORDER}
    n = sum(counts.values())
    tot_all += n
    line = '  ·  '.join(f"{k} {counts[k]}" for k in KORDER if counts[k])
    buf.append(f"\n### {ed.capitalize()} — {n} cards\n")
    buf.append(f"*{line}*\n")
    for k in KORDER:
        es = rows[ed].get(k)
        if not es:
            continue
        buf.append(f"\n#### {ed.capitalize()} · {k}\n")
        buf.append("| card | tagline | back of card | detail |")
        buf.append("|---|---|---|---|")
        for disp, t, d, dd, note, isnew in sorted(es, key=lambda r: r[0]):
            if isnew:
                tot_new += 1
            mark = ' **`NEW`**' if isnew else ''
            cell = f"**{disp}**{mark}"
            if note:
                dd = (dd + f"<br>*{note}*") if dd else f"*{note}*"
            buf.append(f"| {cell} | {t} | {d} | {dd} |")
buf.append(f"\n**Totals: {tot_all} cards ({tot_new} new).**\n")
io.open('/Users/andrew/.claude/jobs/c29305c5/tmp/catalogue.md', 'w',
        encoding='utf-8').write('\n'.join(buf))
print(f"{tot_all} cards, {tot_new} new")
for ed in ORDER:
    print(f"  {ed:13}", {k: len(rows[ed].get(k, [])) for k in KORDER if rows[ed].get(k)})
