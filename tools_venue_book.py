"""Regenerate the Venue Book review page from data/templates/stadiums.yaml.

The page is GENERATED, never hand-edited, so it cannot drift from the data the sim
actually loads. Edit the YAML, run this, republish the HTML.

The NOTES dict below is the one thing here that is not in the YAML: a short line per
venue saying which city or team-name joke it is built on. Keep it current when a
venue is re-read, or the page explains a venue that no longer exists.

Run: python3 tools_venue_book.py
"""
import yaml, json, html, os, sys

OUT = sys.argv[1] if len(sys.argv) > 1 else 'venue-book.html'
D = yaml.safe_load(open('data/templates/stadiums.yaml'))
cfg = json.load(open('config.json'))
T = {i: t for i, t in enumerate(cfg['teams'], 1)}

# reading = the city/name joke the venue is built on.
# alt = a different reading worth considering (None where the current one lands it).
NOTES = {
1:("DISTORTED. Eight million records for the city and not one name in them.", None),
2:("DISTORTED. The only surviving document is a specification, so they built the specification.", None),
3:("BROAD STREET, taken literally. The record gives one property of it and the Cores obliged.", None),
4:("DISTORTED. The monuments, unattributable and the wrong size for anything human.", None),
5:("CARNEGIE MELLON, misheard. The archive spells the name twice, differently, and the Cores resolved it agriculturally.", None),
6:("DISTORTED, and now says so. The city rocked, so the Cores filed it under geology.", None),
7:("DISTORTED. A mirrored monument reconstructed as an actual legume, grown, warm to the touch.", None),
8:("CADILLAC. Two words survive and both are a car; the Cores read the second as a country club.", None),
9:("POP, and the argument about the name. This side holds the word is the SOUND, so it bottles and caps. Paired against Salt Lake City.", None),
10:("Cranes three times over: the docks, the bird, and the man who talked for a living.", None),
11:("DISTORTED. The trees date older than the archive and the flag was left standing.", None),
12:("Rocky Mountain oysters, filed at nine thousand feet with no explanation offered.", None),
13:("RESOLVED. Fat Tuesday, distorted: the archive holds one date for the city and it will not advance.", None),
14:("SETTLED. Fan contribution, Wizard of Oz direction, confirmed by the owner. The location and vibe are not up for redesign; only the weather ladder is ours to tune.", None),
15:("DISTORTED. Read as a CURRENCY, so admission is still paid in them.", None),
16:("DISTORTED. The city survives as one defensive remark about its own temperature.", None),
17:("DISTORTED. The census was filed under entertainment and reconstructed as a residency.", None),
18:("UNDECODABLE, and now that is the joke. A name that rhymes with nothing, so everything else does.", None),
19:("THE 1904 FAIR and a pressed grid, given together in one damaged entry and never separated.", None),
20:("THE MIDNIGHT SUN, inverted from my first draft. The timestamps say night and the light disagrees.", None),
21:("DISTORTED. No land is recorded for this city at all, so nothing could be moored to.", None),
22:("ANACHRONISM. Nothing in the archive records what the object did, so the Cores guessed.", None),
23:("BAY, misfiled by one letter. Nobody caught it and the hive is occupied.", None),
24:("COCA-COLA. The archive holds a formula for the region and refuses to display it.", None),
25:("DISTORTED. Every image recovered is of somebody standing behind somebody else.", None),
26:("DISTORTED. Nothing here was ever recorded in daylight.", None),
27:("POUTINE, where the archive lists the squeak as a required property of the food.", None),
28:("ANACHRONISM. Filed as a period railway, so it has a coal tender and crosses a continent in an afternoon.", None),
29:("DISTORTED. The city and the meal are the same word and the Cores chose the meal.", None),
30:("DISTORTED. Every fragment is loud and none of it is dim.", None),
31:("BUFFALO BUFFALO BUFFALO. The line is grammatical, the Cores checked twice, and it produced animals.", None),
32:("SODA, and the same argument from the other side. The word belongs to the drink, and mixing to order beats anything sealed. Paired against Minnesota.", None),
}

LADDER = [("Still","0.00","suppression window"),("Settled","0.25","quiet league"),
          ("Unsettled","0.60","aggregate climbing"),("Rough","1.00","as authored"),
          ("Severe","1.40","near the threshold"),("Unreal","2.00","Criticality only")]

def esc(x): return html.escape(str(x or ''))

cards = []
flagged = 0
for i in range(1, 33):
    v, t = D[i], T[i]
    reading, alt = NOTES[i]
    if alt: flagged += 1
    base = ' · '.join(f'{k} {val:g}' for k, val in (v.get('effects') or {}).items())
    rows = []
    for w in v['weather']:
        cls = ' class="unreal"' if w.get('unrealOnly') else ''
        eff = ' · '.join(f'{k} {val:g}' for k, val in (w.get('effects') or {}).items()) or 'no change'
        rows.append(f'''<tr{cls}><th scope="row">{esc(w['label'])}</th>
        <td class="wtext">{esc(w['text'])}</td><td class="weff">{esc(eff)}</td></tr>''')
    settled = (i == 14)
    altBlock = ''
    if settled:
        altBlock = '''<div class="alt settled"><p class="alt-h">Settled — fan contribution</p>
        <p>The only venue in the book that is fixed. Red and white poppies, end zones marked
        by flower patches, gentle hills around the field for fans to picnic on.</p></div>'''
    if alt:
        altBlock = f'''<div class="alt"><p class="alt-h">Alternate reading — {esc(alt[0])}</p>
        <p>{esc(alt[1])}</p></div>'''
    cards.append(f'''<article class="venue{' flagged' if alt else ''}{' settled' if settled else ''}" id="t{i}">
      <header class="vhead">
        <p class="city">{esc(t['city'])} <span class="abbr">{esc(t['abbr'])}</span></p>
        <h3>{esc(v['name'])}</h3>
        <p class="team">{esc(t['name'])}</p>
      </header>
      <p class="setting">{esc(v['setting'])}</p>
      <p class="reading"><span class="rlabel">Built on</span> {esc(reading)}</p>
      <p class="base"><span class="rlabel">Always on</span> <span class="mono">{esc(base) or 'nothing'}</span></p>
      <table class="weather"><caption class="sr">Conditions at {esc(v['name'])}</caption>
        <tbody>{''.join(rows)}</tbody></table>
      {altBlock}
    </article>''')

jump = ''.join(f'<a href="#t{i}">{esc(T[i]["city"])}</a>' for i in range(1,33) if NOTES[i][1])
ladder = ''.join(f'<tr><th scope="row">{n}</th><td class="mono">{s}</td><td>{d}</td></tr>' for n,s,d in LADDER)

open(OUT,'w').write(f'''<title>The Venue Book</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Bitter:wght@500;700&family=Karla:ital,wght@0,400;0,600;1,400&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>
:root {{
  --paper:#E9EDF0; --card:#FDFDFC; --ink:#16202B; --mid:#5A6B78;
  --line:#C6D0D7; --accent:#2C6E8F; --accent-soft:#DCE8EE; --warn:#A8501C; --warn-soft:#F2E4D8;
}}
@media (prefers-color-scheme: dark) {{
  :root:not([data-theme="light"]) {{
    --paper:#0E151C; --card:#16202B; --ink:#DCE4EA; --mid:#8FA1AE;
    --line:#27353F; --accent:#6FB3CE; --accent-soft:#1B2C36; --warn:#E09256; --warn-soft:#2E2118;
  }}
}}
:root[data-theme="dark"] {{
  --paper:#0E151C; --card:#16202B; --ink:#DCE4EA; --mid:#8FA1AE;
  --line:#27353F; --accent:#6FB3CE; --accent-soft:#1B2C36; --warn:#E09256; --warn-soft:#2E2118;
}}
* {{ box-sizing:border-box; }}
body {{ background:var(--paper); color:var(--ink); font-family:Karla,system-ui,sans-serif;
  font-size:16px; line-height:1.55; margin:0; padding:clamp(20px,4vw,56px) clamp(16px,4vw,40px); }}
.wrap {{ max-width:1280px; margin:0 auto; display:flex; flex-direction:column; gap:40px; }}
.sr {{ position:absolute; width:1px; height:1px; overflow:hidden; clip:rect(0 0 0 0); }}
.mono {{ font-family:"IBM Plex Mono",ui-monospace,monospace; font-size:.78em; font-variant-numeric:tabular-nums; }}
header.mast {{ display:flex; flex-direction:column; gap:14px; border-bottom:2px solid var(--ink); padding-bottom:24px; }}
.eyebrow {{ font-family:"IBM Plex Mono",monospace; font-size:.72rem; letter-spacing:.16em;
  text-transform:uppercase; color:var(--accent); margin:0; }}
h1 {{ font-family:Bitter,Georgia,serif; font-weight:700; font-size:clamp(2rem,5vw,3.1rem);
  line-height:1.05; margin:0; text-wrap:balance; letter-spacing:-.015em; }}
.lede {{ max-width:64ch; margin:0; color:var(--mid); font-size:1.02rem; }}
.lede em {{ color:var(--ink); font-style:italic; }}
.panels {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(290px,1fr)); gap:24px; align-items:start; }}
.panel {{ background:var(--card); border:1px solid var(--line); padding:20px 22px; }}
.panel h2 {{ font-family:Bitter,Georgia,serif; font-size:1rem; margin:0 0 12px; letter-spacing:.01em; }}
.panel p {{ margin:0 0 10px; color:var(--mid); font-size:.9rem; }}
table.lad {{ border-collapse:collapse; width:100%; font-size:.85rem; }}
table.lad th {{ text-align:left; font-weight:600; padding:5px 10px 5px 0; white-space:nowrap; }}
table.lad td {{ padding:5px 0 5px 10px; color:var(--mid); border-top:1px solid var(--line); }}
table.lad tr:last-child th, table.lad tr:last-child td {{ color:var(--warn); font-weight:600; }}
.jump {{ display:flex; flex-wrap:wrap; gap:7px; }}
.jump a {{ font-family:"IBM Plex Mono",monospace; font-size:.74rem; color:var(--warn);
  background:var(--warn-soft); border:1px solid var(--warn); padding:3px 8px; text-decoration:none; }}
.jump a:hover, .jump a:focus-visible {{ background:var(--warn); color:var(--card); }}
.grid {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(370px,1fr)); gap:22px; }}
.venue {{ background:var(--card); border:1px solid var(--line); padding:22px 24px 24px;
  display:flex; flex-direction:column; gap:12px; }}
.venue.flagged {{ border-color:var(--warn); }}
.venue.settled {{ border-color:var(--accent); }}
.alt.settled {{ background:var(--accent-soft); border-left-color:var(--accent); }}
.alt.settled .alt-h {{ color:var(--accent); }}
.vhead {{ display:flex; flex-direction:column; gap:2px; }}
.city {{ font-family:"IBM Plex Mono",monospace; font-size:.74rem; letter-spacing:.1em;
  text-transform:uppercase; color:var(--mid); margin:0; }}
.abbr {{ color:var(--accent); }}
.venue h3 {{ font-family:Bitter,Georgia,serif; font-size:1.42rem; line-height:1.12; margin:2px 0 0;
  letter-spacing:-.01em; text-wrap:balance; }}
.team {{ margin:0; font-size:.9rem; font-weight:600; color:var(--accent); }}
.setting {{ margin:0; font-style:italic; color:var(--ink); font-size:.95rem; }}
.reading, .base {{ margin:0; font-size:.86rem; color:var(--mid); }}
.rlabel {{ font-family:"IBM Plex Mono",monospace; font-size:.68rem; letter-spacing:.12em;
  text-transform:uppercase; color:var(--accent); margin-right:6px; }}
table.weather {{ border-collapse:collapse; width:100%; font-size:.85rem; margin-top:2px; }}
table.weather th {{ text-align:left; font-weight:600; white-space:nowrap; vertical-align:top;
  padding:7px 12px 7px 0; border-top:1px solid var(--line); width:1%; }}
table.weather td {{ vertical-align:top; padding:7px 0; border-top:1px solid var(--line); color:var(--mid); }}
.weff {{ font-family:"IBM Plex Mono",monospace; font-size:.7rem; padding-left:12px !important;
  text-align:right; white-space:nowrap; color:var(--accent); }}
tr.unreal th {{ color:var(--warn); }}
tr.unreal td.wtext {{ color:var(--ink); }}
tr.unreal .weff {{ color:var(--warn); }}
.alt {{ background:var(--warn-soft); border-left:3px solid var(--warn); padding:12px 16px; margin-top:4px; }}
.alt p {{ margin:0; font-size:.87rem; color:var(--ink); }}
.alt-h {{ font-family:Bitter,Georgia,serif; font-weight:700; color:var(--warn);
  font-size:.82rem !important; margin-bottom:5px !important; }}
@media (max-width:560px) {{ .weff {{ display:none; }} .grid {{ grid-template-columns:1fr; }} }}
</style>
<div class="wrap">
<header class="mast">
  <p class="eyebrow">Reconstructed from fragmentary transmissions</p>
  <h1>The Venue Book</h1>
  <p class="lede">Thirty-two stadiums, each one a guess. The Cores do not know where these
  places were or what they looked like, so every venue is assembled from a team's name, its
  city, and a few garbled signals. That is why Cleveland ends up in a mine. <em>Weather is
  whatever is realistic for the setting</em>, and it worsens as the anomaly aggregate climbs.</p>
</header>
<section class="panels">
  <div class="panel">
    <h2>How the weather scales</h2>
    <p>Intensity rides the criticality dial each game already loads. Authored numbers are
    Rough strength; the scale stretches how far each effect sits from neutral.</p>
    <table class="lad"><tbody>{ladder}</tbody></table>
  </div>
  <div class="panel">
    <h2>What is settled</h2>
    <p><strong>Symmetric.</strong> A wet ball is wet for both teams. No weather effect is
    ever one-sided.</p>
    <p><strong>Announced before kickoff</strong>, so it is real input for pick-em and lineups.</p>
    <p><strong>Criticality hits hard</strong> — the top rung is meant to be disruptive, not
    a few percent.</p>
    <p><strong>Home advantage is separate</strong>, a flat small nudge. There is none in the
    sim today: 50.7% home wins over 687 games.</p>
  </div>
  <div class="panel">
    <h2>The city is never straight</h2>
    <p>A venue is not what a city is like. That is tourism, and it is what most of the
    first draft was. The Cores work from a damaged archive across an enormous gap in
    time, so a city arrives one of two ways.</p>
    <p><strong>Distorted</strong> — a real feature at the wrong scale, material or
    literalism. Chicago's mirrored monument comes back as a legume. Cleveland rocked, so
    the Cores filed it under geology and dug a mine.</p>
    <p><strong>Misdated</strong> — something from long after the sport, dated wrongly
    into it. Seoul's line has a coal tender and crosses a continent in an afternoon.</p>
    <p>The tell should be legible without being explained: something does not add up, and
    the Cores have not noticed.</p>
  </div>
  <div class="panel">
    <h2>Every city is now bent</h2>
    <p>All 31 unsettled venues are rewritten in the register above. Pittsburgh decoded as
    Carnegie Mellon, misheard into a crop. Anchorage flipped from a full moon to the
    midnight sun. Anaheim would not decode at all, so the failure to decode became the
    venue.</p>
    <p><strong>Kansas City is the exception</strong> and stays exactly as contributed.</p>
    <p><strong>Minnesota and Salt Lake City are one venue split in two.</strong> Both
    teams are named for the dispute over what the drink is called, so their stadiums are
    written against each other: bottle versus fountain, sealed versus mixed to order.</p>
    
  </div>
</section>
<section class="grid">{''.join(cards)}</section>
</div>''')
print(f'wrote {OUT} ({len(cards)} venues, {flagged} flagged)')
