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


# Owner picks that override the sequential `(teamId - 1) % 32` assignment.
#   9 Minnesota Pops -> 54 (three-point). The three roundels at 8 were meant to read as
#   soda bubbles and did not.
CLUB_PATTERN_OVERRIDES = {
    9: 54,     # Minnesota Pops -> three-point. The roundels at 8 never read as bubbles.
    27: 55,    # Montreal Curd -> wide annulet, with the new magenta/yellow.
    28: 56,    # Seoul Trains -> pinwheel. Per pall at 27 was a plain three-way split.
}


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
                           teamId: int = None, logoInvert: bool = False,
                           patternIndex: int = None) -> str:
        """
        Generate medieval banner-style SVG with patterns using two colors.
        Patterns include various heraldic designs for visual variety.
        Pattern is sequentially assigned based on team ID.
        """
        # Choose pattern sequentially based on team ID, or fallback to hash.
        # 32 patterns for 32 clubs — one each, no repeats. At 24 the league outgrew the
        # set on expansion and team IDs 25-32 silently drew the same marks as 1-8.
        if patternIndex is None and teamId is not None and teamId in CLUB_PATTERN_OVERRIDES:
            # An owner's pick. Club assignment is `(teamId - 1) % 32`, which cannot reach
            # anything in the 32+ palette, and moving a pattern's body into a club's slot
            # would renumber marks that other clubs already wear. This map is the seam.
            patternType = CLUB_PATTERN_OVERRIDES[teamId]
        elif patternIndex is not None:
            # Explicit override. Needed because club assignment is `(teamId - 1) % 32`,
            # which cannot reach the fountain variations at 32-35 — they exist as a palette
            # to pick from, and only render when one is moved into a club's own slot.
            patternType = patternIndex
        elif teamId is not None:
            patternType = (teamId - 1) % 32  # team IDs start at 1
        else:
            patternHash = int(hashlib.md5(seed.encode()).hexdigest(), 16)
            patternType = patternHash % 32
        
        # Remove # from hex colors if present
        c1 = color1.lstrip('#')
        c2 = color2.lstrip('#')
        # logoInvert: paint the field in the SECONDARY and the figure in the primary.
        # A club that swaps its two colors can set this to keep the mark looking
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
            # Three roundels in a cluster - grouped and overlapping-close rather than
            # ranged in a line. Owner's call: a row of three read as mechanical.
            content = f'''<rect width="{size}" height="{size}" fill="#{c1}"/>
                <circle cx="{size*0.330:.1f}" cy="{size*0.355:.1f}" r="{size*0.180:.1f}" fill="#{c2}"/>
                <circle cx="{size*0.708:.1f}" cy="{size*0.422:.1f}" r="{size*0.142:.1f}" fill="#{c2}"/>
                <circle cx="{size*0.478:.1f}" cy="{size*0.753:.1f}" r="{size*0.160:.1f}" fill="#{c2}"/>'''
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
            # Per fess nebuly - owner's pick for the Tuesdays.
            midY = half
            lobe = size / 6.0
            path = f"M0,{size} L0,{midY:.1f} "
            for i in range(6):
                x = i * lobe
                path += f"Q{x + lobe*0.25:.1f},{midY - lobe*0.55:.1f} {x + lobe*0.5:.1f},{midY:.1f} "
                path += f"Q{x + lobe*0.75:.1f},{midY + lobe*0.55:.1f} {x + lobe:.1f},{midY:.1f} "
            path += f"L{size},{size} Z"
            content = f'''<rect width="{size}" height="{size}" fill="#{c1}"/>
                <path d="{path}" fill="#{c2}"/>'''
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
            # Barry - the field divided into an even number of horizontal bars. The set had
            # bendy sinister on the diagonal and pales on the vertical but nothing plain on
            # the horizontal. Replaces a bandit mask, which was a pictogram.
            n = 6
            bh = size / n
            bars = "".join(
                f'<rect x="0" y="{i * bh:.2f}" width="{size}" height="{bh:.2f}" fill="#{c2}"/>'
                for i in range(1, n, 2))
            content = f'''<rect width="{size}" height="{size}" fill="#{c1}"/>{bars}'''
        elif patternType == 26:
            # Barry indented - owner's pick for the Curd.
            n = 4
            bh = size / n
            bands = ""
            for i in range(0, n, 2):
                y = i * bh
                pts = [f"0,{y:.1f}"]
                for k in range(9):
                    pts.append(f"{k*size/8:.1f},{y + (bh*0.22 if k % 2 else 0):.1f}")
                pts.append(f"{size},{y + bh:.1f}")
                for k in range(8, -1, -1):
                    pts.append(f"{k*size/8:.1f},{y + bh + (bh*0.22 if k % 2 else 0):.1f}")
                bands += f'<polygon points="{" ".join(pts)}" fill="#{c2}"/>'
            content = f'''<rect width="{size}" height="{size}" fill="#{c1}"/>{bands}'''
        elif patternType == 27:
            # Per pall - owner's pick for the Trains.
            content = f'''<rect width="{size}" height="{size}" fill="#{c1}"/>
                <path d="M0,0 L{half},{half} L0,{size} Z" fill="#{c2}"/>
                <path d="M{size},0 L{half},{half} L{size},{size} Z" fill="#{c2}"/>
                <path d="M0,0 L{half},{half} L{size},0 Z" fill="#{c1}"/>
                <path d="M0,{size} L{half},{half} L{size},{size} Z" fill="#{c2}"/>'''
        elif patternType == 28:
            # Chevronny turned 90 degrees - owner's pick for the Grillmeisters.
            ch = size * 0.30
            ch_shapes = ""
            for i in range(4):
                y = size * 1.05 - i * ch
                ch_shapes += (f'<path d="M0,{y:.1f} L{half},{y - ch*0.75:.1f} L{size},{y:.1f} '
                              f'L{size},{y + ch*0.45:.1f} L{half},{y - ch*0.30:.1f} '
                              f'L0,{y + ch*0.45:.1f} Z" fill="#{c2}"/>')
            content = f'''<rect width="{size}" height="{size}" fill="#{c1}"/>
                <g transform="rotate(90 {half} {half})">{ch_shapes}</g>'''
        elif patternType == 29:
            # Sunrise - rays fanning from the base, not from the center.
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
            # Flaunches - a pair of arcs swept in from the flanks of the field. Genuinely
            # heraldic, and the inward sweep carries a hint of horns without the set
            # turning into a bestiary. Replaces a drawing of horns.
            content = f'''<rect width="{size}" height="{size}" fill="#{c1}"/>
                <path d="M0,0 Q{size * 0.80:.1f},{half} 0,{size} Z" fill="#{c2}"/>
                <path d="M{size},0 Q{size * 0.20:.1f},{half} {size},{size} Z" fill="#{c2}"/>'''
        elif patternType == 31:
            # Fountain - the heraldic roundel barry-wavy, which is literally a fountain.
            # Was "Orbit", a ring with a satellite. Pops now carries the bubbles and these
            # two share a division, so the pair have to read apart at a glance: one is
            # scattered and rising, this one is contained and level.
            extraDefs = f'''<clipPath id="fnt{patternId}">
                <circle cx="{half}" cy="{half}" r="{size*0.36:.1f}"/></clipPath>'''
            waves = ""
            for i in range(4):
                y = size * (0.20 + i * 0.155)
                waves += (f'<path d="M{size*0.10:.1f},{y:.1f} '
                          f'Q{size*0.30:.1f},{y - size*0.055:.1f} {half},{y:.1f} '
                          f'Q{size*0.70:.1f},{y + size*0.055:.1f} {size*0.90:.1f},{y:.1f} '
                          f'L{size*0.90:.1f},{y + size*0.075:.1f} '
                          f'Q{size*0.70:.1f},{y + size*0.13:.1f} {half},{y + size*0.075:.1f} '
                          f'Q{size*0.30:.1f},{y + size*0.02:.1f} {size*0.10:.1f},{y + size*0.075:.1f} Z" '
                          f'fill="#{c1}"/>')
            content = f'''<rect width="{size}" height="{size}" fill="#{c1}"/>
                <circle cx="{half}" cy="{half}" r="{size*0.36:.1f}" fill="#{c2}"/>
                <g clip-path="url(#fnt{patternId})">{waves}</g>'''
        elif patternType == 23:
            # Pale - single bold vertical band.
            # ⚠️ EXPLICIT ON PURPOSE. 23 had no branch of its own and fell through to the
            # `else` below, which draws exactly this. The output was unique — nothing else
            # in the set draws a pale — but only by accident, and the next pattern added to
            # the `else` would have silently collided with whichever club holds id 24.
            pw = size * 0.32
            content = f'''<rect width="{size}" height="{size}" fill="#{c1}"/>
                <rect x="{(size - pw) / 2:.1f}" y="0" width="{pw:.1f}" height="{size}" fill="#{c2}"/>'''

        elif patternType == 32:
            # FOUNTAIN FAMILY (32-35). Variations on the heraldic fountain at 31, added as
            # a palette to choose from rather than as club assignments — at 32 clubs the
            # index map only reaches 0-31, so these render only when one is moved into a
            # club's own slot.
            #
            # Barry wavy - the fountain unrolled across the whole field.
            waves = ""
            for i in range(5):
                y = size * (0.06 + i * 0.20)
                waves += (f'<path d="M0,{y:.1f} '
                          f'Q{size*0.25:.1f},{y - size*0.06:.1f} {half},{y:.1f} '
                          f'Q{size*0.75:.1f},{y + size*0.06:.1f} {size},{y:.1f} '
                          f'L{size},{y + size*0.10:.1f} '
                          f'Q{size*0.75:.1f},{y + size*0.16:.1f} {half},{y + size*0.10:.1f} '
                          f'Q{size*0.25:.1f},{y + size*0.04:.1f} 0,{y + size*0.10:.1f} Z" '
                          f'fill="#{c2}"/>')
            content = f'''<rect width="{size}" height="{size}" fill="#{c1}"/>{waves}'''

        elif patternType == 33:
            # Three fountains - the charge borne in the usual two-and-one arrangement.
            extraDefs = ""
            blobs = ""
            for n, (cx, cy) in enumerate(((0.31, 0.34), (0.69, 0.34), (0.50, 0.70))):
                px, py, r = size * cx, size * cy, size * 0.185
                cid = f"f3{patternId}{n}"
                extraDefs += f'<clipPath id="{cid}"><circle cx="{px:.1f}" cy="{py:.1f}" r="{r:.1f}"/></clipPath>'
                inner = ""
                for i in range(3):
                    y = py - r + r * (0.45 + i * 0.62)
                    inner += (f'<path d="M{px - r:.1f},{y:.1f} '
                              f'Q{px - r*0.5:.1f},{y - r*0.30:.1f} {px:.1f},{y:.1f} '
                              f'Q{px + r*0.5:.1f},{y + r*0.30:.1f} {px + r:.1f},{y:.1f} '
                              f'L{px + r:.1f},{y + r*0.30:.1f} '
                              f'Q{px + r*0.5:.1f},{y + r*0.60:.1f} {px:.1f},{y + r*0.30:.1f} '
                              f'Q{px - r*0.5:.1f},{y:.1f} {px - r:.1f},{y + r*0.30:.1f} Z" fill="#{c1}"/>')
                blobs += (f'<circle cx="{px:.1f}" cy="{py:.1f}" r="{r:.1f}" fill="#{c2}"/>'
                          f'<g clip-path="url(#{cid})">{inner}</g>')
            content = f'''<rect width="{size}" height="{size}" fill="#{c1}"/>{blobs}'''

        elif patternType == 34:
            # Roundel barry - the same charge with the bars drawn straight instead of wavy.
            extraDefs = f'''<clipPath id="rb{patternId}">
                <circle cx="{half}" cy="{half}" r="{size*0.36:.1f}"/></clipPath>'''
            bars = "".join(
                f'<rect x="0" y="{size*(0.16 + i*0.135):.1f}" width="{size}" '
                f'height="{size*0.068:.1f}" fill="#{c1}"/>' for i in range(5))
            content = f'''<rect width="{size}" height="{size}" fill="#{c1}"/>
                <circle cx="{half}" cy="{half}" r="{size*0.36:.1f}" fill="#{c2}"/>
                <g clip-path="url(#rb{patternId})">{bars}</g>'''

        elif patternType == 35:
            # Fountain counterchanged - the field parted per fess and the roundel taking
            # the opposite tincture on each side of the line.
            extraDefs = f'''<clipPath id="fc{patternId}">
                <circle cx="{half}" cy="{half}" r="{size*0.38:.1f}"/></clipPath>
                <clipPath id="fct{patternId}"><rect x="0" y="0" width="{size}" height="{half}"/></clipPath>
                <clipPath id="fcb{patternId}"><rect x="0" y="{half}" width="{size}" height="{half}"/></clipPath>'''
            def band(fill):
                out = ""
                for i in range(6):
                    y = size * (0.10 + i * 0.16)
                    out += (f'<path d="M0,{y:.1f} Q{half},{y - size*0.055:.1f} {size},{y:.1f} '
                            f'L{size},{y + size*0.08:.1f} Q{half},{y + size*0.025:.1f} 0,{y + size*0.08:.1f} Z" '
                            f'fill="#{fill}"/>')
                return out
            content = f'''<rect width="{size}" height="{half}" fill="#{c1}"/>
                <rect x="0" y="{half}" width="{size}" height="{half}" fill="#{c2}"/>
                <g clip-path="url(#fc{patternId})">
                  <g clip-path="url(#fct{patternId})"><circle cx="{half}" cy="{half}" r="{size*0.38:.1f}" fill="#{c2}"/>{band(c1)}</g>
                  <g clip-path="url(#fcb{patternId})"><circle cx="{half}" cy="{half}" r="{size*0.38:.1f}" fill="#{c1}"/>{band(c2)}</g>
                </g>'''

        elif patternType == 36:
            # PATTERN IDEAS (36+). A palette to choose from — club assignment only reaches
            # 0-31, so these render nowhere until one is moved into a club's slot.
            #
            # Chequy - the plain checkerboard.
            n = 4
            cell = size / n
            sq = "".join(
                f'<rect x="{col*cell:.2f}" y="{row*cell:.2f}" width="{cell:.2f}" height="{cell:.2f}" fill="#{c2}"/>'
                for row in range(n) for col in range(n) if (row + col) % 2)
            content = f'''<rect width="{size}" height="{size}" fill="#{c1}"/>{sq}'''

        elif patternType == 37:
            # Paly of six - equal vertical bands, the vertical answer to barry.
            n = 6
            bw = size / n
            bars = "".join(f'<rect x="{i*bw:.2f}" y="0" width="{bw:.2f}" height="{size}" fill="#{c2}"/>'
                           for i in range(1, n, 2))
            content = f'''<rect width="{size}" height="{size}" fill="#{c1}"/>{bars}'''

        elif patternType == 38:
            # Chevronny, turned 90 degrees - chevrons pointing sideways rather than up.
            # Upright it sat too close to the double chevron the Beans already wear.
            ch = size * 0.30
            ch_shapes = ""
            for i in range(4):
                y = size * 1.05 - i * ch
                ch_shapes += (f'<path d="M0,{y:.1f} L{half},{y - ch*0.75:.1f} L{size},{y:.1f} '
                              f'L{size},{y + ch*0.45:.1f} L{half},{y - ch*0.30:.1f} '
                              f'L0,{y + ch*0.45:.1f} Z" fill="#{c2}"/>')
            content = f'''<rect width="{size}" height="{size}" fill="#{c1}"/>
                <g transform="rotate(90 {half} {half})">{ch_shapes}</g>'''
        elif patternType == 39:
            # Papelonny - overlapping scales, the fur that looks like a fish or a roof.
            r = size * 0.17
            scales = ""
            for row in range(6):
                y = size * (0.02 + row * 0.19)
                off = r if row % 2 else 0
                for col in range(5):
                    x = col * r * 2 + off - r * 0.5
                    scales += (f'<path d="M{x:.1f},{y:.1f} A{r:.1f},{r:.1f} 0 0 0 {x + 2*r:.1f},{y:.1f} Z" '
                               f'fill="none" stroke="#{c2}" stroke-width="{size*0.045:.1f}"/>')
            content = f'''<rect width="{size}" height="{size}" fill="#{c1}"/>{scales}'''

        elif patternType == 40:
            # Potent - the fur of interlocking T shapes.
            u = size / 4.0
            tees = ""
            for row in range(4):
                for col in range(4):
                    if (row + col) % 2: continue
                    x, y = col * u, row * u
                    tees += (f'<path d="M{x:.1f},{y:.1f} h{u:.1f} v{u*0.34:.1f} h-{u*0.33:.1f} '
                             f'v{u*0.66:.1f} h-{u*0.34:.1f} v-{u*0.66:.1f} h-{u*0.33:.1f} Z" fill="#{c2}"/>')
            content = f'''<rect width="{size}" height="{size}" fill="#{c1}"/>{tees}'''

        elif patternType == 41:
            # Ermine - the fur, its little three-dot tails strewn in offset rows.
            spots = ""
            for row in range(4):
                y = size * (0.14 + row * 0.25)
                off = 0.125 if row % 2 else 0.0
                for col in range(4):
                    x = size * (0.13 + off + col * 0.25)
                    if x > size * 0.95: continue
                    spots += (f'<path d="M{x:.1f},{y - size*0.06:.1f} '
                              f'L{x + size*0.045:.1f},{y + size*0.05:.1f} '
                              f'L{x - size*0.045:.1f},{y + size*0.05:.1f} Z" fill="#{c2}"/>'
                              f'<circle cx="{x:.1f}" cy="{y + size*0.078:.1f}" r="{size*0.017:.1f}" fill="#{c2}"/>'
                              f'<circle cx="{x - size*0.035:.1f}" cy="{y + size*0.095:.1f}" r="{size*0.015:.1f}" fill="#{c2}"/>'
                              f'<circle cx="{x + size*0.035:.1f}" cy="{y + size*0.095:.1f}" r="{size*0.015:.1f}" fill="#{c2}"/>')
            content = f'''<rect width="{size}" height="{size}" fill="#{c1}"/>{spots}'''

        elif patternType == 42:
            # Masoned - a wall, courses of brick offset row by row.
            rows_ = 6
            rh = size / rows_
            lines = ""
            for i in range(1, rows_):
                lines += f'<rect x="0" y="{i*rh - size*0.012:.1f}" width="{size}" height="{size*0.024:.1f}" fill="#{c2}"/>'
            for i in range(rows_):
                off = rh if i % 2 else 0
                for j in range(4):
                    x = j * rh * 2 + off
                    lines += f'<rect x="{x - size*0.012:.1f}" y="{i*rh:.1f}" width="{size*0.024:.1f}" height="{rh:.1f}" fill="#{c2}"/>'
            content = f'''<rect width="{size}" height="{size}" fill="#{c1}"/>{lines}'''

        elif patternType == 43:
            # Orle - a narrow border set in from the edge, floating clear of it.
            inset = size * 0.16
            w = size * 0.10
            content = f'''<rect width="{size}" height="{size}" fill="#{c1}"/>
                <rect x="{inset:.1f}" y="{inset:.1f}" width="{size - 2*inset:.1f}"
                      height="{size - 2*inset:.1f}" fill="none" stroke="#{c2}" stroke-width="{w:.1f}"/>'''

        elif patternType == 44:
            # Annulet - one bold ring, centered.
            content = f'''<rect width="{size}" height="{size}" fill="#{c1}"/>
                <circle cx="{half}" cy="{half}" r="{size*0.30:.1f}" fill="none"
                        stroke="#{c2}" stroke-width="{size*0.15:.1f}"/>'''

        elif patternType == 45:
            # Chapé - the field cut away from the top corners to a point.
            content = f'''<rect width="{size}" height="{size}" fill="#{c2}"/>
                <path d="M0,0 L{half},{size*0.62:.1f} L0,{size} Z" fill="#{c1}"/>
                <path d="M{size},0 L{half},{size*0.62:.1f} L{size},{size} Z" fill="#{c1}"/>'''

        elif patternType == 46:
            # Per pall - the three-way Y division.
            content = f'''<rect width="{size}" height="{size}" fill="#{c1}"/>
                <path d="M0,0 L{half},{half} L0,{size} Z" fill="#{c2}"/>
                <path d="M{size},0 L{half},{half} L{size},{size} Z" fill="#{c2}"/>
                <path d="M0,0 L{half},{half} L{size},0 Z" fill="#{c1}"/>
                <path d="M0,{size} L{half},{half} L{size},{size} Z" fill="#{c2}"/>'''

        elif patternType == 47:
            # Pily - interlocking wedges biting into each other from top and bottom.
            n = 5
            w = size / n
            up = "".join(f'<path d="M{i*w:.1f},{size} L{(i+0.5)*w:.1f},{size*0.30:.1f} L{(i+1)*w:.1f},{size} Z" fill="#{c2}"/>'
                         for i in range(n))
            content = f'''<rect width="{size}" height="{size}" fill="#{c1}"/>{up}'''

        elif patternType == 48:
            # Gobony - a single band of alternating squares running on the bend.
            u = size * 0.17
            sq = "".join(f'<rect x="{i*u:.1f}" y="{size*0.42:.1f}" width="{u:.1f}" height="{size*0.16:.1f}" fill="#{c2}"/>'
                         for i in range(0, 8, 2))
            content = f'''<rect width="{size}" height="{size}" fill="#{c1}"/>
                <g transform="rotate(-45 {half} {half})">
                  <rect x="0" y="{size*0.42:.1f}" width="{size}" height="{size*0.16:.1f}" fill="#{c2}" opacity="0.35"/>
                  {sq}
                </g>'''

        elif patternType == 49:
            # Barry indented - horizontal bands whose edges are sawtoothed.
            n = 4
            bh = size / n
            bands = ""
            for i in range(0, n, 2):
                y = i * bh
                pts = [f"0,{y:.1f}"]
                for k in range(9):
                    pts.append(f"{k*size/8:.1f},{y + (bh*0.22 if k % 2 else 0):.1f}")
                pts.append(f"{size},{y + bh:.1f}")
                for k in range(8, -1, -1):
                    pts.append(f"{k*size/8:.1f},{y + bh + (bh*0.22 if k % 2 else 0):.1f}")
                bands += f'<polygon points="{" ".join(pts)}" fill="#{c2}"/>'
            content = f'''<rect width="{size}" height="{size}" fill="#{c1}"/>{bands}'''

        elif patternType == 50:
            # Per fess nebuly - a horizontal division with a cloud-edged line.
            midY = half
            lobe = size / 6.0
            path = f"M0,{size} L0,{midY:.1f} "
            for i in range(6):
                x = i * lobe
                path += f"Q{x + lobe*0.25:.1f},{midY - lobe*0.55:.1f} {x + lobe*0.5:.1f},{midY:.1f} "
                path += f"Q{x + lobe*0.75:.1f},{midY + lobe*0.55:.1f} {x + lobe:.1f},{midY:.1f} "
            path += f"L{size},{size} Z"
            content = f'''<rect width="{size}" height="{size}" fill="#{c1}"/>
                <path d="{path}" fill="#{c2}"/>'''

        elif patternType == 51:
            # Fusilly - a lattice of narrow lozenges, tighter and sharper than lozengy.
            fw, fh = size * 0.17, size * 0.30
            lz = ""
            for row in range(5):
                for col in range(7):
                    cx = col * fw - fw * 0.5 + (fw * 0.5 if row % 2 else 0)
                    cy = row * fh * 0.75
                    if (row + col) % 2: continue
                    lz += (f'<polygon points="{cx:.1f},{cy - fh/2:.1f} {cx + fw/2:.1f},{cy:.1f} '
                           f'{cx:.1f},{cy + fh/2:.1f} {cx - fw/2:.1f},{cy:.1f}" fill="#{c2}"/>')
            content = f'''<rect width="{size}" height="{size}" fill="#{c1}"/>{lz}'''

        elif patternType == 52:
            # Rayonny - a division line of flame, the field burning across the middle.
            midY = half
            step = size / 7.0
            path = f"M0,{size} L0,{midY:.1f} "
            for i in range(7):
                x = i * step
                path += (f"Q{x + step*0.2:.1f},{midY - step*0.85:.1f} {x + step*0.55:.1f},{midY - step*0.20:.1f} "
                         f"Q{x + step*0.8:.1f},{midY + step*0.20:.1f} {x + step:.1f},{midY:.1f} ")
            path += f"L{size},{size} Z"
            content = f'''<rect width="{size}" height="{size}" fill="#{c1}"/>
                <path d="{path}" fill="#{c2}"/>'''

        elif patternType == 53:
            # Gyronny of twelve - the pie division at twice the usual count, so the field
            # spins rather than quarters. The set already has gyronny of eight.
            import math as _math
            wedges = ""
            for i in range(0, 12, 2):
                a0 = _math.radians(i * 30 - 90)
                a1 = _math.radians((i + 1) * 30 - 90)
                p0 = (half + size * _math.cos(a0), half + size * _math.sin(a0))
                p1 = (half + size * _math.cos(a1), half + size * _math.sin(a1))
                wedges += (f'<polygon points="{half},{half} {p0[0]:.1f},{p0[1]:.1f} '
                           f'{p1[0]:.1f},{p1[1]:.1f}" fill="#{c2}"/>')
            content = f'''<rect width="{size}" height="{size}" fill="#{c1}"/>{wedges}'''

        elif patternType == 54:
            # Three-point - a pall inverted with its arms at a true 120 degrees, so it sits
            # symmetric about the center rather than reaching for the corners.
            #
            # A peace sign is FOUR arms from the center (up, down, down-left, down-right);
            # take the straight-down one out and this is what is left. It is also the
            # arrangement on the Mercedes badge, the whole difference there being the ring
            # drawn around it — deliberately omitted, since the ring is what makes it read
            # as a car badge rather than as heraldry.
            #
            # ⚠️ NOT `per pall` (27 and 46, which the set already carries twice over). Those
            # DIVIDE the field three ways along a Y; this lays a BAND over it, so the field
            # reads around the charge. Different silhouette entirely.
            #
            # Drawn broad on purpose. At the narrow weight the ordinary is normally given,
            # the arms close up to hairlines by the 20px the feed rows use.
            import math as _math
            _armW = size * 0.24
            _R = half * 1.45          # past the box; the circular clip cuts each arm at the rim
            _d = ' '.join(
                f'M {half:.1f},{half:.1f} '
                f'L {half + _R * _math.sin(_math.radians(a)):.1f},'
                f'{half - _R * _math.cos(_math.radians(a)):.1f}'
                for a in (0, 120, 240))
            content = f'''<rect width="{size}" height="{size}" fill="#{c1}"/>
                <path d="{_d}" stroke="#{c2}" stroke-width="{_armW:.2f}" fill="none"
                      stroke-linecap="butt"/>'''

        elif patternType == 55:
            # Annulet, WIDE - a bold ring set close to the rim, so the field reads as a
            # border around it rather than as a background behind it.
            #
            # ⚠️ NOT the annulet at 44, which is a smaller ring centered in open field. This
            # is the same charge at a different scale, and the difference is the whole
            # point: at 44 the eye reads a ring ON a field; here it reads a band WITHIN a
            # circle. Kept separate so 44 stays available in its original proportions.
            _r = half * 0.46
            content = f'''<rect width="{size}" height="{size}" fill="#{c1}"/>
                <circle cx="{half}" cy="{half}" r="{_r:.1f}" fill="none"
                        stroke="#{c2}" stroke-width="{size * 0.13:.2f}"/>'''

        elif patternType == 56:
            # Pinwheel - a triangle at the center with each side carried on past ONE
            # vertex only, always the same way round.
            #
            # ⚠️ The one-sidedness IS the figure. Extend both ends of every side and you
            # get a static three-pointed star (which is what the first attempt drew);
            # extend one and the whole mark turns. Anticlockwise here, which is the
            # owner's pick - reversing the vertex order is the only difference.
            import math as _math
            _R = half * 0.42
            _far = size * 1.6
            _V = [(half + _R * _math.cos(_math.radians(-90 + a)),
                   half + _R * _math.sin(_math.radians(-90 + a))) for a in (0, 120, 240)]
            _V = _V[::-1]                      # anticlockwise
            _lines = ''
            for _i in range(3):
                _a, _b = _V[_i], _V[(_i + 1) % 3]
                _dx, _dy = _b[0] - _a[0], _b[1] - _a[1]
                _L = _math.hypot(_dx, _dy) or 1.0
                _ux, _uy = _dx / _L, _dy / _L
                _lines += (f'<line x1="{_a[0]:.1f}" y1="{_a[1]:.1f}" '
                           f'x2="{_b[0] + _ux * _far:.1f}" y2="{_b[1] + _uy * _far:.1f}" '
                           f'stroke="#{c2}" stroke-width="{size * 0.09:.2f}"/>')
            content = f'''<rect width="{size}" height="{size}" fill="#{c1}"/>{_lines}'''

        else:
            # Unreachable at 32 clubs (patternType is always 0-31 and every value now has a
            # branch). Kept as a safety net so an off-by-one in the pattern count draws
            # something rather than an empty circle.
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
