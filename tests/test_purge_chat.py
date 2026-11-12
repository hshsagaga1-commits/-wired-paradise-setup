import unittest
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlsplit

from purge_chat import (
    CONFIRMATION, apply, authorized, delete_batch, list_messages,
    message_datetime, preview, select_target, split_batch,
)


NOW = datetime(2026, 11, 12, 15, 0, tzinfo=timezone.utc)


def snowflake(at, suffix=0):
    return str((int(at.timestamp() * 1000) - 1420070400000) * (2 ** 22) + suffix)


class FakeApi:
    def __init__(self, messages):
        self.messages = list(messages)
        self.operations = []

    def call(self, method, path, body=None):
        self.operations.append((method, path, body))
        if method == "GET" and path.startswith("/channels/99/messages?"):
            query = parse_qs(urlsplit("https://discord.test" + path).query)
            limit = int(query["limit"][0])
            before = query.get("before", [None])[0]
            source = [m for m in self.messages
                      if before is None or int(m["id"]) < int(before)]
            return source[:limit]
        if method == "POST" and path == "/channels/99/messages/bulk-delete":
            self.messages = [m for m in self.messages if m["id"] not in body["messages"]]
            return {}
        if method == "DELETE" and path.startswith("/channels/99/messages/"):
            to_remove = path.split("/")[-1]
            self.messages = [m for m in self.messages if m["id"] != to_remove]
            return {}
        raise AssertionError("Unexpected API call: " + method + " " + path)


class PurgeTests(unittest.TestCase):
    def test_select_exactly_chat_geral_in_comunidade(self):
        valid = [
            {"id": "1", "type": 4, "name": "COMUNIDADE"},
            {"id": "2", "type": 4, "name": "SEGURANÇA"},
            {"id": "99", "type": 0, "name": "chat-geral", "parent_id": "1"},
            {"id": "100", "type": 0, "name": "chat-geral", "parent_id": "2"},
            {"id": "101", "type": 0, "name": "spam", "parent_id": "1"},
        ]
        self.assertEqual(select_target(valid)["id"], "99")
        with self.assertRaises(Exception):
            select_target([c for c in valid if c["id"] != "99"])
        with self.assertRaises(Exception):
            select_target(valid + [dict(valid[2], id="199")])

    def test_snowflake_roundtrip_and_two_week_rule(self):
        fresh = snowflake(NOW - timedelta(days=1))
        old = snowflake(NOW - timedelta(days=40))
        self.assertLess(abs((message_datetime(fresh) - (NOW - timedelta(days=1))).total_seconds()), 0.01)
        recent, singles = split_batch([{"id": fresh}, {"id": old}], NOW)
        self.assertEqual(recent, [])
        self.assertEqual(singles, [old, fresh])  # singleton recent uses DELETE
        fresh2 = snowflake(NOW - timedelta(days=1), 1)
        recent, singles = split_batch([{"id": fresh}, {"id": fresh2}, {"id": old}], NOW)
        self.assertEqual(recent, [fresh, fresh2])
        self.assertEqual(singles, [old])

    def test_preview_only_reads_and_counts_pins(self):
        messages = [
            {"id": snowflake(NOW - timedelta(days=1), 2), "pinned": True},
            {"id": snowflake(NOW - timedelta(days=30), 1), "pinned": False},
        ]
        api = FakeApi(messages)
        count, ended = preview(api, "99", 100, now=NOW)
        self.assertEqual(count, 2)
        self.assertTrue(ended)
        self.assertEqual(len(api.messages), 2)
        self.assertTrue(all(method == "GET" for method, _, _ in api.operations))

    def test_apply_preserves_channel_and_removes_pins_and_old(self):
        messages = [
            {"id": snowflake(NOW - timedelta(days=1), 3), "pinned": True},
            {"id": snowflake(NOW - timedelta(days=1), 2), "pinned": False},
            {"id": snowflake(NOW - timedelta(days=40), 1), "pinned": False},
        ]
        api = FakeApi(messages)
        # This test's NOW is in 2026, but deletion is relative to the
        # actual system clock, so it may use single deletes. Both are valid.
        number = apply(api, "99", 100, sleep=lambda _: None)
        self.assertEqual(number, 3)
        self.assertEqual(api.messages, [])
        self.assertFalse(any("/channels/99" == p for _, p, _ in api.operations))
        self.assertFalse(any(method == "DELETE" and p == "/channels/99"
                             for method, p, _ in api.operations))

    def test_delete_recent_uses_bulk_when_two(self):
        fresh = [{"id": snowflake(NOW - timedelta(hours=2), x)} for x in (1, 2)]
        api = FakeApi(fresh)
        done = delete_batch(api, "99", fresh, now=NOW, sleep=lambda _: None)
        self.assertEqual(done, 2)
        self.assertTrue(any(op[0] == "POST" and op[1].endswith("/bulk-delete")
                            for op in api.operations))
        self.assertFalse(api.messages)

    def test_limit_and_authorization(self):
        self.assertEqual(CONFIRMATION, "APAGAR CHAT-GERAL")
        self.assertFalse(authorized("123"))
        with self.assertRaises(ValueError):
            list_messages(FakeApi([]), "99", limit=101)


if __name__ == "__main__":
    unittest.main()
