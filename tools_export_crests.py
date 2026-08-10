#!/usr/bin/env python3
"""Export every club crest (and the league mark) as a large PNG for social media.

    python3 tools_export_crests.py [--size 1024] [--out exports/crests-1024]

⚠️ Rasterised through HEADLESS CHROME, not cairosvg. cairosvg needs a native cairo
library that is not installed on this machine, and pulling one in for an occasional
artwork export is not a trade worth making. Chrome is already a dependency of the
workflow here.

⚠️ The SVGs are served through the DEV SERVER rather than loaded as file:// URLs —
Chrome's file:// handling of standalone SVG is inconsistent, and the dev server is
already running. It must be up on :3000.

Output is transparent PNG: the crest is a circle, so a baked-in background would
show as square corners against anything that is not the same colour.
"""
import argparse, json, os, re, shutil, subprocess, sys, struct

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
STAGING = "../floosball-react/public/_crestexport"   # inside the dev server's web root


def slug(team):
    return re.sub(r'[^a-z0-9]+', '-', f"{team['city']} {team['name']}".lower()).strip('-')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--size', type=int, default=1024)
    ap.add_argument('--out', default=None)
    args = ap.parse_args()
    out = args.out or f'exports/crests-{args.size}'

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from avatar_generator import AvatarGenerator

    cfg = json.load(open('config.json'))
    gen = AvatarGenerator()
    os.makedirs(STAGING, exist_ok=True)
    os.makedirs(out, exist_ok=True)

    jobs = [('00-floosball-league',
             gen.generateLeagueLogo(args.size, [t['color'] for t in cfg['teams']]))]
    for i, t in enumerate(cfg['teams'], start=1):
        jobs.append((f"{i:02d}-{slug(t)}",
                     gen.generateTeamAvatar(t['name'], t['color'], t['secondaryColor'],
                                            t['tertiaryColor'], args.size, i, False)))

    for name, svg in jobs:
        open(f'{STAGING}/{name}.svg', 'w').write(svg)

    ok = 0
    try:
        for name, _ in jobs:
            dest = f'{out}/{name}.png'
            subprocess.run([CHROME, '--headless', '--disable-gpu', f'--screenshot={dest}',
                            f'--window-size={args.size},{args.size}',
                            '--default-background-color=00000000', '--hide-scrollbars',
                            f'http://localhost:3000/_crestexport/{name}.svg'],
                           capture_output=True)
            # Verify rather than trust: a Chrome that failed to load still exits 0.
            with open(dest, 'rb') as f:
                head = f.read(26)
            w, h = struct.unpack('>II', head[16:24])
            assert (w, h) == (args.size, args.size) and head[25] == 6, f'{name}: {w}x{h} type={head[25]}'
            ok += 1
    finally:
        shutil.rmtree(STAGING, ignore_errors=True)

    print(f'{ok}/{len(jobs)} PNGs written to {out}/ at {args.size}px, transparent RGBA')


if __name__ == '__main__':
    main()
