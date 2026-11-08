import unittest
from setup import CHANNELS, INVITE, VIEW, SEND, MENTION_ALL, find_channel, overwrites, automod


class WiredParadiseTests(unittest.TestCase):
    def test_channels_unique(self):
        names = [n for group in CHANNELS.values() for n, *_ in group]
        self.assertEqual(len(names), len(set(names)))

    def test_default_members_cannot_create_invites_or_mention_everyone(self):
        o = overwrites([], "123", "COMUNIDADE")[0]
        self.assertTrue(int(o["deny"]) & INVITE)
        self.assertTrue(int(o["deny"]) & MENTION_ALL)

    def test_security_logs_not_visible_to_everyone(self):
        o = overwrites([], "123", "SEGURANÇA")[0]
        self.assertTrue(int(o["deny"]) & VIEW)

    def test_scripts_read_only(self):
        o = overwrites([], "123", "MEUS PROJETOS", True)[0]
        self.assertTrue(int(o["deny"]) & SEND)

    def test_preserves_other_roles(self):
        existing = [{"id": "456", "type": 0, "allow": "1024", "deny": "0"}]
        o = overwrites(existing, "123", "COMUNIDADE")
        self.assertEqual(o[0], existing[0])

    def test_removes_conflicting_allow_bits(self):
        existing = [{"id": "123", "type": 0, "allow": str(INVITE | VIEW), "deny": "0"}]
        o = overwrites(existing, "123", "SEGURANÇA")
        self.assertEqual(int(o[0]["allow"]) & (INVITE | VIEW), 0)

    def test_matches_category(self):
        channels = [{"name": "chat-geral", "type": 0, "parent_id": "1", "id": "2"}]
        self.assertIsNotNone(find_channel(channels, "chat-geral", 0, "1"))
        self.assertIsNone(find_channel(channels, "chat-geral", 0, "3"))

    def test_raid_rule_enabled(self):
        spec = automod("WP Anti-raid", 5, "111")
        self.assertEqual(spec["trigger_metadata"]["mention_total_limit"], 5)
        self.assertTrue(spec["enabled"])


if __name__ == "__main__":
    unittest.main()
