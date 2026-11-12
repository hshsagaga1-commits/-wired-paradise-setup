#!/usr/bin/env python3
"""Wired Paradise English join roles and Discord Community Onboarding.

A one-shot GitHub Actions setup, not a background member-join listener.
Use Loritta AutoRole for assigning Member to every new join.
"""
import hashlib
import hmac
import os
import sys

from setup import API, DiscordError, AUTHORIZED_GUILD_SHA256

# Neutral grayscale role palette, matching Wired Paradise's theme.
SELECTABLE_ROLES = {
    "Male": 0xA9A9A9,
    "Female": 0xD3D3D3,
    "PC": 0xB0B0B0,
    "Mobile": 0x999999,
    "Console": 0x777777,
    "Notifications": 0xE0E0E0,
}

# Question title, single-select, required, and answer (text, role or None, emoji).
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


def authorized_guild(guild_id):
    return bool(guild_id and guild_id.isascii() and guild_id.isdecimal()
                and hmac.compare_digest(
                    hashlib.sha256(guild_id.encode("ascii")).hexdigest(),
                    AUTHORIZED_GUILD_SHA256
                ))


def make_option(title, role_id, emoji, old=None, neutral_channel=None):
    """Preserve an existing answer ID, if there is one.

    Answers without a role get a safe public channel so the option is valid
    without revealing a 'prefer not to say' role on the member's profile.
    """
    option = {
        "title": title,
        "description": None,
        "role_ids": [str(role_id)] if role_id else [],
        "channel_ids": [str(neutral_channel)] if not role_id and neutral_channel else [],
        "emoji_id": None,
        "emoji_name": emoji,
        "emoji_animated": False,
    }
    if old and old.get("id"):
        option["id"] = old["id"]
    return option


def build_prompts(existing, roles, neutral_channel):
    """Keep all other onboarding questions untouched and avoid duplicates."""
    prompts = [dict(p) for p in existing]
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
    """Create selectable roles, preserving assignments and permissions of existing roles."""
    roles = list(initial)
    names = ["Member"] + list(SELECTABLE_ROLES)
    for name in names:
        existing = next((r for r in roles if r.get("name") == name), None)
        if name == "Member" and not existing:
            existing = next((r for r in roles if r.get("name") == "Membro" and not r.get("managed")), None)
            if existing:
                api.call("PATCH", f"/guilds/{guild_id}/roles/{existing['id']}", {"name": "Member"})
                existing["name"] = "Member"
                print("Renamed Membro to Member (existing members keep their role).")
        if not existing:
            existing = api.call("POST", f"/guilds/{guild_id}/roles", {
                "name": name,
                "color": SELECTABLE_ROLES.get(name, 0xFFFFFF),
                "permissions": "0",
                "hoist": False,
                "mentionable": False,
            })
            roles.append(existing)
            print("Created role:", name)
        else:
            print("Existing role:", name)
        if existing.get("managed") or int(existing.get("permissions", "0")) & (1 << 3):
            raise DiscordError(f"Role {name} is managed or has Administrator; review manually.")
    return {name: next(r for r in roles if r.get("name") == name) for name in names}


def onboarding_ready(default_ids, channels, everyone_permissions):
    """Conservative check: only clearly writable text/voice? text channels count."""
    if len(set(default_ids)) < 7:
        return False
    by_id = {c["id"]: c for c in channels}
    sendable = 0
    for channel_id in set(default_ids):
        c = by_id.get(channel_id)
        if not c or c.get("type") not in (0, 5, 15):
            continue
        p = everyone_permissions
        for overwrite in c.get("permission_overwrites", []):
            if str(overwrite.get("id")) == str(c.get("guild_id", "")):
                # Some responses do not include guild_id; handled by caller's
                # guild_id parameter below when available.
                pass
        # Count only channels with explicit @everyone send permission, or where
        # the base @everyone role permits sending and no everyone deny exists.
        everyone = next((r for r in c.get("permission_overwrites", [])
                         if str(r.get("id")) == str(c.get("_guild_id"))), None)
        if everyone:
            deny, allow = int(everyone.get("deny", 0)), int(everyone.get("allow", 0))
            p = (p & ~deny) | allow
        if p & (1 << 11):
            sendable += 1
    return sendable >= 5


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
    for ch in channels:
        ch["_guild_id"] = guild_id
    role_map = {r["name"]: r for r in role_list}
    if mode == "preview":
        print("PREVIEW ONLY: no Discord changes.")
        for name in ["Member"] + list(SELECTABLE_ROLES):
            status = "EXISTS" if name in role_map else (
                "RENAME Membro" if name == "Member" and "Membro" in role_map else "CREATE")
            print(status + ":", name)
        for title, *_ in QUESTIONS:
            print("Onboarding question:", title)
        print("Loritta must be added and its AutoRole set to Member separately.")
        print("Community enabled:", "COMMUNITY" in guild.get("features", []))
        return

    if mode == "apply":
        selected = ensure_roles(api, guild_id, role_list)
    else:
        selected = {name: role_map.get(name) for name in ["Member"] + list(SELECTABLE_ROLES)}
        for name, value in selected.items():
            if not value:
                raise DiscordError("Missing role: " + name)

    if "COMMUNITY" not in guild.get("features", []):
        print("Onboarding requires Discord Community. Roles are ready; enable Community in server settings.")
        if mode == "audit":
            raise DiscordError("Community not enabled.")
        return

    current = api.call("GET", f"/guilds/{guild_id}/onboarding")
    neutral = next((c.get("id") for c in channels if c.get("name") == "chat-geral"
                    and c.get("type") == 0), None)
    if not neutral:
        neutral = next((c.get("id") for c in channels
                        if c.get("type") == 0 and c.get("name") != "spam"), None)
    if not neutral:
        raise DiscordError("Need a normal public text channel for skip/no-notifications answers.")

    desired = build_prompts(current.get("prompts", []), selected, neutral)
    if mode == "audit":
        present = {p.get("title"): p for p in current.get("prompts", [])}
        for title, *_ in QUESTIONS:
            if title not in present:
                raise DiscordError("Missing onboarding question: " + title)
        if not current.get("enabled"):
            raise DiscordError("Questions staged but onboarding not enabled.")
        print("AUDIT OK: all join questions exist and onboarding is enabled.")
        print("Check Loritta AutoRole separately in its dashboard.")
        return

    defaults = current.get("default_channel_ids", [])
    everyone = role_map.get("@everyone", {})
    # Discord @everyone role is keyed by the guild ID, not necessarily by name.
    everyone = next((r for r in role_list if r.get("id") == guild_id), everyone)
    ready = onboarding_ready(defaults, channels, int(everyone.get("permissions", "0")))
    body = {"prompts": desired}
    if ready or current.get("enabled"):
        body["enabled"] = True
    # Preserve all unrelated onboarding settings and default channels.
    api.call("PUT", f"/guilds/{guild_id}/onboarding", body)
    print("Onboarding questions updated in English; existing unrelated prompts retained.")
    if not (ready or current.get("enabled")):
        print("NOT ENABLED YET: Discord requires >=7 default channels and >=5 writable by @everyone.")
        print("Configure suitable default channels in Discord > Server Settings > Onboarding.")
    else:
        print("Onboarding enabled.")
    print("IMPORTANT: add Loritta and configure AutoRole -> Member; GitHub Actions alone")
    print("cannot assign roles to users joining later (there is no permanent process).")


if __name__ == "__main__":
    try:
        main()
    except DiscordError as error:
        sys.exit("Setup blocked: " + str(error))
