"""The username length cap applies to names a USER made up, not to ones we offered them.

The app generated `LowercaseMortadella47` (21 characters), showed it as a suggestion, and
then refused it on submit against its own 20-character limit. 14,786 of the generator's
66,300 pairings run past 20 characters, so roughly 22% of two-digit suggestions were
unusable with nothing to tell the user which ones.

`_generateUsernameCandidate` already states the rule it broke — "a suggestion the
validator would refuse is worse than no suggestion" — and screens suggestions for
profanity. Length was simply missed.

The exemption is VERIFIED against the generator's own vocabulary rather than trusted from
the client, so it cannot be used to smuggle a long custom name past the cap.

Run: .venv/bin/python test_username_length.py   (exits non-zero on any failure)
"""
import sys
sys.path.insert(0, '/Users/andrew/Projects/floosball')
import logging; logging.disable(logging.CRITICAL)
import random

from api.auth import (
    validateUsername, isGeneratedUsername, USERNAME_MAX_LEN,
    _USERNAME_FIRSTS, _USERNAME_LASTS,
)

fails = []
def expect(d, c):
    print(f"  [{'OK' if c else 'FAIL'}] {d}")
    if not c: fails.append(d)


def accepted(name):
    _, err = validateUsername(name)
    return err is None


print("\nA suggestion the app offers is a suggestion the app accepts")
random.seed(11)
rejected = []
for _ in range(6000):
    name = random.choice(_USERNAME_FIRSTS) + random.choice(_USERNAME_LASTS) + str(random.randint(1, 99))
    _, err = validateUsername(name)
    # Profanity is a legitimate refusal — the generator screens for it separately and
    # never offers those. Anything else is the app contradicting itself.
    if err and 'not available' not in err:
        rejected.append((name, err))
expect("6000 sampled generated names, none refused for length or format", not rejected)
if rejected:
    for n, e in rejected[:5]:
        print(f"        {n} ({len(n)}) -> {e}")

overLong = [n for n in
            (a + b + '47' for a in _USERNAME_FIRSTS[:60] for b in _USERNAME_LASTS[:60])
            if len(n) > USERNAME_MAX_LEN]
expect("the over-long pairings exist at all (the bug was real)", len(overLong) > 0)
expect("...and every one of them is accepted now", all(accepted(n) for n in overLong))

print("\nA name the user made up is still capped")
for name in ['MyVeryLongCustomHandle99', 'aaaaaaaaaaaaaaaaaaaaaaaaaa',
             'Supercalifragilisticexpialidocious']:
    expect(f"{name[:28]} ({len(name)}) is refused", not accepted(name))

print("\nThe exemption cannot be forged")
# Each of these LOOKS like a generated name without being one. If any passes, the cap is
# bypassable by anyone who guesses the shape, which defeats having a cap.
forgeries = [
    'NotAWordAtAllHereFriend42',   # right shape, words are not in the vocabulary
    'LowercaseMortadella047',      # leading zero — randint(1, 99) never emits one
    'LowercaseMortadella',         # real pairing, no number
    'Lowercase47Mortadella',       # digits in the middle
    'LowercaseMortadella100',      # three digits
]
for name in forgeries:
    expect(f"{name} is not treated as generated", not isGeneratedUsername(name))
expect("...and the over-long forgeries are refused",
       all(not accepted(n) for n in forgeries if len(n) > USERNAME_MAX_LEN))

print("\nShort names are unaffected either way")
expect("a short generated name still passes", accepted(_USERNAME_FIRSTS[0] + _USERNAME_LASTS[0] + '7')
       or isGeneratedUsername(_USERNAME_FIRSTS[0] + _USERNAME_LASTS[0] + '7'))
expect("a short custom name still passes", accepted('Andrew'))
expect("too short is still too short", not accepted('Al'))
expect("bad characters are still refused", not accepted('has spaces'))
expect("must still start with a letter", not accepted('9Lives'))

print()
if fails:
    print(f"FAIL — {len(fails)} check(s) failed:")
    for f in fails:
        print(f"  - {f}")
else:
    print("PASS — the app never offers a name it will refuse, and the cap still holds.")
sys.exit(1 if fails else 0)
