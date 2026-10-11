import unittest

from backend.phase3.security import (
    generate_session_token,
    hash_password,
    hash_session_token,
    validate_password,
    verify_password,
)


# Synthetic fixture for local cryptographic tests; never an account credential.
TEST_ONLY_PASSWORD = "UnitTestOnly!9_Fake"


class Phase3SecurityTests(unittest.TestCase):
    def test_passwords_use_argon2id(self):
        encoded = hash_password(TEST_ONLY_PASSWORD)
        self.assertTrue(encoded.startswith("$argon2id$"))
        self.assertTrue(verify_password(TEST_ONLY_PASSWORD, encoded))
        self.assertFalse(verify_password("wrong-password", encoded))

    def test_session_tokens_are_opaque_and_only_hash_is_persistable(self):
        token = generate_session_token()
        self.assertNotIn(".", token)
        self.assertGreaterEqual(len(token), 48)
        self.assertEqual(len(hash_session_token(token)), 64)

    def test_password_policy(self):
        with self.assertRaises(ValueError):
            validate_password("onlyletterslong")
        with self.assertRaises(ValueError):
            validate_password("123456789012")
        self.assertEqual(validate_password(TEST_ONLY_PASSWORD), TEST_ONLY_PASSWORD)


if __name__ == "__main__":
    unittest.main()
