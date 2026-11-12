#!/usr/bin/env python3
"""Wired Paradise — owner-only control of Discord integrations and AutoMod.

A manual, double-confirmed server permission hardening operation.
Preview and audit modes use GET only. Bot-managed roles are never modified.
The real Discord server owner has inherent privileges regardless of role bits.

It does not log in to, modify, or claim to audit Loritta's private dashboard.
"""
import hashlib
import hmac
import os
import sys

from setup import API, DiscordError, AUTHORIZED_GUILD_SHA256

ADMINISTRATOR = 1 << 3
MANAGE_CHANNELS = 1 << 4
MANAGE_GUILD = 1 << 5
MANAGE_ROLES = 1 << 28
MANAGE_WEBHOOKS = 1 << 29

# Guild roles: remove paths to change AutoMod, app setup, role hierarchies,
# webhook automations, and security channel configuration.
PROTECTED_GUILD = (ADMINISTRATOR | MANAGE_GUILD | MANAGE_ROLES |
                   MANAGE_CHANNELS | MANAGE_WEBHOOKS)

# Channel overwrites can grant the last three bits; guild-only permissions
# such as Administrator and Manage Guild are not channel-overwrite permissions.
PROTECTED_CHANNEL = MANAGE_CHANNELS | MANAGE_ROLES | MANAGE_WEBHOOKS

GUILD_ONLY_NAMES = (
    (ADMINISTRATOR, "Administrator"),
    (MANAGE_GUILD, "Manage Server"),
    (MANAGE_ROLES, "Manage Roles"),
    (MANAGE_CHANNELS, "Manage Channels"),
    (MANAGE_WEBHOOKS, "Manage Webhooks"),
)

CONFIRMATION = "SOMENTE DONO"


def authorized(guild_id):
    return bool(guild_id and guild_id.isascii() and guild_id.isdecimal()
                and hmac.compare_digest(
                    hashlib.sha256(guild_id.encode("ascii")).hexdigest(),
                    AUTHORIZED_GUILD_SHA256))


def forbidden_names(bits):
    return [name for bit, name in GUILD_ONLY_NAMES if bits & bit]


def updated_role_permissions(role):
    old = int(role.get("permissions", 0))
    return old & ~PROTECTED_GUILD


def is_protected_bot_role(role):
    """Managed roles belong to bots/integrations. Never rewrite them."""
    return bool(role.get("managed"))


def role_fixes(roles, guild_id):
    """Audit every editable (human/grantable) role including @everyone."""
    fixes = []
    for role in roles:
        if is_protected_bot_role(role):
            continue
        old = int(role.get("permissions", 0))
        new = updated_role_permissions(role)
        if old != new:
            fixes.append({
                "id": role["id"],
                "name": role.get("name", "(unnamed)"),
                "old": old, "new": new,
                "removed": forbidden_names(old & ~new),
                "everyone": str(role["id"]) == str(guild_id),
            })
    return fixes


def bot_user_ids(roles):
    """Bot member IDs for normal managed bot roles; protect direct bot overwrites."""
    result = set()
    for role in roles:
        tags = role.get("tags") or {}
        bot_id = tags.get("bot_id")
        if bot_id:
            result.add(str(bot_id))
    return result


def channel_fixes(channels, roles, owner_id, guild_id):
    """Remove security-management ALLOW overrides for non-owner humans.

    Preserve managed bot roles and bot account member overwrites.
    Channel permissions unrelated to security stay byte-for-byte intact.
    """
    managed_ids = {str(r["id"]) for r in roles if is_protected_bot_role(r)}
    bots = bot_user_ids(roles)
    fixes = []
    for channel in channels:
        overrides = channel.get("permission_overwrites") or []
        revised = []
        changed = False
        removed_entries = 0
        for item in overrides:
            entry = dict(item)
            target = str(entry.get("id", ""))
            target_type = int(entry.get("type", -1))
            # Discord's owner bypasses role permissions anyway.
            skip = (
                target_type == 1 and target == str(owner_id) or
                target_type == 0 and target in managed_ids or
                target_type == 1 and target in bots
            )
            if not skip and target_type in (0, 1):
                old_allow = int(entry.get("allow", 0))
                new_allow = old_allow & ~PROTECTED_CHANNEL
                if old_allow != new_allow:
                    entry["allow"] = str(new_allow)
                    changed = True
                    removed_entries += 1
            revised.append(entry)
        if changed:
            fixes.append({
                "id": channel["id"],
                "name": channel.get("name", "(unnamed)"),
                "overwrites": revised,
                "removed_entries": removed_entries,
            })
    return fixes


def display_plan(roles, channels, guild_id, owner_id):
    role_items = role_fixes(roles, guild_id)
    channel_items = channel_fixes(channels, roles, owner_id, guild_id)
    print("OWNER-ONLY SECURITY AUDIT")
    print("Role changes needed:", len(role_items))
    for role in role_items:
        print(" - ROLE:", role["name"], "| remove:", ", ".join(role["removed"]))
    print("Channels with dangerous permission overwrites:", len(channel_items))
    for item in channel_items:
        print(" - CHANNEL:", item["name"],
              "| affected overrides:", item["removed_entries"])
    print("Managed bot roles are always preserved (Loritta and other integrations).")
    print("Moderation capabilities like Manage Messages / Timeout are preserved.")
    print("Bot dashboard/editor settings cannot be queried with the Discord bot token.")
    print("Loritta slash command permissions must be reviewed in Discord Integrations.")
    return role_items, channel_items


def main():
    mode = os.getenv("WP_SECURITY_MODE", "preview").strip()
    confirm = os.getenv("WP_SECURITY_CONFIRM", "").strip()
    guild_id = os.getenv("DISCORD_GUILD_ID", "").strip()
    token = os.getenv("DISCORD_BOT_TOKEN", "").strip()
    if mode not in ("preview", "apply", "audit"):
        sys.exit("Invalid mode; choose preview, apply or audit.")
    if mode == "apply" and confirm != CONFIRMATION:
        sys.exit("NOT APPLIED: choose apply and enter SOMENTE DONO.")
    if not token or not authorized(guild_id):
        sys.exit("Missing secrets or unauthorized guild; no changes.")

    api = API(token)
    guild = api.call("GET", f"/guilds/{guild_id}")
    if str(guild.get("id")) != guild_id:
        raise DiscordError("Guild identity mismatch; no changes.")
    owner_id = guild.get("owner_id")
    if not owner_id:
        raise DiscordError("Cannot verify actual server owner; no changes.")

    roles = api.call("GET", f"/guilds/{guild_id}/roles")
    channels = api.call("GET", f"/guilds/{guild_id}/channels")
    role_items, channel_items = display_plan(roles, channels, guild_id, owner_id)

    if mode == "preview":
        print("PREVIEW ONLY: no server changes were made.")
        print("To lock down, choose mode=apply AND confirmation=SOMENTE DONO.")
        return

    if mode == "audit":
        if role_items or channel_items:
            raise DiscordError(
                f"AUDIT NOT YET SECURE: {len(role_items)} roles and "
                f"{len(channel_items)} channels need restrictions."
            )
        print("AUDIT PASSED: no normal role or non-bot channel overwrite "
              "can grant Discord integration / AutoMod administration.")
        print("NOTE: Loritta-specific custom access rules were not audited.")
        return

    if not role_items and not channel_items:
        print("ALREADY SECURE: no restricted permissions needed removal.")
        return

    for role in role_items:
        api.call("PATCH", f"/guilds/{guild_id}/roles/{role['id']}",
                 {"permissions": str(role["new"])})
        print("Restricted human role:", role["name"])
    for channel in channel_items:
        api.call("PATCH", f"/channels/{channel['id']}",
                 {"permission_overwrites": channel["overwrites"]})
        print("Restricted overrides in channel:", channel["name"])

    # Verify the state, not just HTTP success responses.
    new_roles = api.call("GET", f"/guilds/{guild_id}/roles")
    new_channels = api.call("GET", f"/guilds/{guild_id}/channels")
    remaining_roles = role_fixes(new_roles, guild_id)
    remaining_channels = channel_fixes(new_channels, new_roles, owner_id, guild_id)
    if remaining_roles or remaining_channels:
        raise DiscordError(
            f"Partial lockdown: {len(remaining_roles)} roles and "
            f"{len(remaining_channels)} channels still have elevated grants."
        )
    print("SUCCESS: Discord server-management permissions locked to owner.")
    print("Loritta bot itself was not modified. Review its slash commands and "
          "dashboard access rules separately.")


if __name__ == "__main__":
    try:
        main()
    except DiscordError as error:
        sys.exit("Owner-only security failed: " + str(error))
