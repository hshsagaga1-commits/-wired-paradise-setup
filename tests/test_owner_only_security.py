import unittest

from owner_only_security import (
    ADMINISTRATOR, MANAGE_CHANNELS, MANAGE_GUILD, MANAGE_ROLES,
    MANAGE_WEBHOOKS, PROTECTED_GUILD, PROTECTED_CHANNEL,
    CONFIRMATION, authorized, bot_user_ids, channel_fixes,
    role_fixes, updated_role_permissions,
)

SEND = 1 << 11
MANAGE_MESSAGES = 1 << 13
MODERATE_MEMBERS = 1 << 40


class OwnerOnlySecurityTests(unittest.TestCase):
    def test_owner_confirmation_and_server_fingerprint(self):
        self.assertEqual(CONFIRMATION, "SOMENTE DONO")
        self.assertFalse(authorized("123"))
        self.assertFalse(authorized("random"))

    def test_all_sensitive_permissions_covered(self):
        self.assertEqual(PROTECTED_GUILD & (
            ADMINISTRATOR | MANAGE_GUILD | MANAGE_ROLES |
            MANAGE_CHANNELS | MANAGE_WEBHOOKS
        ), PROTECTED_GUILD)

    def test_preserve_moderation_but_remove_admin_and_manage_server(self):
        role = {"id": "5", "name": "Moderação",
                "permissions": str(ADMINISTRATOR | MANAGE_GUILD |
                                   MANAGE_ROLES | MANAGE_MESSAGES |
                                   MODERATE_MEMBERS | SEND), "managed": False}
        new = updated_role_permissions(role)
        self.assertFalse(new & PROTECTED_GUILD)
        self.assertTrue(new & MANAGE_MESSAGES)
        self.assertTrue(new & MODERATE_MEMBERS)
        self.assertTrue(new & SEND)
        self.assertEqual(role["permissions"],
                         str(ADMINISTRATOR | MANAGE_GUILD | MANAGE_ROLES |
                             MANAGE_MESSAGES | MODERATE_MEMBERS | SEND))

    def test_role_audit_includes_everyone_and_preserves_bot(self):
        roles = [
            {"id": "1", "name": "@everyone", "permissions": str(MANAGE_GUILD),
             "managed": False},
            {"id": "2", "name": "Member", "permissions": "0", "managed": False},
            {"id": "3", "name": "Old Admin", "permissions": str(ADMINISTRATOR | SEND),
             "managed": False},
            {"id": "4", "name": "Loritta",
             "permissions": str(ADMINISTRATOR | MANAGE_GUILD),
             "managed": True, "tags": {"bot_id": "400"}},
        ]
        fixes = role_fixes(roles, "1")
        self.assertEqual({f["id"] for f in fixes}, {"1", "3"})
        self.assertNotIn("4", {f["id"] for f in fixes})
        self.assertEqual(next(f["new"] for f in fixes if f["id"] == "3"), SEND)
        self.assertEqual(roles[2]["permissions"], str(ADMINISTRATOR | SEND))

    def test_channel_overwrites_owner_and_bots_preserved(self):
        roles = [
            {"id": "12", "name": "Member", "managed": False, "permissions": "0"},
            {"id": "13", "name": "Loritta", "managed": True,
             "tags": {"bot_id": "230"}, "permissions": str(ADMINISTRATOR)},
        ]
        mask = PROTECTED_CHANNEL | SEND
        ch = {
            "id": "99", "name": "chat-geral", "type": 0,
            "permission_overwrites": [
                {"id": "12", "type": 0, "allow": str(mask), "deny": "0"},
                {"id": "13", "type": 0, "allow": str(mask), "deny": "0"},
                {"id": "230", "type": 1, "allow": str(mask), "deny": "0"},
                {"id": "240", "type": 1, "allow": str(mask), "deny": "0"},
                {"id": "300", "type": 1, "allow": str(mask), "deny": "0"},
            ]
        }
        self.assertEqual(bot_user_ids(roles), {"230"})
        changed = channel_fixes([ch], roles, owner_id="300", guild_id="1")
        self.assertEqual(len(changed), 1)
        updated = {item["id"]: item for item in changed[0]["overwrites"]}
        self.assertEqual(int(updated["12"]["allow"]), SEND)
        self.assertEqual(int(updated["240"]["allow"]), SEND)
        self.assertEqual(int(updated["13"]["allow"]), mask)
        self.assertEqual(int(updated["230"]["allow"]), mask)
        self.assertEqual(int(updated["300"]["allow"]), mask)
        self.assertEqual(int(ch["permission_overwrites"][0]["allow"]), mask)

    def test_audit_doesnt_mark_safe_roles_channels(self):
        roles = [{"id": "1", "name": "@everyone",
                  "permissions": str(SEND), "managed": False}]
        channels = [{"id": "99", "name": "chat",
                     "permission_overwrites": [
                         {"id": "1", "type": 0, "allow": str(SEND), "deny": "0"}
                     ]}]
        self.assertEqual(role_fixes(roles, "1"), [])
        self.assertEqual(channel_fixes(channels, roles, "1", "1"), [])


if __name__ == "__main__":
    unittest.main()
