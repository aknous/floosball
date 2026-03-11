"""
Team Avatar Generator
Generates SVG avatars for teams using team colors and caches them.
Avatars are persisted to disk for reuse across server restarts.
"""

import hashlib
from typing import Dict, Optional
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
        
    def generateTeamAvatar(self, teamName: str, primaryColor: str, secondaryColor: str, tertiaryColor: str, size: int = 32, teamId: int = None) -> str:
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
        cacheKey = self._getCacheKey(teamName, primaryColor, secondaryColor, tertiaryColor, size)
        
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
        svg = self._generateMarbleSvg(teamName, primaryColor, secondaryColor, tertiaryColor, size, teamId)
        
        # Save to disk
        self._saveToDisk(cacheKey, svg)
        
        # Cache in memory
        self.cache[cacheKey] = svg
        logger.info(f"Generated and cached avatar for {teamName}")
        
        return svg
    
    def _getCacheFilePath(self, cacheKey: str) -> str:
        """Get file path for cached avatar"""
        return os.path.join(self.cacheDir, f"{cacheKey}.svg")
    
    def getPng(self, teamName: str, primaryColor: str, secondaryColor: str, tertiaryColor: str, size: int = 256, teamId: int = None) -> bytes:
        """Generate or return cached PNG avatar for a team."""
        cacheKey = self._getCacheKey(teamName, primaryColor, secondaryColor, tertiaryColor, size)
        pngPath = os.path.join(self.cacheDir, f"{cacheKey}.png")

        # Check disk cache
        if os.path.exists(pngPath):
            with open(pngPath, 'rb') as f:
                return f.read()

        # Generate SVG first, then convert
        svg = self.generateTeamAvatar(teamName, primaryColor, secondaryColor, tertiaryColor, size, teamId)
        import cairosvg
        pngBytes = cairosvg.svg2png(bytestring=svg.encode('utf-8'), output_width=size, output_height=size)

        # Cache to disk
        try:
            with open(pngPath, 'wb') as f:
                f.write(pngBytes)
        except Exception as e:
            logger.error(f"Failed to save PNG to disk: {e}")

        return pngBytes

    def generateLeagueLogo(self, size: int = 256) -> str:
        """Generate the Floosball league logo as SVG — blue circle with tilted football."""
        return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 32 32">
  <circle cx="16" cy="16" r="16" fill="#3b82f6"/>
  <g transform="rotate(-45 16 16)">
    <ellipse cx="16" cy="16" rx="10" ry="6.5" fill="#e2e8f0"/>
    <line x1="6" y1="16" x2="26" y2="16" stroke="#3b82f6" stroke-width="1.2"/>
    <line x1="13" y1="13.2" x2="13" y2="18.8" stroke="#3b82f6" stroke-width="1"/>
    <line x1="16" y1="12.5" x2="16" y2="19.5" stroke="#3b82f6" stroke-width="1"/>
    <line x1="19" y1="13.2" x2="19" y2="18.8" stroke="#3b82f6" stroke-width="1"/>
  </g>
</svg>'''

    def getLeagueLogoPng(self, size: int = 256) -> bytes:
        """Generate or return cached PNG of the league logo."""
        pngPath = os.path.join(self.cacheDir, f"league_logo_{size}.png")
        if os.path.exists(pngPath):
            with open(pngPath, 'rb') as f:
                return f.read()
        svg = self.generateLeagueLogo(size)
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
    
    def _getCacheKey(self, teamName: str, primaryColor: str, secondaryColor: str, tertiaryColor: str, size: int) -> str:
        """Generate a cache key from team data"""
        data = f"{teamName}|{primaryColor}|{secondaryColor}|{tertiaryColor}|{size}"
        return hashlib.md5(data.encode()).hexdigest()
    
    def _generateMarbleSvg(self, seed: str, color1: str, color2: str, color3: str, size: int, teamId: int = None) -> str:
        """
        Generate medieval banner-style SVG with patterns using two colors.
        Patterns include various heraldic designs for visual variety.
        Pattern is sequentially assigned based on team ID.
        """
        # Choose pattern sequentially based on team ID, or fallback to hash
        if teamId is not None:
            patternType = (teamId - 1) % 24  # Cycle through 24 patterns (team IDs start at 1)
        else:
            patternHash = int(hashlib.md5(seed.encode()).hexdigest(), 16)
            patternType = patternHash % 24
        
        # Remove # from hex colors if present
        c1 = color1.lstrip('#')
        c2 = color2.lstrip('#')
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
            # Double chevron
            sw = size * 0.16
            content = f'''<rect width="{size}" height="{size}" fill="#{c1}"/>
                <polyline points="0,{size*0.42:.1f} {half:.1f},{size*0.16:.1f} {size},{size*0.42:.1f}" stroke="#{c2}" stroke-width="{sw:.1f}" fill="none" stroke-linejoin="miter"/>
                <polyline points="0,{size*0.82:.1f} {half:.1f},{size*0.56:.1f} {size},{size*0.82:.1f}" stroke="#{c2}" stroke-width="{sw:.1f}" fill="none" stroke-linejoin="miter"/>'''

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
            # Isometric cube hexagon - solid hex fill with 3 internal depth lines
            r = size * 0.42
            v0x, v0y = half, half - r
            v1x, v1y = half + r*0.866, half - r*0.5
            v2x, v2y = half + r*0.866, half + r*0.5
            v3x, v3y = half, half + r
            v4x, v4y = half - r*0.866, half + r*0.5
            v5x, v5y = half - r*0.866, half - r*0.5
            sw = size * 0.025
            hexPts = f'{v0x:.1f},{v0y:.1f} {v1x:.1f},{v1y:.1f} {v2x:.1f},{v2y:.1f} {v3x:.1f},{v3y:.1f} {v4x:.1f},{v4y:.1f} {v5x:.1f},{v5y:.1f}'
            content = (
                f'<rect width="{size}" height="{size}" fill="#{c2}"/>'
                f'<polygon points="{hexPts}" fill="#{c1}"/>'
                f'<line x1="{half:.1f}" y1="{half:.1f}" x2="{v1x:.1f}" y2="{v1y:.1f}" stroke="#{c2}" stroke-width="{sw:.1f}"/>'
                f'<line x1="{half:.1f}" y1="{half:.1f}" x2="{v3x:.1f}" y2="{v3y:.1f}" stroke="#{c2}" stroke-width="{sw:.1f}"/>'
                f'<line x1="{half:.1f}" y1="{half:.1f}" x2="{v5x:.1f}" y2="{v5y:.1f}" stroke="#{c2}" stroke-width="{sw:.1f}"/>'
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
            cacheKey = self._getCacheKey(team.name, primaryColor, secondaryColor, tertiaryColor, size)
            filePath = self._getCacheFilePath(cacheKey)
            
            if not os.path.exists(filePath):
                # Generate and save
                self.generateTeamAvatar(team.name, primaryColor, secondaryColor, tertiaryColor, size, team.id)
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
