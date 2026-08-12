"""Contrast check for team marks — run while editing colors in config.json.

A club's avatar is painted in its PRIMARY and SECONDARY only (avatar_generator paints the
field in one and the heraldic figure in the other), so those two colors have to differ in
LUMINANCE, not just in hue. Two colors can look completely different to the eye and still
be the same brightness — at which point the pattern disappears and the mark is a flat disc.
That is not hypothetical: San Diego currently sits at 1.0:1, which is exactly that.

    .venv/bin/python tools_team_contrast.py           # everything under the bar
    .venv/bin/python tools_team_contrast.py --all     # every club, sorted
    .venv/bin/python tools_team_contrast.py --fix SND # candidate fixes for one club

Bar is 3.0:1. Marks render as small as 20px in the standings, and below 3.0 the pattern
starts to mush at that size; below 2.0 it is effectively gone.

⚠️ `logoInvert` does NOT help here. It swaps which color paints field vs figure, so it
changes the look but not the luminance gap — a low-contrast pair stays low-contrast.
"""
import sys, json, colorsys

BAR = 3.0
POOR = 2.0


def lum(h):
    h = h.lstrip('#')
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    f = lambda c: c / 12.92 if c <= .03928 else ((c + .055) / 1.055) ** 2.4
    return .2126 * f(r) + .7152 * f(g) + .0722 * f(b)


def ratio(a, b):
    l1, l2 = sorted((lum(a), lum(b)), reverse=True)
    return (l1 + .05) / (l2 + .05)


def hexToHls(h):
    h = h.lstrip('#')
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    return colorsys.rgb_to_hls(r, g, b)


def hlsToHex(hh, l, s):
    r, g, b = colorsys.hls_to_rgb(hh, max(0, min(1, l)), max(0, min(1, s)))
    return '#{:02X}{:02X}{:02X}'.format(round(r * 255), round(g * 255), round(b * 255))


teams = json.load(open('config.json'))['teams']
args = sys.argv[1:]

if '--fix' in args:
    want = args[args.index('--fix') + 1].upper()
    t = next((x for x in teams if x['abbr'].upper() == want), None)
    if not t:
        print(f"no club with abbr {want}")
        raise SystemExit(1)
    p, sec = t['color'], t['secondaryColor']
    print(f"{t['abbr']} {t['city']} {t['name']}")
    print(f"  primary   {p}")
    print(f"  secondary {sec}   -> {ratio(p, sec):.1f}:1\n")
    print("  Candidates keep the secondary's HUE and move its lightness, so the club keeps")
    print("  its color identity and only the brightness gap changes.\n")
    h, l, s = hexToHls(sec)
    seen = set()
    for dl in [x / 100 for x in range(-60, 65, 5)]:
        cand = hlsToHex(h, l + dl, s)
        r = ratio(p, cand)
        if r >= BAR and cand not in seen:
            seen.add(cand)
            way = 'darker ' if dl < 0 else 'lighter'
            print(f"    {way} {cand}  -> {r:4.1f}:1")
    if not seen:
        print("    Nothing at this hue clears the bar — the PRIMARY needs to move instead,")
        print("    or the secondary needs a different hue.")
    raise SystemExit(0)

rows = sorted(((ratio(t['color'], t['secondaryColor']), i, t) for i, t in enumerate(teams)))
showAll = '--all' in args
shown = rows if showAll else [r for r in rows if r[0] < BAR]

print(f"{len(rows)} clubs, {sum(1 for r in rows if r[0] < BAR)} under {BAR}:1"
      f", {sum(1 for r in rows if r[0] < POOR)} under {POOR}:1\n")
for r, i, t in shown:
    sev = 'LOW ' if r < POOR else ('thin' if r < BAR else '    ')
    print(f"  {sev} {t['abbr']:4} {t['city']} {t['name']:20} "
          f"{t['color']} / {t['secondaryColor']}  {r:4.1f}:1")
if not showAll and shown:
    print(f"\n  --fix <ABBR> for candidates, --all for every club")
