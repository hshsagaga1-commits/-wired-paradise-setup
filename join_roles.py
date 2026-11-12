#!/usr/bin/env python3
"""Wired Paradise — one-shot English welcome + onboarding configuration.

Safe workflow modes: preview (GET only), apply (explicit confirmation), audit (GET only).
This is not a bot running 24/7; configure Loritta AutoRole and custom greetings
from the Loritta dashboard for new-member events.
"""
import hashlib
import hmac
import os
import sys

from setup import API, DiscordError, AUTHORIZED_GUILD_SHA256

VIEW = 1 << 10
SEND = 1 << 11
HISTORY = 1 << 16
INVITE = 1 << 0
MENTION_ALL = 1 << 17
SEND_IN_THREADS = 1 << 38
CREATE_PUBLIC_THREADS = 1 << 35
CREATE_PRIVATE_THREADS = 1 << 36

SELECTABLE_ROLES = {
    "Male": 0xA9A9A9,
    "Female": 0xD3D3D3,
    "PC": 0xB0B0B0,
    "Mobile": 0x999999,
    "Console": 0x777777,
    "Notifications": 0xE0E0E0,
}

# title, one selection at most, required, (answer, role, emoji)
QUESTIONS = (
    ("How do you identify?", True, False, (
        ("Male", "Male", "👨"),
        ("Female", "Female", "👩"),
        ("Prefer not to say", None, "🔒"),
    )),
    ("What do you play on?", False, False, (
        ("PC", "PC", "🖥️"),
        ("Mobile", "Mobile", "📱"),
        ("Console", "Console", "🎮"),
    )),
    ("Would you like notifications?", True, False, (
        ("Yes, notify me", "Notifications", "🔔"),
        ("No, thanks", None, "🔕"),
    )),
)

# These are useful, deliberately selected default channels rather than dummy
# channels added solely to pass Discord's onboarding limits.
ENTRY_CHANNELS = (
    ("WELCOME", "welcome", False,
     "Welcome to Wired Paradise! Check #rules and pick your roles."),
    ("WELCOME", "rules", False,
     "Community guidelines — read before participating."),
    ("COMUNIDADE", "introductions", True,
     "Introduce yourself to the community."),
    ("COMUNIDADE", "gaming-chat", True,
     "Discuss your favorite games and gaming platforms."),
    ("COMUNIDADE", "off-topic", True,
     "Everything that doesn't fit elsewhere."),
)
DEFAULT_CHANNEL_NAMES = (
    "welcome", "rules", "chat-geral", "midias",
    "introductions", "gaming-chat", "off-topic",
)
PRIVATE_OR_UNSAFE_CHANNEL_NAMES = {
    "spam", "logs-de-seguranca", "meus-scripts",
    "metodos-de-qualidade", "anuncios", "cargos",
}


def authorized_guild(guild_id):
    return bool(guild_id and guild_id.isascii() and guild_id.isdecimal()
                and hmac.compare_digest(
                    hashlib.sha256(guild_id.encode("ascii")).hexdigest(),
                    AUTHORIZED_GUILD_SHA256
                ))


def make_option(title, role_id, emoji, old=None, neutral_channel=None):
    # Skip / no-notifications answers have no personal-identifying role.
    result = {
        "title": title,
        "description": None,
        "role_ids": [str(role_id)] if role_id else [],
        "channel_ids": [str(neutral_channel)] if not role_id and neutral_channel else [],
        "emoji_id": None,
        "emoji_name": emoji,
        "emoji_animated": False,
    }
    if old and old.get("id"):
        result["id"] = old["id"]
    return result


def build_prompts(existing, roles, neutral_channel):
    """Merge by title and preserve unrelated prompts and existing prompt IDs."""
    prompts = [dict(p) for p in (existing or [])]
    for title, single, required, answers in QUESTIONS:
        old = next((p for p in prompts if p.get("title") == title), None)
        older_options = {o.get("title"): o for o in old.get("options", [])} if old else {}
        options = [
            make_option(answer, roles.get(role_name, {}).get("id") if role_name else None,
                        emoji, older_options.get(answer), neutral_channel)
            for answer, role_name, emoji in answers
        ]
        spec = {
            "title": title,
            "type": 0,
            "single_select": single,
            "required": required,
            "in_onboarding": True,
            "options": options,
        }
        if old:
            spec["id"] = old["id"]
            prompts[prompts.index(old)] = spec
        else:
            prompts.append(spec)
    return prompts


def ensure_roles(api, guild_id, initial):
    """Reuse or rename Member without losing any existing assignments."""
    roles = list(initial)
    for name in ("Member", *SELECTABLE_ROLES):
        role = next((r for r in roles if r.get("name") == name), None)
        if name == "Member" and not role:
            role = next((r for r in roles if r.get("name") == "Membro"
                         and not r.get("managed")), None)
            if role:
                api.call("PATCH", f"/guilds/{guild_id}/roles/{role['id']}",
                         {"name": "Member"})
                role["name"] = "Member"
                print("Renamed Membro to Member — previous assignments retained.")
        if not role:
            role = api.call("POST", f"/guilds/{guild_id}/roles", {
                "name": name, "color": SELECTABLE_ROLES.get(name, 0xFFFFFF),
                "permissions": "0", "hoist": False, "mentionable": False,
            })
            roles.append(role)
            print("Created role:", name)
        else:
            print("Existing role:", name)
        if role.get("managed") or int(role.get("permissions", 0)) & (1 << 3):
            raise DiscordError(f"Role {name} is managed or has Administrator. Stop for manual review.")
    return {name: next(r for r in roles if r.get("name") == name)
            for name in ("Member", *SELECTABLE_ROLES)}


def permission_overwrites(guild_id, sendable):
    allow = VIEW | HISTORY | (SEND if sendable else 0)
    deny = INVITE | MENTION_ALL | (0 if sendable else
            SEND | SEND_IN_THREADS | CREATE_PUBLIC_THREADS | CREATE_PRIVATE_THREADS)
    return [{"id": guild_id, "type": 0,
             "allow": str(allow), "deny": str(deny)}]


def ensure_entry_channels(api, guild_id, channels):
    """Create only requested welcome and purposeful community channels."""
    channels = list(channels)
    results = {}
    for category_name, name, sendable, topic in ENTRY_CHANNELS:
        category = next((c for c in channels if c.get("type") == 4
                         and c.get("name") == category_name), None)
        if not category:
            category = api.call("POST", f"/guilds/{guild_id}/channels",
                                {"name": category_name, "type": 4})
            channels.append(category)
            print("Created category:", category_name)
        existing = next((c for c in channels if c.get("type") == 0
                         and c.get("name") == name
                         and c.get("parent_id") == category["id"]), None)
        if not existing:
            existing = api.call("POST", f"/guilds/{guild_id}/channels", {
                "name": name,
                "type": 0,
                "parent_id": category["id"],
                "topic": topic,
                "permission_overwrites": permission_overwrites(guild_id, sendable),
            })
            channels.append(existing)
            print("Created #"+name)
        else:
            print("Existing #"+name+" preserved")
        results[name] = existing
    return channels, results


def can_everyone_send(channel, guild_id, everyone_permissions):
    if channel.get("type") != 0:
        return False
    bits = everyone_permissions
    override = next((o for o in channel.get("permission_overwrites", [])
                     if str(o.get("id")) == guild_id and o.get("type") == 0), None)
    if override:
        bits = (bits & ~int(override.get("deny", "0"))) | int(override.get("allow", "0"))
    return (bits & (VIEW | SEND)) == (VIEW | SEND)


def can_everyone_view(channel, guild_id, everyone_permissions):
    if channel.get("type") != 0:
        return False
    bits = everyone_permissions
    override = next((o for o in channel.get("permission_overwrites", [])
                     if str(o.get("id")) == guild_id and o.get("type") == 0), None)
    if override:
        bits = (bits & ~int(override.get("deny", "0"))) | int(override.get("allow", "0"))
    return bool(bits & VIEW)


def onboarding_ready(default_ids, channels, everyone_permissions):
    """Pure readiness check. Uses every channel's injected _guild_id."""
    by_id = {c["id"]: c for c in channels}
    selected = {i for i in default_ids if i in by_id}
    if len(selected) < 7:
        return False
    writable = sum(can_everyone_send(by_id[i], str(by_id[i].get("_guild_id", "")),
                                     everyone_permissions) for i in selected)
    return writable >= 5


def select_default_channels(channels, guild_id, everyone_permissions):
    """At least 7 useful public defaults, including 5 writable ones.

    Never make the spam trap or private security channels into entry channels.
    """
    selected = []
    safe_channels = [
        c for c in channels if c.get("type") == 0
        and c.get("name") not in PRIVATE_OR_UNSAFE_CHANNEL_NAMES
        and can_everyone_view(c, guild_id, everyone_permissions)
    ]
    by_name = {c.get("name"): c for c in safe_channels}
    for name in DEFAULT_CHANNEL_NAMES:
        c = by_name.get(name)
        if c and c["id"] not in selected:
            selected.append(c["id"])
    for c in safe_channels:
        if c["id"] not in selected and len(selected) < 7:
            selected.append(c["id"])
    writable = sum(can_everyone_send(c, guild_id, everyone_permissions)
                   for c in safe_channels if c["id"] in selected)
    if len(selected) < 7 or writable < 5:
        raise DiscordError(
            "Onboarding needs >=7 visible default channels and >=5 writable by @everyone. "
            f"Found {len(selected)} channels / {writable} writable. "
            "Check @everyone permissions without opening #spam."
        )
    return selected


def enable_community_if_needed(api, guild_id, guild, rules_id, updates_id):
    if "COMMUNITY" in guild.get("features", []):
        print("Community already enabled.")
        return guild
    if not rules_id or not updates_id:
        raise DiscordError("Cannot enable Community without rules and moderator updates channels.")
    patch = {
        "features": list(dict.fromkeys([*guild.get("features", []), "COMMUNITY"])),
        "rules_channel_id": rules_id,
        "public_updates_channel_id": updates_id,
        "verification_level": max(1, int(guild.get("verification_level", 0))),
        "explicit_content_filter": 2,
        "default_message_notifications": 1,
    }
    print("Enabling Discord Community (not Server Discovery / public directory).")
    try:
        updated = api.call("PATCH", f"/guilds/{guild_id}", patch)
    except DiscordError as error:
        raise DiscordError("Could not enable Community (bot Administrator permission "
                           "and server requirements may be needed): " + str(error)) from None
    if "COMMUNITY" not in updated.get("features", []):
        raise DiscordError("Community enable request returned without COMMUNITY feature.")
    print("Community enabled.")
    return updated


def set_native_welcome(api, guild_id, guild, welcome_id):
    # Discord sends native system join messages. A user-specific custom ping
    # still requires a real-time bot like Loritta with Greetings configured.
    old_flags = int(guild.get("system_channel_flags") or 0)
    patch = {
        "system_channel_id": welcome_id,
        "system_channel_flags": old_flags & ~1,  # Unsuppress join notifications
    }
    updated = api.call("PATCH", f"/guilds/{guild_id}", patch)
    if updated.get("system_channel_id") != welcome_id or \
            int(updated.get("system_channel_flags", 0)) & 1:
        raise DiscordError("Discord did not confirm system #welcome notifications.")
    print("Native Discord join messages enabled in #welcome.")
    return updated


def check_prompts(actual, expected):
    present = {p.get("title"): p for p in actual}
    for wanted in expected:
        if wanted["title"] not in {q[0] for q in QUESTIONS}:
            continue
        question = present.get(wanted["title"])
        if question is None:
            raise DiscordError("Onboarding question missing: " + wanted["title"])
        for key in ("single_select", "required", "in_onboarding"):
            if question.get(key) != wanted[key]:
                raise DiscordError("Onboarding question configuration mismatch: " + wanted["title"])
        options = {o.get("title"): o for o in question.get("options", [])}
        for option in wanted["options"]:
            current = options.get(option["title"])
            if current is None or set(current.get("role_ids", [])) != set(option["role_ids"]):
                raise DiscordError("Onboarding role mapping mismatch: " +
                                   wanted["title"] + " / " + option["title"])


def main():
    mode = os.getenv("WP_MODE", "preview")
    confirm = os.getenv("WP_CONFIRMATION", "")
    guild_id = os.getenv("DISCORD_GUILD_ID", "").strip()
    token = os.getenv("DISCORD_BOT_TOKEN", "").strip()
    if mode not in ("preview", "apply", "audit"):
        sys.exit("Invalid mode.")
    if mode == "apply" and confirm != "APLICAR":
        sys.exit("To apply, enter APLICAR. No changes made.")
    if not token or not authorized_guild(guild_id):
        sys.exit("Missing token or unauthorized guild ID. No changes made.")
    api = API(token)
    guild = api.call("GET", f"/guilds/{guild_id}")
    role_list = api.call("GET", f"/guilds/{guild_id}/roles")
    channels = api.call("GET", f"/guilds/{guild_id}/channels")
    everyone = next((r for r in role_list if r.get("id") == guild_id), None)
    if not everyone:
        raise DiscordError("Cannot inspect @everyone permissions.")
    everybody_permissions = int(everyone.get("permissions", 0))
    current_roles = {r["name"]: r for r in role_list}
    print("Workflow mode:", mode.upper())
    print("Community enabled:", "COMMUNITY" in guild.get("features", []))

    if mode == "preview":
        print("PREVIEW ONLY — nothing is changed in Discord.")
        for name in ("Member", *SELECTABLE_ROLES):
            status = "EXISTS" if name in current_roles else (
                "RENAME Membro" if name == "Member" and "Membro" in current_roles else "CREATE"
            )
            print(f"{status}: {name}")
        print("PLAN: create #welcome, #rules, #introductions, #gaming-chat, #off-topic if missing.")
        print("PLAN: enable Community, activate three English join questions,")
        print("      set seven safe default channels and Discord's native join messages.")
        print("NOT INCLUDED: Loritta bot invitation, AutoRole or custom @mention welcome.")
        print("For changes: choose mode=apply AND enter confirmation=APLICAR.")
        return

    if mode == "apply":
        roles = ensure_roles(api, guild_id, role_list)
        channels, made = ensure_entry_channels(api, guild_id, channels)
        # The private security-log channel is suitable for Community updates.
        updates = next((c for c in channels if c.get("type") == 0
                        and c.get("name") == "logs-de-seguranca"), None)
        if not updates:
            raise DiscordError("Missing private logs-de-seguranca channel for Community updates; "
                               "run the original setup workflow apply first.")
        guild = enable_community_if_needed(api, guild_id, guild, made["rules"]["id"],
                                            updates["id"])
        guild = set_native_welcome(api, guild_id, guild, made["welcome"]["id"])
        onboarding = api.call("GET", f"/guilds/{guild_id}/onboarding")
        defaults = select_default_channels(channels, guild_id, everybody_permissions)
        desired = build_prompts(onboarding.get("prompts", []), roles, made["welcome"]["id"])
        payload = {
            "prompts": desired,
            "default_channel_ids": defaults,
            "enabled": True,
            "mode": 1,
        }
        api.call("PUT", f"/guilds/{guild_id}/onboarding", payload)
        actual = api.call("GET", f"/guilds/{guild_id}/onboarding")
        if not actual.get("enabled"):
            raise DiscordError("Onboarding still disabled after apply.")
        check_prompts(actual.get("prompts", []), desired)
        print("SUCCESS: English join questions enabled and role mappings verified.")
        print("SUCCESS: Discord native welcome messages set to #welcome.")
        print("Loritta AutoRole and custom @mention greetings MUST still be configured")
        print("from the Loritta dashboard. GitHub Actions does not run a 24/7 join bot.")
        return

    # Audit is read-only and fails rather than presenting staged configuration as active.
    if "COMMUNITY" not in guild.get("features", []):
        raise DiscordError("AUDIT FAIL: Community is disabled. Run APPLY.")
    roles = {name: current_roles.get(name) for name in ("Member", *SELECTABLE_ROLES)}
    missing = [name for name, role in roles.items() if not role]
    if missing:
        raise DiscordError("AUDIT FAIL missing roles: " + ", ".join(missing))
    welcome = next((c for c in channels if c.get("type") == 0
                    and c.get("name") == "welcome"), None)
    if not welcome or guild.get("system_channel_id") != welcome["id"] or \
            int(guild.get("system_channel_flags") or 0) & 1:
        raise DiscordError("AUDIT FAIL: native #welcome join notifications not enabled.")
    actual = api.call("GET", f"/guilds/{guild_id}/onboarding")
    if not actual.get("enabled"):
        raise DiscordError("AUDIT FAIL: Onboarding is disabled.")
    for c in channels:
        c["_guild_id"] = guild_id
    if not onboarding_ready(actual.get("default_channel_ids", []),
                            channels, everybody_permissions):
        raise DiscordError("AUDIT FAIL: inadequate onboarding default channels.")
    expected = build_prompts(actual.get("prompts", []), roles, welcome["id"])
    check_prompts(actual.get("prompts", []), expected)
    print("AUDIT OK: Community, English join prompts, default channels, and native welcome.")
    print("AUDIT DOES NOT CHECK Loritta AutoRole or Loritta custom greetings.")


if __name__ == "__main__":
    try:
        main()
    except DiscordError as error:
        sys.exit("FAILED: " + str(error))
