"""Which names read too close to a new one, for the admin name-pool tools.

A name is compared on its BASE form (`database.connection.baseName`), lowercased, accents
and punctuation dropped: "Freed Marinara Jr." is the same lineage as "Freed Marinara", and
a field of near-identical names reads as a bug on a box score. The score is difflib's
ratio, taken on the names as written and with their words sorted, so "Smith John" and
"John Smith" read as the same name.
"""
import difflib
import re
import unicodedata

from constants import NAME_SIMILARITY_THRESHOLD

_NON_ALNUM = re.compile(r'[^a-z0-9 ]+')


def normalizeName(name: str) -> str:
    from database.connection import baseName
    name = baseName(' '.join((name or '').split()))
    name = unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode('ascii')
    return ' '.join(_NON_ALNUM.sub(' ', name.lower()).split())


def _sortedWords(norm: str) -> str:
    return ' '.join(sorted(norm.split()))


def nameSimilarity(a: str, b: str) -> float:
    """0..1 between two names, 1.0 when they are the same lineage."""
    na, nb = normalizeName(a), normalizeName(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    return max(difflib.SequenceMatcher(None, na, nb).ratio(),
               difflib.SequenceMatcher(None, _sortedWords(na), _sortedWords(nb)).ratio())


class NameIndex:
    """The names a new one is checked against, each tagged with where it lives
    ('pool', 'held', 'player', 'retired', 'coach', 'suggested'), normalized once."""

    def __init__(self, entries):
        self.entries = []
        seen = set()
        for name, source in entries:
            if not name or (name, source) in seen:
                continue
            seen.add((name, source))
            norm = normalizeName(name)
            if norm:
                self.entries.append((name, source, norm, _sortedWords(norm)))

    def similarTo(self, name: str, threshold: float = NAME_SIMILARITY_THRESHOLD,
                  limit: int = 5, exclude=()):
        """The closest names at or above `threshold`, best first:
        [{name, source, score, sameLineage}]. `exclude` drops exact names (a submission
        is not similar to itself)."""
        norm = normalizeName(name)
        if not norm:
            return []
        words = _sortedWords(norm)
        plain, sortedMatcher = difflib.SequenceMatcher(), difflib.SequenceMatcher()
        plain.set_seq2(norm)
        sortedMatcher.set_seq2(words)
        out = []
        for other, source, otherNorm, otherWords in self.entries:
            if other in exclude:
                continue
            if otherNorm == norm:
                score = 1.0
            else:
                score = 0.0
                for matcher, seq in ((plain, otherNorm), (sortedMatcher, otherWords)):
                    matcher.set_seq1(seq)
                    if (matcher.real_quick_ratio() >= threshold
                            and matcher.quick_ratio() >= threshold):
                        score = max(score, matcher.ratio())
            if score >= threshold:
                out.append({'name': other, 'source': source, 'score': round(score, 2),
                            'sameLineage': otherNorm == norm})
        out.sort(key=lambda m: (-m['score'], m['name']))
        return out[:limit]
