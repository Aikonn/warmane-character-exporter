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


    def test_lenient_links(self):
        from warmane_exporter.identity import parse_character_link
        for text in ("https://armory.warmane.com/character/Aikka/Onyxia/summary", "  armory.warmane.com/character/aikka/onyxia ",
                     "http://armory.warmane.com/character/Aikka/Onyxia/", '"https://armory.warmane.com/character/Aikka/Onyxia/summary?x=1"',
                     "https://armory.warmane.com/character/Aikka/Onyxia/profile#top"):
            found = parse_character_link(text)
            self.assertEqual((found.name.lower(), found.realm), ("aikka", "Onyxia"), text)
        for bad in ("", "https://example.com/character/A/Onyxia", "https://armory.warmane.com/character/A/Lordaeron", "Aikka"):
            with self.assertRaises(ValueError):
                parse_character_link(bad)


if __name__ == "__main__":
    unittest.main()
