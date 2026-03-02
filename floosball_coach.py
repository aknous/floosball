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

    @property
    def overallRating(self):
        return round(
            (self.offensiveMind + self.defensiveMind + self.adaptability +
             self.aggressiveness + self.clockManagement + self.playerDevelopment) / 6
        )

    def generateAttributes(self, seed: int = None):
        """Generate attributes centered around seed quality (60–100 range)."""
        center = seed if seed is not None else randint(70, 90)
        for attr in ['offensiveMind', 'defensiveMind', 'adaptability',
                     'aggressiveness', 'clockManagement', 'playerDevelopment']:
            val = int(np.clip(np.random.normal(center, 10), 60, 100))
            setattr(self, attr, val)
        return self

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
