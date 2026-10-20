"""A valid token with a failing database is a 500, not a 401, and the optional-auth
path does not quietly serve that caller as signed out (prod, 2026-10-20).

Run: python test_auth_db_failure.py
"""
import unittest
from unittest import mock

from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from api import auth


class _BrokenSession:
    def query(self, *a, **kw):
        raise RuntimeError('database or disk is full')

    def rollback(self):
        pass

    def close(self):
        pass


def _creds():
    return HTTPAuthorizationCredentials(scheme='Bearer', credentials='tok')


class AuthDbFailureTests(unittest.TestCase):
    def setUp(self):
        key = mock.Mock(key='k')
        client = mock.Mock(get_signing_key_from_jwt=mock.Mock(return_value=key))
        self.patches = [
            mock.patch.object(auth, '_getJwksClient', return_value=client),
            mock.patch.object(auth.pyjwt, 'decode', return_value={'sub': 'user_x'}),
            mock.patch.object(auth, 'get_session', return_value=_BrokenSession()),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()

    def testDatabaseFailureIsA500(self):
        with self.assertRaises(HTTPException) as ctx:
            auth.getCurrentUser(_creds())
        self.assertEqual(ctx.exception.status_code, 500)

    def testOptionalAuthDoesNotHideIt(self):
        with self.assertRaises(HTTPException) as ctx:
            auth.getOptionalUser(_creds())
        self.assertEqual(ctx.exception.status_code, 500)

    def testABadTokenIsStillAnonymous(self):
        with mock.patch.object(auth.pyjwt, 'decode', side_effect=ValueError('bad sig')):
            with self.assertRaises(HTTPException) as ctx:
                auth.getCurrentUser(_creds())
            self.assertEqual(ctx.exception.status_code, 401)
            self.assertIsNone(auth.getOptionalUser(_creds()))


if __name__ == '__main__':
    unittest.main()
