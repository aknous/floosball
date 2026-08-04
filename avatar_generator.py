"""
Team Avatar Generator
Generates SVG avatars for teams using team colors and caches them.
Avatars are persisted to disk for reuse across server restarts.
"""

import hashlib
import math
from typing import Dict, List, Optional
import logging
import os

logger = logging.getLogger(__name__)


class AvatarGenerator:
    """Generates and caches team avatars as SVG with disk persistence"""
    
    def __init__(self, cacheDir: str = "data/avatars"):
        self.cache: Dict[str, str] = {}
        self.cacheDir = cacheDir
        
        # Create cache directory if it doesn't exist
        if not os.path.exists(cacheDir):
            os.makedirs(cacheDir)
            logger.info(f"Created avatar cache directory: {cacheDir}")
        
    def generateTeamAvatar(self, teamName: str, primaryColor: str, secondaryColor: str, tertiaryColor: str,
                           size: int = 32, teamId: int = None, logoInvert: bool = False) -> str:
        """
        Generate a marble-style SVG avatar for a team
        
        Args:
            teamName: Team name (used as seed for consistent generation)
            primaryColor: Primary team color (hex)
            secondaryColor: Secondary team color (hex)
            tertiaryColor: Tertiary team color (hex)
            size: Size of the avatar in pixels
            teamId: Team ID (used for sequential pattern assignment)
            
        Returns:
            SVG string
        """
        # Create cache key
        cacheKey = self._getCacheKey(teamName, primaryColor, secondaryColor, tertiaryColor, size, logoInvert)
        
        # Check memory cache first
        if cacheKey in self.cache:
            logger.debug(f"Returning memory-cached avatar for {teamName}")
            return self.cache[cacheKey]
        
        # Check disk cache
        filePath = self._getCacheFilePath(cacheKey)
        if os.path.exists(filePath):
            logger.debug(f"Loading avatar from disk for {teamName}")
            with open(filePath, 'r') as f:
                svg = f.read()
            # Store in memory cache for faster future access
            self.cache[cacheKey] = svg
            return svg
        
        # Generate new avatar
        svg = self._generateMarbleSvg(teamName, primaryColor, secondaryColor, tertiaryColor, size, teamId, logoInvert)
        
        # Save to disk
        self._saveToDisk(cacheKey, svg)
        
        # Cache in memory
        self.cache[cacheKey] = svg
        logger.info(f"Generated and cached avatar for {teamName}")
        
        return svg
    
    def _getCacheFilePath(self, cacheKey: str) -> str:
        """Get file path for cached avatar"""
        return os.path.join(self.cacheDir, f"{cacheKey}.svg")
    
    def getPng(self, teamName: str, primaryColor: str, secondaryColor: str, tertiaryColor: str,
               size: int = 256, teamId: int = None, logoInvert: bool = False) -> bytes:
        """Generate or return cached PNG avatar for a team."""
        cacheKey = self._getCacheKey(teamName, primaryColor, secondaryColor, tertiaryColor, size, logoInvert)
        pngPath = os.path.join(self.cacheDir, f"{cacheKey}.png")

        # Check disk cache
        if os.path.exists(pngPath):
            with open(pngPath, 'rb') as f:
                return f.read()

        # Generate SVG first, then convert
        svg = self.generateTeamAvatar(teamName, primaryColor, secondaryColor, tertiaryColor, size, teamId, logoInvert)
        import cairosvg
        pngBytes = cairosvg.svg2png(bytestring=svg.encode('utf-8'), output_width=size, output_height=size)

        # Cache to disk
        try:
            with open(pngPath, 'wb') as f:
                f.write(pngBytes)
        except Exception as e:
            logger.error(f"Failed to save PNG to disk: {e}")

        return pngBytes

    def generateLeagueLogo(self, size: int = 256, teamColors: Optional[List[str]] = None) -> str:
        """Generate the Floosball league logo as SVG — pie chart of team colors with football overlay."""
        cx, cy, r = 16, 16, 16

        if teamColors and len(teamColors) >= 2:
            sliceCount = len(teamColors)
            sliceAngle = 360.0 / sliceCount
            slices = []
            for i, color in enumerate(teamColors):
                startDeg = i * sliceAngle - 90  # start from top
                endDeg = startDeg + sliceAngle
                startRad = math.radians(startDeg)
                endRad = math.radians(endDeg)
                x1 = cx + r * math.cos(startRad)
                y1 = cy + r * math.sin(startRad)
                x2 = cx + r * math.cos(endRad)
                y2 = cy + r * math.sin(endRad)
                largeArc = 1 if sliceAngle > 180 else 0
                slices.append(
                    f'  <path d="M{cx},{cy} L{x1:.2f},{y1:.2f} A{r},{r} 0 {largeArc},1 {x2:.2f},{y2:.2f} Z" fill="{color}"/>'
                )
            background = "\n".join(slices)
        else:
            background = f'  <circle cx="{cx}" cy="{cy}" r="{r}" fill="#3b82f6"/>'

        return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 32 32">
{background}
  <g transform="rotate(-45 16 16)">
    <ellipse cx="16" cy="16" rx="10" ry="6.5" fill="#e2e8f0"/>
    <line x1="6" y1="16" x2="26" y2="16" stroke="#1e293b" stroke-width="1.2"/>
    <line x1="13" y1="13.2" x2="13" y2="18.8" stroke="#1e293b" stroke-width="1"/>
    <line x1="16" y1="12.5" x2="16" y2="19.5" stroke="#1e293b" stroke-width="1"/>
    <line x1="19" y1="13.2" x2="19" y2="18.8" stroke="#1e293b" stroke-width="1"/>
  </g>
</svg>'''

    def getLeagueLogoPng(self, size: int = 256, teamColors: Optional[List[str]] = None) -> bytes:
        """Generate or return cached PNG of the league logo."""
        colorHash = hashlib.md5(",".join(teamColors or []).encode()).hexdigest()[:8]
        pngPath = os.path.join(self.cacheDir, f"league_logo_{size}_{colorHash}.png")
        if os.path.exists(pngPath):
            with open(pngPath, 'rb') as f:
                return f.read()
        svg = self.generateLeagueLogo(size, teamColors)
        import cairosvg
        pngBytes = cairosvg.svg2png(bytestring=svg.encode('utf-8'), output_width=size, output_height=size)
        try:
            with open(pngPath, 'wb') as f:
                f.write(pngBytes)
        except Exception as e:
            logger.error(f"Failed to save league logo PNG: {e}")
        return pngBytes

    def clearCache(self):
        """Clear both memory and disk cache"""
        # Clear memory cache
        self.cache.clear()
        logger.info("Cleared avatar memory cache")

        # Clear disk cache
        if os.path.exists(self.cacheDir):
            for file in os.listdir(self.cacheDir):
                if file.endswith('.svg') or file.endswith('.png'):
                    filePath = os.path.join(self.cacheDir, file)
                    os.remove(filePath)
            logger.info(f"Cleared avatar disk cache in {self.cacheDir}")
    
    def _saveToDisk(self, cacheKey: str, svg: str) -> None:
        """Save SVG to disk cache"""
        try:
            filePath = self._getCacheFilePath(cacheKey)
            with open(filePath, 'w') as f:
                f.write(svg)
            logger.debug(f"Saved avatar to disk: {filePath}")
        except Exception as e:
            logger.error(f"Failed to save avatar to disk: {e}")
    
    def _getCacheKey(self, teamName: str, primaryColor: str, secondaryColor: str, tertiaryColor: str,
                     size: int, logoInvert: bool = False) -> str:
        """Generate a cache key from team data"""
        data = f"{teamName}|{primaryColor}|{secondaryColor}|{tertiaryColor}|{size}|{int(bool(logoInvert))}"
        return hashlib.md5(data.encode()).hexdigest()
    
    def _generateMarbleSvg(self, seed: str, color1: str, color2: str, color3: str, size: int,
                           teamId: int = None, logoInvert: bool = False) -> str:
        """
        Generate medieval banner-style SVG with patterns using two colors.
        Patterns include various heraldic designs for visual variety.
        Pattern is sequentially assigned based on team ID.
        """
        # Choose pattern sequentially based on team ID, or fallback to hash.
        # 32 patterns for 32 clubs — one each, no repeats. At 24 the league outgrew the
        # set on expansion and team IDs 25-32 silently drew the same marks as 1-8.
        if teamId is not None:
            patternType = (teamId - 1) % 32  # team IDs start at 1
        else:
            patternHash = int(hashlib.md5(seed.encode()).hexdigest(), 16)
            patternType = patternHash % 32
        
        # Remove # from hex colors if present
        c1 = color1.lstrip('#')
        c2 = color2.lstrip('#')
        # logoInvert: paint the field in the SECONDARY and the figure in the primary.
        # A club that swaps its two colours can set this to keep the mark looking
        # exactly as it did, while kits and team pages pick up the new primary.
        if logoInvert:
            c1, c2 = c2, c1
        c3 = color3.lstrip('#')
        
        # Generate unique ID for pattern definition
        patternId = hashlib.md5(f"{seed}{color1}{color2}pattern".encode()).hexdigest()[:8]
        
        # Every pattern is wrapped in a common SVG frame with a circle clipPath.
        # This ensures the circle clipping is done by the SVG itself (not CSS border-radius),
        # eliminating sub-pixel anti-aliasing mismatches that cause off-center appearance.
        half = size / 2
        clipId = f"clip{patternId}"
        extraDefs = ""  # Pattern-specific defs (patterns that use <pattern> elements)
        content = ""    # Pattern-specific inner elements

        if patternType == 0:
            # Nested diamonds - background, large diamond ring, small inner diamond
            o1 = size * 0.1   # outer diamond tip (10%)
            o2 = size * 0.9   # outer diamond tip (90%)
            i1 = size * 0.3   # inner diamond tip (30%)
            i2 = size * 0.7   # inner diamond tip (70%)
            content = f'''<rect width="{size}" height="{size}" fill="#{c1}"/>
                <polygon points="{half},{o1:.1f} {o2:.1f},{half} {half},{o2:.1f} {o1:.1f},{half}" fill="#{c2}"/>
                <polygon points="{half},{i1:.1f} {i2:.1f},{half} {half},{i2:.1f} {i1:.1f},{half}" fill="#{c1}"/>'''

        elif patternType == 1:
            # Cross pattern (Nordic cross style)
            cw = size / 5
            content = f'''<rect width="{size}" height="{size}" fill="#{c2}"/>
                <rect x="{(size - cw)/2:.2f}" y="0" width="{cw:.2f}" height="{size}" fill="#{c1}"/>
                <rect x="0" y="{(size - cw)/2:.2f}" width="{size}" height="{cw:.2f}" fill="#{c1}"/>'''

        elif patternType == 2:
            # Per chevron - c1 top, c2 bottom separated by an upward-pointing V
            apexY = size * 0.38
            footY = size * 0.65
            content = f'''<rect width="{size}" height="{size}" fill="#{c2}"/>
                <polygon points="0,{footY:.1f} {half:.1f},{apexY:.1f} {size},{footY:.1f} {size},{size} 0,{size}" fill="#{c1}"/>'''

        elif patternType == 3:
            # Three pales - three thin vertical bands on background
            pw = size * 0.1
            gap = (size - 3 * pw) / 4
            content = f'''<rect width="{size}" height="{size}" fill="#{c1}"/>
                <rect x="{gap:.1f}" y="0" width="{pw:.1f}" height="{size}" fill="#{c2}"/>
                <rect x="{gap*2 + pw:.1f}" y="0" width="{pw:.1f}" height="{size}" fill="#{c2}"/>
                <rect x="{gap*3 + pw*2:.1f}" y="0" width="{pw:.1f}" height="{size}" fill="#{c2}"/>'''

        elif patternType == 4:
            # Quartered (4 quadrants alternating colors)
            content = f'''<rect width="{size}" height="{size}" fill="#{c1}"/>
                <rect x="0" y="0" width="{half}" height="{half}" fill="#{c2}"/>
                <rect x="{half}" y="{half}" width="{half}" height="{half}" fill="#{c2}"/>'''

        elif patternType == 5:
            # Saltire (X cross)
            cw = size / 9
            content = f'''<rect width="{size}" height="{size}" fill="#{c2}"/>
                <path d="M 0 0 L {cw * 1.5:.2f} 0 L {size} {size - cw * 1.5:.2f} L {size} {size} L {size - cw * 1.5:.2f} {size} L 0 {cw * 1.5:.2f} Z" fill="#{c1}"/>
                <path d="M {size} 0 L {size} {cw * 1.5:.2f} L {cw * 1.5:.2f} {size} L 0 {size} L 0 {size - cw * 1.5:.2f} L {size - cw * 1.5:.2f} 0 Z" fill="#{c1}"/>'''

        elif patternType == 6:
            # Double chevron. The arms are drawn PAST the square on both sides and then
            # clipped by the circle, so each one meets the rim cleanly. Terminating them
            # at x=0 and x=size left the butt cap sitting inside the circle at that height
            # (at y=0.42*size the rim is ~0.6px in, not 0), which read as a notch where the
            # chevron met the outline.
            sw = size * 0.16
            over = 0.25                      # how far past each edge to run the arms
            slope = (0.42 - 0.16) / 0.5      # arm gradient, in units of size
            yTop, yBot = 0.42, 0.82
            yTopEdge = yTop + over * slope
            yBotEdge = yBot + over * slope
            content = f'''<rect width="{size}" height="{size}" fill="#{c1}"/>
                <polyline points="{-over*size:.1f},{yTopEdge*size:.1f} {half:.1f},{size*0.16:.1f} {(1+over)*size:.1f},{yTopEdge*size:.1f}" stroke="#{c2}" stroke-width="{sw:.1f}" fill="none" stroke-linejoin="miter"/>
                <polyline points="{-over*size:.1f},{yBotEdge*size:.1f} {half:.1f},{size*0.56:.1f} {(1+over)*size:.1f},{yBotEdge*size:.1f}" stroke="#{c2}" stroke-width="{sw:.1f}" fill="none" stroke-linejoin="miter"/>'''

        elif patternType == 7:
            # Meshing bands - 5 pairs where c1 goes thick→thin (top→bottom) and c2 goes thin→thick
            # Both colors have equal total coverage; bands are equal at the midpoint
            mbR = 0.55
            mbN = 5
            mbSum = sum(mbR ** i for i in range(mbN))
            mbH = size / (2 * mbSum)
            mbBands = ''
            mbY = 0.0
            for i in range(mbN):
                h1 = mbH * (mbR ** i)
                h2 = mbH * (mbR ** (mbN - 1 - i))
                mbBands += f'<rect x="0" y="{mbY:.2f}" width="{size}" height="{h1:.2f}" fill="#{c1}"/>'
                mbY += h1
                mbBands += f'<rect x="0" y="{mbY:.2f}" width="{size}" height="{h2:.2f}" fill="#{c2}"/>'
                mbY += h2
            content = mbBands

        elif patternType == 8:
            # Ruffle (nebuly) - a scalloped division, all curves and no straight edges.
            # Owned by the Blouses; the isometric cube that used to sit here read as
            # technical drawing, which is the wrong register for that club entirely.
            n = 5
            w = size / n
            r = w / 2
            midY = size * 0.47
            arcs = "".join(
                f" A {r:.1f},{r:.1f} 0 0,1 {(i + 1) * w:.1f},{midY:.1f}" for i in range(n)
            )
            skirt = (f"M 0,{size} L 0,{midY:.1f}{arcs} L {size},{size} Z")
            # A second, smaller scalloped hem inside it for the layered look.
            n2 = 7
            w2 = size / n2
            r2 = w2 / 2
            lowY = size * 0.72
            arcs2 = "".join(
                f" A {r2:.1f},{r2:.1f} 0 0,1 {(i + 1) * w2:.1f},{lowY:.1f}" for i in range(n2)
            )
            hem = (f"M 0,{size} L 0,{lowY:.1f}{arcs2} L {size},{size} Z")
            content = (
                f'<rect width="{size}" height="{size}" fill="#{c1}"/>'
                f'<path d="{skirt}" fill="#{c2}"/>'
                f'<path d="{hem}" fill="#{c1}" opacity="0.35"/>'
            )

        elif patternType == 9:
            # 4-pointed star - diamond with sides curved inward (f=0.7)
            f = 0.7
            cp1 = (half*(3-f)/2, half*(1+f)/2)
            cp2 = (half*(3-f)/2, half*(3-f)/2)
            cp3 = (half*(1+f)/2, half*(3-f)/2)
            cp4 = (half*(1+f)/2, half*(1+f)/2)
            starPath = (f'M {half},{0} '
                        f'Q {cp1[0]:.2f},{cp1[1]:.2f} {size},{half} '
                        f'Q {cp2[0]:.2f},{cp2[1]:.2f} {half},{size} '
                        f'Q {cp3[0]:.2f},{cp3[1]:.2f} {0},{half} '
                        f'Q {cp4[0]:.2f},{cp4[1]:.2f} {half},{0} Z')
            content = f'''<rect width="{size}" height="{size}" fill="#{c2}"/>
                <path d="{starPath}" fill="#{c1}"/>'''

        elif patternType == 10:
            # Split vertically (per pale)
            content = f'''<rect width="{size}" height="{size}" fill="#{c1}"/>
                <rect x="{half}" y="0" width="{half}" height="{size}" fill="#{c2}"/>'''

        elif patternType == 11:
            # Split horizontally (per fess)
            content = f'''<rect width="{size}" height="{size}" fill="#{c1}"/>
                <rect x="0" y="{half}" width="{size}" height="{half}" fill="#{c2}"/>'''

        elif patternType == 12:
            # Zigzag (dancetty)
            s = size
            amp = s * 0.19
            midY = s * 0.5
            nTeeth = 4
            zagPts = [f"0,{midY + amp:.1f}"]
            for i in range(nTeeth):
                xPeak = (2 * i + 1) * s / (2 * nTeeth)
                xValley = (i + 1) * s / nTeeth
                zagPts.append(f"{xPeak:.1f},{midY - amp:.1f}")
                if i < nTeeth - 1:
                    zagPts.append(f"{xValley:.1f},{midY + amp:.1f}")
            zagPts.append(f"{s:.1f},{midY + amp:.1f}")
            bottomPoints = ' '.join(zagPts) + f" {s},{s} 0,{s}"
            content = f'''<rect width="{size}" height="{size}" fill="#{c1}"/>
                <polygon points="{bottomPoints}" fill="#{c2}"/>'''

        elif patternType == 13:
            # Diamond (lozengy)
            d = size / 3
            extraDefs = f'''<pattern id="loz{patternId}" width="{d}" height="{d}" patternUnits="userSpaceOnUse">
                        <rect width="{d}" height="{d}" fill="#{c1}"/>
                        <polygon points="{d/2},0 {d},{d/2} {d/2},{d} 0,{d/2}" fill="#{c2}"/>
                    </pattern>'''
            content = f'<rect width="{size}" height="{size}" fill="url(#loz{patternId})"/>'

        elif patternType == 14:
            # Single diagonal stripe (bend)
            bw = size * 0.36
            content = f'''<rect width="{size}" height="{size}" fill="#{c1}"/>
                <rect x="{half - bw/2:.1f}" y="-{size:.1f}" width="{bw:.1f}" height="{size * 3:.1f}" transform="rotate(45 {half} {half})" fill="#{c2}"/>'''

        elif patternType == 15:
            # Gyronny - 8 pie-slice triangles
            s = size
            cx, cy = half, half
            perimPts = [(cx, 0), (s, 0), (s, cy), (s, s), (cx, s), (0, s), (0, cy), (0, 0)]
            content = ''.join([
                f'<polygon points="{cx},{cy} {perimPts[i][0]},{perimPts[i][1]} {perimPts[(i+1)%8][0]},{perimPts[(i+1)%8][1]}" fill="#{c1 if i % 2 == 0 else c2}"/>'
                for i in range(8)
            ])

        elif patternType == 16:
            # Pile - triangle pointing down from top
            content = f'''<rect width="{size}" height="{size}" fill="#{c1}"/>
                <polygon points="0,0 {size},0 {half},{size}" fill="#{c2}"/>'''

        elif patternType == 17:
            # Per bend sinister - diagonal split
            content = f'''<rect width="{size}" height="{size}" fill="#{c1}"/>
                <polygon points="0,0 {size},0 0,{size}" fill="#{c2}"/>'''

        elif patternType == 18:
            # Concave octagon - 8 vertices at 45° intervals, each side bows gently inward (30% pull toward center)
            s = size
            octPath = (
                f'M {half:.1f},{s*0.083:.1f} '
                f'Q {s*0.6:.1f},{s*0.25:.1f} {s*0.792:.1f},{s*0.208:.1f} '
                f'Q {s*0.75:.1f},{s*0.4:.1f} {s*0.917:.1f},{half:.1f} '
                f'Q {s*0.75:.1f},{s*0.6:.1f} {s*0.792:.1f},{s*0.792:.1f} '
                f'Q {s*0.6:.1f},{s*0.75:.1f} {half:.1f},{s*0.917:.1f} '
                f'Q {s*0.4:.1f},{s*0.75:.1f} {s*0.208:.1f},{s*0.792:.1f} '
                f'Q {s*0.25:.1f},{s*0.6:.1f} {s*0.083:.1f},{half:.1f} '
                f'Q {s*0.25:.1f},{s*0.4:.1f} {s*0.208:.1f},{s*0.208:.1f} '
                f'Q {s*0.4:.1f},{s*0.25:.1f} {half:.1f},{s*0.083:.1f} Z'
            )
            content = f'''<rect width="{size}" height="{size}" fill="#{c2}"/>
                <path d="{octPath}" fill="#{c1}"/>'''

        elif patternType == 19:
            # Bendy sinister - diagonal bands (top-right to bottom-left, / direction)
            extraDefs = f'''<pattern id="bendsin{patternId}" width="{size/3:.2f}" height="{size/3:.2f}" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
                        <rect width="{size/6:.2f}" height="{size/3:.2f}" fill="#{c1}"/>
                        <rect x="{size/6:.2f}" width="{size/6:.2f}" height="{size/3:.2f}" fill="#{c2}"/>
                    </pattern>'''
            content = f'<rect width="{size}" height="{size}" fill="url(#bendsin{patternId})"/>'

        elif patternType == 20:
            # Per saltire - X division into 4 triangles
            s = size
            cx, cy = half, half
            content = f'''<polygon points="{cx},{cy} 0,0 {s},0" fill="#{c1}"/>
                <polygon points="{cx},{cy} {s},0 {s},{s}" fill="#{c2}"/>
                <polygon points="{cx},{cy} {s},{s} 0,{s}" fill="#{c1}"/>
                <polygon points="{cx},{cy} 0,{s} 0,0" fill="#{c2}"/>'''

        elif patternType == 21:
            # 6 bold spokes - lines radiating from center at 60° intervals
            sw = size * 0.12
            spokes = ''.join([
                f'<line x1="{half:.1f}" y1="{half:.1f}" x2="{half:.1f}" y2="0" stroke="#{c2}" stroke-width="{sw:.1f}" transform="rotate({angle},{half:.1f},{half:.1f})"/>'
                for angle in range(0, 360, 60)
            ])
            content = f'<rect width="{size}" height="{size}" fill="#{c1}"/>{spokes}'

        elif patternType == 22:
            # Wavy (undé)
            s = size
            midY = s * 0.5
            amp = s * 0.14
            wavePath = (
                f"M 0,{s} "
                f"L 0,{midY:.1f} "
                f"Q {s*0.25:.1f},{midY - amp:.1f} {s*0.5:.1f},{midY:.1f} "
                f"Q {s*0.75:.1f},{midY + amp:.1f} {s:.1f},{midY:.1f} "
                f"L {s},{s} Z"
            )
            content = f'''<rect width="{size}" height="{size}" fill="#{c1}"/>
                <path d="{wavePath}" fill="#{c2}"/>'''

        elif patternType == 24:
            # Bullseye - concentric rings. Nothing else in the set is radial-symmetric.
            content = f'''<rect width="{size}" height="{size}" fill="#{c1}"/>
                <circle cx="{half}" cy="{half}" r="{size * 0.40:.1f}" fill="#{c2}"/>
                <circle cx="{half}" cy="{half}" r="{size * 0.26:.1f}" fill="#{c1}"/>
                <circle cx="{half}" cy="{half}" r="{size * 0.12:.1f}" fill="#{c2}"/>'''

        elif patternType == 25:
            # Chequy - a 4x4 checkerboard. The only grid in the set.
            cell = size / 4
            squares = "".join(
                f'<rect x="{c * cell:.1f}" y="{r * cell:.1f}" width="{cell:.1f}" '
                f'height="{cell:.1f}" fill="#{c2}"/>'
                for r in range(4) for c in range(4) if (r + c) % 2
            )
            content = f'<rect width="{size}" height="{size}" fill="#{c1}"/>{squares}'

        elif patternType == 26:
            # Honeycomb - seven hexagons, one ringed by six. Still the "loose shapes"
            # idea, but hexagons tile visually where circles read as dice pips.
            hr = size * 0.152
            step = hr * 1.74
            centres = [(half, half)] + [
                (half + step * math.cos(math.radians(60 * k)),
                 half + step * math.sin(math.radians(60 * k)))
                for k in range(6)
            ]
            hexes = ""
            for cx, cy in centres:
                pts = " ".join(
                    f"{cx + hr * math.cos(math.radians(60 * v + 90)):.1f},"
                    f"{cy + hr * math.sin(math.radians(60 * v + 90)):.1f}"
                    for v in range(6)
                )
                hexes += f'<polygon points="{pts}" fill="#{c2}"/>'
            content = f'<rect width="{size}" height="{size}" fill="#{c1}"/>{hexes}'

        elif patternType == 27:
            # Crescent - a disc with a second disc bitten out of it.
            content = f'''<rect width="{size}" height="{size}" fill="#{c1}"/>
                <circle cx="{half}" cy="{half}" r="{size * 0.38:.1f}" fill="#{c2}"/>
                <circle cx="{size * 0.62:.1f}" cy="{size * 0.40:.1f}" r="{size * 0.32:.1f}" fill="#{c1}"/>'''

        elif patternType == 28:
            # Spiral - an Archimedean coil. The only curve-based mark in the set.
            turns, steps = 3.0, 96
            maxR = size * 0.42
            pts = []
            for i in range(steps + 1):
                th = (i / steps) * turns * 2 * math.pi
                rr = maxR * (i / steps)
                pts.append(f"{half + rr * math.cos(th):.1f},{half + rr * math.sin(th):.1f}")
            content = (f'<rect width="{size}" height="{size}" fill="#{c1}"/>'
                       f'<polyline points="{" ".join(pts)}" fill="none" stroke="#{c2}" '
                       f'stroke-width="{size * 0.105:.1f}" stroke-linecap="round"/>')

        elif patternType == 29:
            # Sunrise - rays fanning from the base, not from the centre.
            rays = 7
            wedges = ""
            for i in range(rays):
                if i % 2:
                    continue
                a1 = math.pi * (i / rays)
                a2 = math.pi * ((i + 1) / rays)
                L = size * 1.45
                x1, y1 = half - L * math.cos(a1), size - L * math.sin(a1)
                x2, y2 = half - L * math.cos(a2), size - L * math.sin(a2)
                wedges += (f'<polygon points="{half},{size} {x1:.1f},{y1:.1f} '
                           f'{x2:.1f},{y2:.1f}" fill="#{c2}"/>')
            content = f'<rect width="{size}" height="{size}" fill="#{c1}"/>{wedges}'

        elif patternType == 30:
            # Peaks - a three-summit range. The existing "pile" is one triangle, not a skyline.
            base = size * 1.02
            peaks = "".join(
                f'<polygon points="{cx * size - size * 0.30:.1f},{base:.1f} '
                f'{cx * size:.1f},{py * size:.1f} {cx * size + size * 0.30:.1f},{base:.1f}" '
                f'fill="#{c2}"/>'
                for cx, py in [(0.22, 0.52), (0.78, 0.46), (0.5, 0.28)]
            )
            content = f'<rect width="{size}" height="{size}" fill="#{c1}"/>{peaks}'

        elif patternType == 31:
            # Orbit - an open ring with a satellite riding it.
            content = f'''<rect width="{size}" height="{size}" fill="#{c1}"/>
                <circle cx="{half}" cy="{half}" r="{size * 0.31:.1f}" fill="none"
                        stroke="#{c2}" stroke-width="{size * 0.085:.1f}"/>
                <circle cx="{half}" cy="{size * 0.19:.1f}" r="{size * 0.125:.1f}" fill="#{c2}"/>'''

        else:
            # Pale - single bold vertical band
            pw = size * 0.32
            content = f'''<rect width="{size}" height="{size}" fill="#{c1}"/>
                <rect x="{(size - pw) / 2:.1f}" y="0" width="{pw:.1f}" height="{size}" fill="#{c2}"/>'''

        svg = f'''<svg width="{size}" height="{size}" viewBox="0 0 {size} {size}" xmlns="http://www.w3.org/2000/svg">
            <defs>
                <clipPath id="{clipId}"><circle cx="{half}" cy="{half}" r="{half}"/></clipPath>
                {extraDefs}
            </defs>
            <g clip-path="url(#{clipId})">
                {content}
            </g>
        </svg>'''

        return svg
    
    def clearCache(self):
        """Clear the avatar cache (memory only)"""
        self.cache.clear()
        logger.info("Avatar memory cache cleared")
    
    def clearDiskCache(self):
        """Clear all cached avatars from disk"""
        try:
            import glob
            files = glob.glob(os.path.join(self.cacheDir, "*.svg"))
            for f in files:
                os.remove(f)
            logger.info(f"Cleared {len(files)} avatars from disk cache")
        except Exception as e:
            logger.error(f"Failed to clear disk cache: {e}")
    
    def getCacheSize(self) -> int:
        """Get number of cached avatars in memory"""
        return len(self.cache)
    
    def getDiskCacheSize(self) -> int:
        """Get number of cached avatars on disk"""
        try:
            import glob
            files = glob.glob(os.path.join(self.cacheDir, "*.svg"))
            return len(files)
        except Exception:
            return 0
    
    def pregenerateTeamAvatars(self, teams, size: int = 32) -> int:
        """
        Pre-generate avatars for all teams
        
        Args:
            teams: List of team objects with name, color, secondaryColor, tertiaryColor attributes
            size: Avatar size
            
        Returns:
            Number of avatars generated (skips already cached)
        """
        generated = 0
        for team in teams:
            primaryColor = team.color
            secondaryColor = getattr(team, 'secondaryColor', team.color)
            tertiaryColor = getattr(team, 'tertiaryColor', team.color)
            
            # Check if already exists
            cacheKey = self._getCacheKey(team.name, primaryColor, secondaryColor, tertiaryColor, size,
                                        getattr(team, 'logoInvert', False))
            filePath = self._getCacheFilePath(cacheKey)
            
            if not os.path.exists(filePath):
                # Generate and save
                self.generateTeamAvatar(team.name, primaryColor, secondaryColor, tertiaryColor, size, team.id,
                                        getattr(team, 'logoInvert', False))
                generated += 1
        
        logger.info(f"Pre-generated {generated} team avatars ({len(teams) - generated} already cached)")
        return generated


# Global instance
_avatarGenerator: Optional[AvatarGenerator] = None

def getAvatarGenerator() -> AvatarGenerator:
    """Get global avatar generator instance"""
    global _avatarGenerator
    if _avatarGenerator is None:
        _avatarGenerator = AvatarGenerator()
    return _avatarGenerator

def resetAvatarGenerator():
    """Reset the global avatar generator instance (clears all caches)"""
    global _avatarGenerator
    if _avatarGenerator is not None:
        _avatarGenerator.clearCache()
    _avatarGenerator = None
    logger.info("Reset global avatar generator")
