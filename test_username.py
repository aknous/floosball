"""The app never offers a username it would then refuse.

⚠️ THE FAILURE WAS ASYMMETRIC. The generator pairs 255 firsts with 260 lasts and adds
up to two digits; 14,786 of those 66,300 pairings run past USERNAME_MAX_LEN. The server
grandfathered them, but the ONBOARDING CLIENT applies the plain rule to every path
including a clicked suggestion, so an over-long offer showed "20 characters or fewer"
and the pick never left the browser. The server exemption could not help, because
nothing was ever sent.

Measured on production: 36 of 157 named users (23%) carry a generated name past the
cap, handed to them by auto-provisioning at signup. They stay valid — the exemption is
grandfathering for those accounts, not a licence for the generator.
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


class UsernameTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.tmp.close()
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from database.models import Base
        import api.auth as auth

        self.auth = auth
        self.engine = create_engine(f'sqlite:///{self.tmp.name}')
        Base.metadata.create_all(bind=self.engine)
        self.session = sessionmaker(bind=self.engine)()

    def tearDown(self):
        self.session.close()
        self.engine.dispose()
        os.unlink(self.tmp.name)

    # -- the vocabulary itself ---------------------------------------------

    def testTheVocabularyStillContainsOverLongPairings(self):
        """If this ever fails the screening has become dead code, not redundant.

        The rule is enforced at draw time rather than by curating the word lists, so
        the lists are expected to keep producing names that need rejecting.
        """
        longest = (max(self.auth._USERNAME_FIRSTS, key=len)
                   + max(self.auth._USERNAME_LASTS, key=len) + '99')
        self.assertGreater(len(longest), self.auth.USERNAME_MAX_LEN)

    # -- screening ---------------------------------------------------------

    def testScreeningRejectsAnOverLongName(self):
        self.assertTrue(self.auth._usernameSuggestionRejected('A' * (self.auth.USERNAME_MAX_LEN + 1)))

    def testScreeningAcceptsAnExactlyMaxLengthName(self):
        # Off-by-one guard: the cap is inclusive.
        self.assertFalse(self.auth._usernameSuggestionRejected('A' * self.auth.USERNAME_MAX_LEN))

    # -- the generators ----------------------------------------------------

    def testCandidatesAreNeverOverLong(self):
        # Enough draws to cover the 22% that used to slip through.
        for _ in range(60):
            for name in self.auth.generateUsernameCandidates(self.session, count=4):
                self.assertLessEqual(len(name), self.auth.USERNAME_MAX_LEN, name)

    def testEverySuggestionPassesTheValidatorWithoutTheExemption(self):
        """The real assertion: a suggestion must stand on its own merits.

        Checked WITHOUT `isGeneratedUsername`, because the client has no access to the
        server's vocabulary and cannot apply that exemption.
        """
        for _ in range(40):
            for name in self.auth.generateUsernameCandidates(self.session, count=4):
                chosen, err = self.auth.validateUsername(name)
                self.assertIsNone(err, f'{name}: {err}')
                self.assertLessEqual(len(name), self.auth.USERNAME_MAX_LEN, name)

    def testSingleCandidateIsNeverOverLong(self):
        for _ in range(80):
            name = self.auth._generateUsernameCandidate(self.session)
            self.assertLessEqual(len(name), self.auth.USERNAME_MAX_LEN, name)

    def testCandidatesAreDistinct(self):
        names = self.auth.generateUsernameCandidates(self.session, count=4)
        self.assertEqual(len(names), len(set(names)))

    def testCandidatesAvoidNamesAlreadyTaken(self):
        from database.models import User
        taken = self.auth.generateUsernameCandidates(self.session, count=1)[0]
        self.session.add(User(clerk_id='c1', email='c1@example.com', username=taken))
        self.session.commit()
        for _ in range(40):
            self.assertNotIn(taken, self.auth.generateUsernameCandidates(self.session, count=4))

    def testCandidatesStillArriveWhenAskedForFour(self):
        # Screening removes a fifth of the space; the retry budget must absorb that.
        for _ in range(30):
            self.assertEqual(len(self.auth.generateUsernameCandidates(self.session, count=4)), 4)

    # -- leading character -------------------------------------------------

    def testANameMayStartWithAnUnderscoreOrADigit(self):
        for name in ('_floosfan', '99Problems', '_99', 'x_9'):
            chosen, err = self.auth.validateUsername(name)
            self.assertIsNone(err, f'{name}: {err}')

    def testTheCharacterSetItselfDidNotWiden(self):
        # Only the LEADING rule opened up. Punctuation is still out, which is what
        # keeps lookalikes from being buildable out of dots and dashes.
        for name in ('floos-fan', '.floos', 'floos fan', 'floos!'):
            chosen, err = self.auth.validateUsername(name)
            self.assertIsNotNone(err, name)

    def testReservedNamesSurviveALeadingUnderscore(self):
        """Allowing a leading underscore re-opens the route the list exists to close.

        "_admin" and "_cassian_" clear a plain membership test while reading in a feed
        as exactly the name they imitate, so separators are stripped before the check.
        """
        for name in ('_admin', 'admin_', '_cassian_', '__vera__', 'admin1', '_mod_'):
            chosen, err = self.auth.validateUsername(name)
            self.assertEqual(err, 'That name is reserved', f'{name}: {err}')

    def testStrippingDoesNotOverReach(self):
        # A real name that merely CONTAINS a reserved word is not reserved.
        for name in ('_administrator_of_nothing', 'Veranda', 'Coreymatic'):
            chosen, err = self.auth.validateUsername(name)
            self.assertNotEqual(err, 'That name is reserved', name)

    # -- grandfathering ----------------------------------------------------

    def testAnAlreadyIssuedLongNameStaysValid(self):
        """The 36 production users must not be locked out of their own identity."""
        long = None
        for first in self.auth._USERNAME_FIRSTS:
            for last in self.auth._USERNAME_LASTS:
                if len(first + last + '94') > self.auth.USERNAME_MAX_LEN:
                    long = first + last + '94'
                    break
            if long:
                break
        self.assertIsNotNone(long)
        chosen, err = self.auth.validateUsername(long)
        self.assertIsNone(err, f'{long}: {err}')

    def testAMadeUpLongNameIsStillRefused(self):
        # The exemption is verified against the generator's own vocabulary, so it
        # cannot be used to smuggle an arbitrary over-long name past the cap.
        chosen, err = self.auth.validateUsername('Zzzzqqqxxvvbbnnmmllkk99')
        self.assertIsNotNone(err)


if __name__ == '__main__':
    unittest.main(verbosity=2)
