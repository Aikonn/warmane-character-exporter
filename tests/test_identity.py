import unittest

from warmane_exporter.identity import parse_character_url


class IdentityTests(unittest.TestCase):
    def test_summary_url_parses(self) -> None:
        identity = parse_character_url("https://armory.warmane.com/character/Aikka/Onyxia/summary")
        self.assertEqual(identity.name, "Aikka")
        self.assertEqual(identity.realm, "Onyxia")
        self.assertEqual(identity.view, "summary")
        self.assertEqual(identity.canonical_url, "https://armory.warmane.com/character/Aikka/Onyxia/summary")

    def test_profile_url_parses_and_canonicalizes(self) -> None:
        identity = parse_character_url("https://armory.warmane.com/character/Aikka/Icecrown/profile")
        self.assertEqual(identity.realm, "Icecrown")
        self.assertEqual(identity.view, "profile")
        self.assertEqual(identity.request_url, "https://armory.warmane.com/character/Aikka/Icecrown/profile")
        self.assertEqual(identity.canonical_url, "https://armory.warmane.com/character/Aikka/Icecrown/summary")

    def test_invalid_host_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unsupported host"):
            parse_character_url("https://example.com/character/Aikka/Onyxia/summary")

    def test_invalid_realm_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unsupported realm"):
            parse_character_url("https://armory.warmane.com/character/Aikka/Blackrock/summary")


if __name__ == "__main__":
    unittest.main()
