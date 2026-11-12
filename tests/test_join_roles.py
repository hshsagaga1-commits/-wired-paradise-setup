import unittest
from join_roles import QUESTIONS, SELECTABLE_ROLES, authorized_guild, build_prompts, onboarding_ready


class JoinRolesTests(unittest.TestCase):
    def setUp(self):
        self.roles = {name: {"id": str(i + 100)} for i, name in enumerate(SELECTABLE_ROLES)}

    def test_all_questions_english_and_optional(self):
        self.assertEqual(len(QUESTIONS), 3)
        self.assertEqual([q[0] for q in QUESTIONS], [
            "How do you identify?",
            "What do you play on?",
            "Would you like notifications?",
        ])
        self.assertTrue(all(q[2] is False for q in QUESTIONS))

    def test_prompt_roles_and_privacy(self):
        result = build_prompts([], self.roles, "123")
        self.assertEqual(len(result), 3)
        self.assertEqual([o["title"] for o in result[0]["options"]],
                         ["Male", "Female", "Prefer not to say"])
        self.assertEqual(result[0]["options"][2]["role_ids"], [])
        self.assertEqual(result[0]["options"][2]["channel_ids"], ["123"])
        self.assertEqual(result[1]["options"][0]["role_ids"], [self.roles["PC"]["id"]])
        self.assertEqual(result[2]["options"][0]["role_ids"],
                         [self.roles["Notifications"]["id"]])
        self.assertEqual(result[2]["options"][1]["role_ids"], [])

    def test_existing_other_prompts_and_ids_preserved(self):
        existing = [
            {"id": "10", "title": "Other question", "options": []},
            {"id": "20", "title": "What do you play on?", "options": [
                {"id": "21", "title": "Mobile", "role_ids": []}
            ]},
        ]
        new = build_prompts(existing, self.roles, "123")
        self.assertEqual(new[0], existing[0])
        platform = next(p for p in new if p["title"] == "What do you play on?")
        self.assertEqual(platform["id"], "20")
        self.assertEqual(next(o for o in platform["options"]
                              if o["title"] == "Mobile")["id"], "21")
        self.assertEqual(len(new), 4)

    def test_onboarding_ready_checks_defaults_and_writable(self):
        gid = "999"
        channels = [
            {"id": str(i), "_guild_id": gid, "type": 0,
             "permission_overwrites": []}
            for i in range(7)
        ]
        self.assertTrue(onboarding_ready([str(i) for i in range(7)],
                                         channels, (1 << 10) | (1 << 11)))
        self.assertFalse(onboarding_ready([str(i) for i in range(6)],
                                          channels, (1 << 10) | (1 << 11)))
        channels[0]["permission_overwrites"] = [
            {"id": gid, "deny": str(1 << 11), "allow": "0"}
        ]
        channels[1]["permission_overwrites"] = [
            {"id": gid, "deny": str(1 << 11), "allow": "0"}
        ]
        channels[2]["permission_overwrites"] = [
            {"id": gid, "deny": str(1 << 11), "allow": "0"}
        ]
        self.assertFalse(onboarding_ready([str(i) for i in range(7)],
                                          channels, (1 << 10) | (1 << 11)))

    def test_wrong_guild_rejected(self):
        self.assertFalse(authorized_guild("123"))
        self.assertFalse(authorized_guild("not-a-number"))
        self.assertFalse(authorized_guild(""))


if __name__ == "__main__":
    unittest.main()
