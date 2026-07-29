"""Coach class for Floosball — attributes, name generation, and retirement logic."""

from random import randint, random, choice
import numpy as np

COACH_FIRST_NAMES = [
    "Bill", "Tom", "Andy", "Mike", "Sean", "Kyle", "Matt", "John", "Dan", "Greg",
    "Ron", "Pete", "Dave", "Steve", "Frank", "Gary", "Rick", "Joe", "Jim", "Bob",
    "Ray", "Art", "Lou", "Hank", "Vince", "Wade", "Marty", "Rex", "Norm", "Buddy",
    "Chuck", "Chip", "Curt", "Dean", "Earl", "Fran", "Glen", "Hal", "Ivan", "Jack",
    "Karl", "Lane", "Marc", "Nick", "Otto", "Paul", "Quinn", "Rob", "Sam", "Ted",
    "Vic", "Walt", "Zach", "Alan", "Bret", "Clyde", "Don", "Eric", "Fred", "Gus",
]

COACH_LAST_NAMES = [
    "Walsh", "Belichick", "Noll", "Shula", "Halas", "Lombardi", "Landry", "Brown",
    "Parcells", "Gibbs", "Johnson", "Reid", "Payton", "Carroll", "Rivera", "Taylor",
    "Smith", "Jones", "Davis", "Wilson", "Moore", "Thomas", "Jackson", "White",
    "Harris", "Martin", "Thompson", "Garcia", "Martinez", "Anderson", "Robinson",
    "Clark", "Lewis", "Lee", "Walker", "Hall", "Allen", "Young", "King", "Wright",
    "Scott", "Green", "Baker", "Adams", "Nelson", "Hill", "Ramirez", "Campbell",
    "Mitchell", "Roberts", "Carter", "Phillips", "Evans", "Turner", "Torres",
    "Parker", "Collins", "Edwards", "Stewart", "Flores", "Morris", "Nguyen",
]


class Coach:
    def __init__(self):
        self.id = None
        self.name = ""
        self.seasonsCoached = 0

        # Attributes (60–100)
        self.offensiveMind = 80
        self.defensiveMind = 80
        self.adaptability = 80
        self.aggressiveness = 80
        self.clockManagement = 80
        self.playerDevelopment = 80
        # Scouting drives how accurately fans can see upcoming rookies' potential.
        # Coach scouting + funding tier bonus = effective scouting accuracy. A
        # scouting specialist on a MEGA-market team nails every ceiling call;
        # a castoff on a SMALL-market team sees wide potential ranges.
        self.scouting = 80
        # Attitude (60-100): coach's locker-room presence on the toxic→leader
        # spectrum. Leader-tier coaches reign in toxic players (dampening their
        # contagion) and make the room want to play hard for them; toxic-tier
        # coaches let dysfunction fester and add to it. Wired into:
        #   - _propagateAttitudeContagion (anchor effect on room signal)
        #   - _driftAttitudes (scales upward / downward drift magnitude)
        #   - _computeContextMultiplier ("play hard for them" boost/penalty)
        self.attitude = 80
        # Fan trust (60-100): how much fan sentiment moves this GM's roster
        # decisions. 60 = ignores the fans entirely and trusts their own read;
        # 100 = populist who churns fan-villains and regrets it. Deliberately
        # INDEPENDENT of coaching quality (a great coach can be a populist) and
        # separate from `attitude`, which is the locker-room axis, not the
        # fanbase one. GM-only — it has no gameday effect.
        # See docs/AUTONOMOUS_FRONT_OFFICE_PLAN.md Part B.
        self.fanTrust = 80

    @property
    def overallRating(self):
        """DEPRECATED — do not display. Since Part B coaches are specialists, so
        central limit pulls this aggregate to the middle for everyone and it
        carries almost no signal. It also excludes `scouting` and `attitude`,
        the two most GM-critical traits. Retained only to populate the legacy
        `coaches.overall_rating` column and the no-votes hire fallback, both of
        which disappear with the binding votes (plan Part E). Use `profile()`."""
        return round(
            (self.offensiveMind + self.defensiveMind + self.adaptability +
             self.aggressiveness + self.clockManagement + self.playerDevelopment) / 6
        )

    def generateAttributes(self, seed: int = None):
        """Generate a SPECIALIST attribute spread (60–100 range).

        Each attribute is drawn largely independently around a small shared
        quality component, so a coach is strong at some things and weak at
        others rather than uniformly good or bad. Most land near-average
        overall; the rare all-around elite or bust comes from the shared term.
        See docs/AUTONOMOUS_FRONT_OFFICE_PLAN.md Part B.

        `seed`, when given, sets the center — the hire slate still offers
        premium/mid/budget candidates (COACH_CANDIDATE_SEEDS), each now a
        specialist around that quality level rather than flat across the board.
        """
        from constants import (COACH_ATTR_CENTER, COACH_ATTR_SHARED_SIGMA,
                               COACH_ATTR_INDEP_SIGMA)
        center = seed if seed is not None else COACH_ATTR_CENTER
        # One shared draw per coach — small, so it shifts the whole profile only
        # slightly. This is the ONLY thing correlating the attributes.
        shared = np.random.normal(0, COACH_ATTR_SHARED_SIGMA)
        for attr in ['offensiveMind', 'defensiveMind', 'adaptability',
                     'aggressiveness', 'clockManagement', 'playerDevelopment',
                     'scouting', 'attitude']:
            val = int(np.clip(
                np.random.normal(center + shared, COACH_ATTR_INDEP_SIGMA), 60, 100))
            setattr(self, attr, val)
        # fanTrust is drawn INDEPENDENTLY of the coach's quality seed — how much
        # a GM listens to the fans says nothing about how good they are, so a
        # sharp evaluator is as likely to be a populist as a poor one.
        self.fanTrust = int(np.clip(np.random.normal(80, 10), 60, 100))
        return self

    # Human-readable attribute labels for the scouting report. Top attribute
    # becomes a specialty, bottom becomes a flaw.
    _SPECIALTY_LABELS = {
        'offensiveMind': 'Offensive Guru',
        'defensiveMind': 'Defensive Architect',
        'adaptability': 'Quick Study',
        'aggressiveness': 'Gambler',
        'clockManagement': 'Clock Surgeon',
        'playerDevelopment': 'Teacher',
        'scouting': 'Sharp Eye',
        'attitude': "Players' Coach",
    }
    _FLAW_LABELS = {
        'offensiveMind': 'No Feel for Offense',
        'defensiveMind': 'No Feel for Defense',
        'adaptability': 'Stubborn',
        'aggressiveness': 'Timid',
        'clockManagement': 'Clock Trouble',
        'playerDevelopment': 'Poor Developer',
        'scouting': "Can't Scout",
        'attitude': 'Sour Room',
    }
    _PROFILE_ATTRS = ('offensiveMind', 'defensiveMind', 'adaptability',
                      'aggressiveness', 'clockManagement', 'playerDevelopment',
                      'scouting', 'attitude')

    def profile(self) -> dict:
        """Scouting report replacing the (now meaningless) overall star."""
        return buildCoachProfile(
            {a: getattr(self, a, 80) for a in self._PROFILE_ATTRS},
            getattr(self, 'fanTrust', 80))

    def generateName(self, namePool: list = None):
        """Generate a random coach name from namePool if provided, else built-in lists."""
        if namePool:
            self.name = choice(namePool)
        else:
            self.name = f"{choice(COACH_FIRST_NAMES)} {choice(COACH_LAST_NAMES)}"
        return self

    def shouldRetire(self) -> bool:
        """Tenure-based retirement check. Called at season end."""
        retireChance = max(0.0, (self.seasonsCoached - 10) * 0.03)
        return random() < retireChance

    def __repr__(self):
        return (f"<Coach '{self.name}' overall={self.overallRating} "
                f"off={self.offensiveMind} def={self.defensiveMind}>")


def buildCoachProfile(values: dict, fanTrust: int = 80) -> dict:
    """Derive a coach's scouting report from raw attribute values.

    Module-level so both the in-memory Coach and a raw DB row (snake_case
    columns) produce an identical report — the hire slate reads straight off
    unassigned Coach rows and must not drift from the live version.

    A specialist spread has no honest scalar summary — central limit pulls every
    aggregate to the middle — so a coach reads as their standout, their weakness,
    and where they sit on the fan-trust axis. Tags are only awarded when an
    attribute is genuinely notable; a flat coach reads as a Generalist rather
    than being handed a misleading label.
    """
    from constants import (COACH_PROFILE_SPECIALTY_MIN, COACH_PROFILE_FLAW_MAX,
                           COACH_FANTRUST_POPULIST_MIN,
                           COACH_FANTRUST_INDEPENDENT_MAX)
    vals = {a: int(values.get(a, 80) or 80) for a in Coach._PROFILE_ATTRS}
    topAttr = max(vals, key=lambda a: vals[a])
    bottomAttr = min(vals, key=lambda a: vals[a])

    specialty = (Coach._SPECIALTY_LABELS[topAttr]
                 if vals[topAttr] >= COACH_PROFILE_SPECIALTY_MIN else None)
    flaw = (Coach._FLAW_LABELS[bottomAttr]
            if vals[bottomAttr] <= COACH_PROFILE_FLAW_MAX else None)

    trust = int(fanTrust or 80)
    if trust >= COACH_FANTRUST_POPULIST_MIN:
        trustLabel = 'Populist'
    elif trust <= COACH_FANTRUST_INDEPENDENT_MAX:
        trustLabel = 'Old School'
    else:
        trustLabel = None

    tags = [t for t in (specialty, flaw, trustLabel) if t] or ['Generalist']

    # Per-attribute QUALITATIVE bands. Coach/GM rating NUMBERS are never
    # surfaced — a GM reads as archetypes, not a stat line. Bands reuse the
    # vocabulary the play-insights panel already uses for coaches
    # (Elite/Sharp/Capable/Limited) so the two can't drift.
    traits = [{'attr': a, 'label': ATTR_DISPLAY_NAMES[a], 'band': attributeBand(vals[a])}
              for a in Coach._PROFILE_ATTRS]

    return {
        'specialty': specialty,
        'specialtyAttr': topAttr if specialty else None,
        'flaw': flaw,
        'flawAttr': bottomAttr if flaw else None,
        'fanTrustLabel': trustLabel,
        'tags': tags,
        'traits': traits,
    }


# Display names for the scouting report. No numbers ever accompany these.
ATTR_DISPLAY_NAMES = {
    'offensiveMind': 'Offensive Mind',
    'defensiveMind': 'Defensive Mind',
    'adaptability': 'Adaptability',
    'aggressiveness': 'Aggressiveness',
    'clockManagement': 'Clock Management',
    'playerDevelopment': 'Player Development',
    'scouting': 'Scouting',
    'attitude': 'Locker Room',
}

# Band thresholds mirror PlayInsightsPanel.coachMindLabel so a coach never reads
# 'Elite' in one place and 'Sharp' in another.
ATTR_BAND_ELITE = 90
ATTR_BAND_SHARP = 80
ATTR_BAND_CAPABLE = 70


def attributeBand(value: int) -> str:
    """Qualitative band for a coach attribute — the only thing ever shown."""
    v = int(value or 0)
    if v >= ATTR_BAND_ELITE:
        return 'Elite'
    if v >= ATTR_BAND_SHARP:
        return 'Sharp'
    if v >= ATTR_BAND_CAPABLE:
        return 'Capable'
    return 'Limited'


def profileFromDbRow(row) -> dict:
    """Scouting report for a raw `coaches` DB row (snake_case columns)."""
    return buildCoachProfile({
        'offensiveMind': getattr(row, 'offensive_mind', 80),
        'defensiveMind': getattr(row, 'defensive_mind', 80),
        'adaptability': getattr(row, 'adaptability', 80),
        'aggressiveness': getattr(row, 'aggressiveness', 80),
        'clockManagement': getattr(row, 'clock_management', 80),
        'playerDevelopment': getattr(row, 'player_development', 80),
        'scouting': getattr(row, 'scouting', 80),
        'attitude': getattr(row, 'attitude', 80),
    }, getattr(row, 'fan_trust', 80))
