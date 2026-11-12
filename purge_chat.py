#!/usr/bin/env python3
"""Manual, strictly scoped Discord message deletion for Wired Paradise.

Only #chat-geral in COMUNIDADE on the authorized server is eligible.
PREVIEW is read-only. APPLY requires both a mode selection and a phrase.
Never delete channels, pins selectively, roles, members or other channels.
"""
import hashlib
import hmac
import os
import sys
import time
from datetime import datetime, timedelta, timezone

from setup import API, DiscordError, AUTHORIZED_GUILD_SHA256

CATEGORY_NAME = "COMUNIDADE"
CHANNEL_NAME = "chat-geral"
CONFIRMATION = "APAGAR CHAT-GERAL"
DISCORD_EPOCH_MS = 1420070400000
MAX_ALLOWED = 2000
BULK_SAFETY_MARGIN = timedelta(minutes=10)


def authorized(guild_id):
    return bool(guild_id and guild_id.isascii() and guild_id.isdecimal()
                and hmac.compare_digest(
                    hashlib.sha256(guild_id.encode("ascii")).hexdigest(),
                    AUTHORIZED_GUILD_SHA256))


def select_target(channels):
    """Fail closed unless there is exactly one matching text channel."""
    parents = [c for c in channels
               if c.get("type") == 4 and c.get("name") == CATEGORY_NAME]
    if len(parents) != 1:
        raise DiscordError("Expected exactly one COMUNIDADE category; no deletion.")
    matches = [c for c in channels
               if c.get("type") == 0 and c.get("name") == CHANNEL_NAME
               and c.get("parent_id") == parents[0]["id"]]
    if len(matches) != 1:
        raise DiscordError("Expected exactly one COMUNIDADE/#chat-geral; no deletion.")
    return matches[0]


def message_datetime(message_id):
    """Discord snowflake timestamp in UTC, without needing message content."""
    millis = (int(message_id) >> 22) + DISCORD_EPOCH_MS
    return datetime.fromtimestamp(millis / 1000, tz=timezone.utc)


def split_batch(messages, now):
    """Bulk-delete only IDs comfortably under 14 days old."""
    cutoff = now - timedelta(days=14) + BULK_SAFETY_MARGIN
    bulk = []
    singles = []
    for message in messages:
        (bulk if message_datetime(message["id"]) > cutoff else singles).append(
            message["id"])
    # A one-message bulk request is invalid.
    if len(bulk) == 1:
        singles.extend(bulk)
        bulk = []
    return bulk, singles


def list_messages(api, channel_id, before=None, limit=100):
    if limit < 1 or limit > 100:
        raise ValueError("Discord pagination limit must be 1..100")
    path = "/channels/" + str(channel_id) + "/messages?limit=" + str(limit)
    if before:
        path += "&before=" + str(before)
    messages = api.call("GET", path)
    if not isinstance(messages, list):
        raise DiscordError("Unexpected Discord messages response; no deletion.")
    return messages


def preview(api, channel_id, cap, now=None):
    """Read-only scan limited to cap; no user message content appears in logs."""
    now = now or datetime.now(timezone.utc)
    total = pinned = recent = old = 0
    before = None
    ended = False
    while total < cap:
        page = list_messages(api, channel_id, before, min(100, cap - total))
        if not page:
            ended = True
            break
        total += len(page)
        pinned += sum(bool(m.get("pinned")) for m in page)
        cutoff = now - timedelta(days=14) + BULK_SAFETY_MARGIN
        recent += sum(message_datetime(m["id"]) > cutoff for m in page)
        old += sum(message_datetime(m["id"]) <= cutoff for m in page)
        before = page[-1]["id"]
        if len(page) < min(100, cap - (total - len(page))):
            ended = True
            break
    print("PREVIEW ONLY. No messages were deleted.")
    print("Target: COMUNIDADE/#chat-geral")
    print("Scanned message count:", total)
    print("Pinned messages within scan:", pinned)
    print("Within bulk-delete age range:", recent)
    print("Requires per-message deletion:", old)
    if not ended:
        print("LIMIT REACHED: older messages may exist beyond the scan.")
    print("Apply permanently deletes messages INCLUDING pinned messages.")
    print("If more than the chosen limit exist, run this action again to continue.")
    return total, ended


def delete_single(api, channel_id, message_id):
    try:
        api.call("DELETE", f"/channels/{channel_id}/messages/{message_id}")
        return True
    except DiscordError as error:
        # Concurrent moderation may already have removed the message.
        if str(error).startswith("Discord HTTP 404:"):
            print("One message was already removed.")
            return False
        raise


def delete_batch(api, channel_id, messages, now=None, sleep=time.sleep):
    """Delete a fetched page; respect both Discord deletion APIs."""
    now = now or datetime.now(timezone.utc)
    bulk_ids, single_ids = split_batch(messages, now)
    completed = 0
    if bulk_ids:
        api.call("POST", f"/channels/{channel_id}/messages/bulk-delete",
                 {"messages": bulk_ids})
        completed += len(bulk_ids)
    for message_id in single_ids:
        if delete_single(api, channel_id, message_id):
            completed += 1
        # Avoid rapid single-message DELETE bursts, especially with old history.
        sleep(1.2)
    return completed


def apply(api, channel_id, cap, sleep=time.sleep):
    """Re-fetch from newest after each page, so old messages aren't skipped."""
    attempted = 0
    deleted = 0
    try:
        while attempted < cap:
            page = list_messages(api, channel_id, limit=min(100, cap - attempted))
            if not page:
                break
            removed = delete_batch(api, channel_id, page, sleep=sleep)
            deleted += removed
            attempted += len(page)
            print(f"Progress: processed {attempted}; deleted {deleted} messages.")
            # Even in all-recent channels, avoid hammering the API.
            sleep(0.8)
    except DiscordError:
        print(f"STOPPED: deleted {deleted} messages before the API error. "
              "Rerun preview to see what remains.")
        raise

    remaining = list_messages(api, channel_id, limit=1)
    print(f"COMPLETE THIS RUN: {deleted} messages removed from #chat-geral.")
    if remaining:
        print("MORE MESSAGES REMAIN. Repeat preview and apply if you want all history deleted.")
    else:
        print("CHANNEL EMPTY at the final check. Channel and permissions were preserved.")
    return deleted


def main():
    mode = os.environ.get("WP_PURGE_MODE", "preview").strip()
    confirm = os.environ.get("WP_PURGE_CONFIRM", "").strip()
    token = os.environ.get("DISCORD_BOT_TOKEN", "").strip()
    guild_id = os.environ.get("DISCORD_GUILD_ID", "").strip()
    cap_str = os.environ.get("WP_PURGE_LIMIT", "500").strip()
    if mode not in ("preview", "apply"):
        sys.exit("Invalid mode: choose preview or apply.")
    if mode == "apply" and confirm != CONFIRMATION:
        sys.exit("No deletion: choose apply AND enter APAGAR CHAT-GERAL.")
    if cap_str not in ("100", "500", "2000") or int(cap_str) > MAX_ALLOWED:
        sys.exit("Invalid limit: choose 100, 500 or 2000.")
    if not token or not authorized(guild_id):
        sys.exit("Missing token or unauthorized server. No deletion.")

    api = API(token)
    guild = api.call("GET", "/guilds/" + guild_id)
    if str(guild.get("id")) != guild_id:
        raise DiscordError("Server identity mismatch; no deletion.")
    target = select_target(api.call("GET", "/guilds/" + guild_id + "/channels"))
    print("Authorized target found: COMUNIDADE/#chat-geral.")
    print("Channel ID verified internally; no channels will be deleted.")
    print("Limit:", cap_str, "messages this run")
    if mode == "preview":
        preview(api, target["id"], int(cap_str))
    else:
        print("APPLY CONFIRMED: permanently deleting messages, including pinned ones.")
        apply(api, target["id"], int(cap_str))


if __name__ == "__main__":
    try:
        main()
    except DiscordError as error:
        sys.exit("Discord purge error: " + str(error))
