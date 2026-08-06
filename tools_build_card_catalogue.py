# -*- coding: utf-8 -*-
"""Merge the live card catalogue (from code) with the planned new cards into the doc."""
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


# Cards whose behaviour or name changes under this plan. value = note shown in the table.
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
  'Once the rhythm arrives, everything comes easier. FPx growing with every completion past 20.',
  '+{perCompletionMult} FPx per completion past {threshold}'),
 ('clockwork','prismatic','FP','Clockwork','Never misses a beat',
  'Same time every week. Streak grows each week this player clears 25 completions.',
  '+{baseFP} FP, +{growthPerTick} per week this player clears {threshold} completions'),
 # QB — pass yards, flight
 ('slipstream','metallic','FPx','Slipstream','Riding the air',
  'The ball hangs and the yards pile up. FPx scaling with passing yards.',
  '+{perHundredMult} FPx for every 100 passing yards by this player'),
 ('updraft','holographic','FP','Updraft','Catching a lift',
  'Some days the ball just carries. Escalating FP past 200, 300 and 400 yards.',
  '+{gate1}/{gate2}/{gate3} FP at 200, 300 and 400 passing yards'),
 ('stratosphere','prismatic','FPx','Stratosphere','Thin air up here',
  'Territory most passers never see. Streak grows each week this player clears 300 yards.',
  '+{baseMult} FPx, +{growthPerTick} per week this player clears {threshold} passing yards'),
 # QB — pass TDs, ordnance
 ('bombardier','metallic','FPx','Bombardier','Target acquired',
  'Precision from altitude. FPx for every passing touchdown.',
  '+{perTdMult} FPx for every passing TD by this player'),
 ('salvo','holographic','FP','Salvo','All at once',
  'One is a shot. Three is a salvo. FP per passing TD, doubled at three.',
  '+{perTdFP} FP per passing TD, doubled at {threshold}+'),
 ('barrage','prismatic','FP','Barrage','Keep firing',
  'Each score raises the odds the next one pays. Escalating chance per passing TD.',
  '+{baseFP} FP, escalating chance at {bonusFP} FP per passing TD'),
 # QB — throw quality, marksmanship
 ('marksman','holographic','FPx','Marksman','Nothing wasted',
  'Not one ball off target. FPx when this player finishes the week without a bad throw.',
  '+{cleanSheetMult} FPx when this player records 0 bad throws'),
 ('dead_eye','prismatic','FP','Dead Eye','Never off target',
  'Week after week, right on the numbers. Streak grows with every clean sheet.',
  '+{baseFP} FP, +{growthPerTick} per week this player records 0 bad throws'),
 # RB — carries, labour
 ('beast_of_burden','holographic','FPx','Beast of Burden','Carrying the load',
  'Keep feeding the ball until the legs give out. FPx once this player clears 25 carries.',
  '+{perCarryMult} FPx per carry past {threshold}'),
 ('iron_man','prismatic','FP','Iron Man','Never comes off the field',
  'Twenty carries, every single week. Streak grows each week the bar is cleared.',
  '+{baseFP} FP, +{growthPerTick} per week this player clears {threshold} carries'),
 # RB — rush yards, journey
 ('odyssey','prismatic','FP','Odyssey','The long road',
  'A hundred yards a week, week after week. Streak grows each time the mark is reached.',
  '+{baseFP} FP, +{growthPerTick} per week this player clears {threshold} rushing yards'),
 # RB — rush TDs, force
 ('battering_ram','metallic','FPx','Battering Ram','Straight through',
  'No finesse required. FPx for every rushing touchdown.',
  '+{perTdMult} FPx for every rushing TD by this player'),
 # RB — yards after contact, mass
 ('freight','metallic','FP','Freight','Hard to stop',
  "The first hit never finishes the job. FP for every yard gained after contact.",
  '+{perYardFP} FP per yard after contact by this player'),
 ('grinder','holographic','FPx','Grinder','Earning every inch',
  'More yards after the hit than before it. FPx when contact yards clear half the total.',
  '+{ratioMult} FPx when yards after contact exceed half of rushing yards'),
 ('landslide','prismatic','FP','Landslide','Gathering weight',
  'A hundred yards after contact, every week. Streak grows each time.',
  '+{baseFP} FP, +{growthPerTick} per week this player clears {threshold} yards after contact'),
 # WR/TE — receptions, custody
 ('custody','holographic','FPx','Custody','Safe hands',
  'Everything thrown that way comes down. FPx per catch past eight.',
  '+{perReceptionMult} FPx per reception past {threshold}'),
 ('tenure','prismatic','FP','Tenure','Long service',
  'Eight catches a week, without fail. Streak grows each week the bar is cleared.',
  '+{baseFP} FP, +{growthPerTick} per week this player clears {threshold} receptions'),
 # WR/TE — receiving yards, territory
 ('frontier','metallic','FP','Frontier','Always pushing out',
  'Every yard is new ground. FP for every receiving yard.',
  '+{perYardFP} FP per receiving yard by this player'),
 ('territory','holographic','FPx','Territory','Claiming ground',
  'Escalating FPx as this player passes 75, 125 and 175 receiving yards.',
  '+{gate1}/{gate2}/{gate3} FPx at 75, 125 and 175 receiving yards'),
 ('dominion','prismatic','FP','Dominion','The whole field',
  'A hundred yards a week and nobody takes it back. Streak grows each time.',
  '+{baseFP} FP, +{growthPerTick} per week this player clears {threshold} receiving yards'),
 # WR/TE — receiving TDs, end zone
 ('paydirt','metallic','FPx','Paydirt','Cash in',
  'Cross the line, collect. FPx for every receiving touchdown.',
  '+{perTdMult} FPx for every receiving TD by this player'),
 ('end_zone','holographic','FP','End Zone','Where it counts',
  "One is good. Two is somebody else's problem. FP per receiving TD, doubled at two.",
  '+{perTdFP} FP per receiving TD, doubled at {threshold}+'),
 ('promised_land','prismatic','FP','Promised Land','Getting there',
  'Each score raises the odds the next one pays.',
  '+{baseFP} FP, escalating chance at {bonusFP} FP per receiving TD'),
 # WR/TE — YAC, escape
 ('getaway','prismatic','FP','Getaway','Gone',
  'Forty yards after the catch, every week. Streak grows each time.',
  '+{baseFP} FP, +{growthPerTick} per week this player clears {threshold} YAC'),
 # K — punting, burial
 ('pinpoint','metallic','FP','Pinpoint','Drop it on a dime',
  'Placement over power. FP for every punt downed inside the 20.',
  '+{perPuntFP} FP per punt downed inside the 20'),
 ('coffin_corner','holographic','FPx','Coffin Corner','Nowhere to go',
  'Inside the ten and pinned against the sideline. FPx per punt downed inside the 10.',
  '+{perPuntMult} FPx per punt downed inside the 10'),
 ('undertaker','prismatic','FP','Undertaker','Bury them',
  'Week after week the opponent starts in a hole. Streak grows with multi-pin weeks.',
  '+{baseFP} FP, +{growthPerTick} per week this player pins {threshold}+ punts inside the 20'),
 # K — returns, the runback
 ('runback','metallic','FP','Runback','Bring it out',
  'The play starts on the catch. FP for every punt return yard.',
  '+{perYardFP} FP per punt return yard by this player'),
 ('house_call','prismatic','FP','House Call','All the way',
  'Sometimes nobody gets a hand on it. Chance paying out on a return touchdown.',
  '+{baseFP} FP, chance at {bonusFP} FP on a punt return TD'),
 # One-offs
 ('attention','metallic','FPx','Attention','Feed the target',
  'The ball is coming down there, caught or not. FPx for every target.',
  '+{perTargetMult} FPx for every target by this player'),
 ('altitude','holographic','FP','Altitude','Throwing it deep',
  'Nothing underneath. FP scaling with average depth of target above 8 yards.',
  '+{perYardFP} FP per yard of average target depth above {threshold}'),
 ('haymaker','holographic','FP','Haymaker','Swinging big',
  'Twenty yards at a time. FP for every throw of 20 or more.',
  '+{perThrowFP} FP for every 20+ yard completion by this player'),
 ('highpoint','holographic','FP','Highpoint','Above the crowd',
  'Two defenders on the ball and it still comes down. FP per contested catch.',
  '+{perCatchFP} FP per contested catch by this player'),
 ('breakaway','holographic','FP','Breakaway','Gone in a blink',
  'One crease is all it takes. FP for every run of 20 or more.',
  '+{perRunFP} FP for every 20+ yard run by this player'),
 ('houdini','prismatic','FP','Houdini',"Impossible to corner",
  "The tackle was there and then it wasn't. Chance filling from broken tackles.",
  '+{baseFP} FP guaranteed, chance at {bonusFP} FP filling from broken tackles'),
 ('custodian','prismatic','FP','Custodian','Cleaning up',
  'The throw was bad. The catch was made anyway. FP for every bailout.',
  '+{perBailoutFP} FP per bailout by this player'),
]

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
    rows[ed][kind(e)].append((label, t, d, dd, note, False))
for key, ed, k, disp, t, d, dd in NEW:
    rows[ed][k].append((disp, t, d, dd, '', True))

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
