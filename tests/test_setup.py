import unittest
from setup import (
    CHANNELS, ROLE_SPECS, INVITE, VIEW, SEND, MENTION_ALL, ATTACH, EMBED,
    MODERATE_MEMBERS, ADMIN, find_channel, overwrites, automod, trap_rule,
)


class WiredParadiseTests(unittest.TestCase):
    def test_expected_channels(self):
        names = [name for specs in CHANNELS.values() for name, *_ in specs]
        self.assertEqual(len(names), len(set(names)))
        for name in (
            "anuncios", "chat-geral", "midias", "spam", "cargos",
            "meus-scripts", "metodos-de-qualidade", "logs-de-seguranca",
        ):
            self.assertIn(name, names)

    def test_owner_only(self):
        for name in ("anuncios", "cargos", "meus-scripts", "metodos-de-qualidade"):
            spec = next(s for specs in CHANNELS.values() for s in specs if s[0] == name)
            self.assertEqual(spec[4], "owner")
        perms = overwrites([], "123", "owner", owner_id="999")
        everyone = next(o for o in perms if o["id"] == "123")
        owner = next(o for o in perms if o["id"] == "999")
        self.assertTrue(int(everyone["deny"]) & SEND)
        self.assertTrue(int(owner["allow"]) & SEND)
        self.assertFalse(int(owner["deny"]) & SEND)

    def test_no_global_invite_or_mention(self):
        for policy in ("owner", "chat", "media", "spam", "logs", "voice"):
            overwrite = overwrites([], "123", policy)[0]
            self.assertEqual(
                int(overwrite["deny"]) & (INVITE | MENTION_ALL),
                INVITE | MENTION_ALL,
            )

    def test_chat_members_can_write_without_media(self):
        perms = overwrites([], "123", "chat")
        everyone = perms[0]
        self.assertTrue(int(everyone["allow"]) & SEND)
        self.assertEqual(int(everyone["deny"]) & (ATTACH | EMBED), ATTACH | EMBED)
        self.assertEqual(int(everyone["allow"]) & (ATTACH | EMBED), 0)

    def test_media_allows_text_and_attachments(self):
        everyone = overwrites([], "123", "media")[0]
        self.assertEqual(int(everyone["allow"]) & (SEND | ATTACH | EMBED),
                         SEND | ATTACH | EMBED)

    def test_security_logs_private_with_moderator_access(self):
        perms = overwrites([], "123", "logs", owner_id="999", moderator_id="456")
        everyone = next(p for p in perms if p["id"] == "123")
        moderator = next(p for p in perms if p["id"] == "456")
        owner = next(p for p in perms if p["id"] == "999")
        self.assertTrue(int(everyone["deny"]) & VIEW)
        self.assertTrue(int(moderator["allow"]) & VIEW)
        self.assertTrue(int(owner["allow"]) & VIEW)

    def test_removes_role_bypass_from_readonly_channels(self):
        perms = overwrites(
            [{"id": "456", "type": 0, "allow": str(SEND | VIEW), "deny": "0"}],
            "123", "owner", owner_id="999",
        )
        old_role = next(p for p in perms if p["id"] == "456")
        self.assertFalse(int(old_role["allow"]) & SEND)
        self.assertTrue(int(old_role["allow"]) & VIEW)

    def test_removes_role_bypass_from_chat_uploads(self):
        perms = overwrites(
            [{"id": "456", "type": 0,
              "allow": str(ATTACH | EMBED | SEND), "deny": "0"}],
            "123", "chat",
        )
        role = next(p for p in perms if p["id"] == "456")
        self.assertEqual(int(role["allow"]) & (ATTACH | EMBED), 0)
        self.assertTrue(int(role["allow"]) & SEND)

    def test_preserves_other_permissions(self):
        original = [{"id": "456", "type": 0, "allow": str(VIEW), "deny": "0"}]
        results = overwrites(original, "123", "media")
        self.assertEqual(results[0], original[0])

    def test_channel_lookup_respects_parent(self):
        channels = [{"name": "chat-geral", "type": 0, "id": "2", "parent_id": "1"}]
        self.assertIsNotNone(find_channel(channels, "chat-geral", 0, "1"))
        self.assertIsNone(find_channel(channels, "chat-geral", 0, "3"))

    def test_owner_role_has_no_administrator(self):
        owner = next(spec for spec in ROLE_SPECS if spec[0] == "👑 Dono")
        self.assertFalse(owner[2] & ADMIN)
        moderator = next(spec for spec in ROLE_SPECS if spec[0] == "Moderação")
        self.assertTrue(moderator[2] & MODERATE_MEMBERS)
        self.assertFalse(moderator[2] & ADMIN)

    def test_spam_trap_blocks_any_text(self):
        channels = [
            {"id": "1", "name": "spam", "type": 0},
            {"id": "2", "name": "chat-geral", "type": 0},
            {"id": "3", "name": "midias", "type": 0},
        ]
        spec = trap_rule("4", channels, "1")
        self.assertEqual(spec["trigger_metadata"]["regex_patterns"], [r"[\s\S]+"])
        self.assertEqual(spec["exempt_channels"], ["2", "3"])
        self.assertEqual(spec["actions"][-1]["type"], 3)
        self.assertNotIn("ban", str(spec).lower())

    def test_spam_trap_warns_in_channel_description(self):
        spam = next(s for specs in CHANNELS.values() for s in specs if s[0] == "spam")
        self.assertIn("BAN", spam[2])
        self.assertIn("NÃO ESCREVA", spam[2])
        self.assertEqual(spam[4], "spam")

    def test_spam_trap_refuses_too_many_exempt_channels(self):
        channels = [{"id": str(i), "type": 0} for i in range(60)]
        with self.assertRaises(ValueError):
            trap_rule("100", channels, "0")

    def test_raid_rule_enabled(self):
        spec = automod("WP | Anti-raid de menções", 5, "111")
        self.assertEqual(spec["trigger_metadata"]["mention_total_limit"], 5)
        self.assertTrue(spec["enabled"])


if __name__ == "__main__":
    unittest.main()
