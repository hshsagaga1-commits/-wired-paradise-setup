#!/usr/bin/env python3
"""Montador pontual do Wired Paradise. Usa a API oficial do Discord."""
import json
import os
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

BASE = "https://discord.com/api/v10"
INVITE = 1 << 0
VIEW = 1 << 10
SEND = 1 << 11
MENTION_ALL = 1 << 17
CHANNELS = {
    "COMUNIDADE": [
        ("chat-geral", 0, "Conversa geral da comunidade.", 5, False),
        ("midias", 0, "Imagens, vídeos e edits.", 10, False),
        ("spam", 0, "Conversa livre, sem golpes nem ataques.", 2, False),
    ],
    "MEUS PROJETOS": [
        ("meus-scripts", 0, "Scripts publicados pela equipe.", 0, True),
        ("metodos-de-qualidade", 0, "Métodos e tutoriais da equipe.", 0, True),
    ],
    "VOZ": [("Call Geral", 2, None, 0, False)],
    "SEGURANÇA": [("logs-de-seguranca", 0, "Alertas do AutoMod.", 0, False)],
}


class DiscordError(Exception):
    pass


class API:
    def __init__(self, token):
        self.token = token

    def call(self, method, path, body=None):
        payload = json.dumps(body, ensure_ascii=False).encode() if body is not None else None
        url = BASE + path
        headers = {
            "Authorization": "Bot " + self.token,
            "User-Agent": "WiredParadiseSetup/1.0",
            "Content-Type": "application/json",
            "X-Audit-Log-Reason": quote("Configuração autorizada Wired Paradise"),
        }
        for attempt in range(5):
            req = Request(url, data=payload, method=method, headers=headers)
            try:
                with urlopen(req, timeout=25) as res:
                    raw = res.read().decode("utf-8")
                    return json.loads(raw) if raw else {}
            except HTTPError as err:
                body_text = err.read().decode("utf-8", errors="replace")
                try:
                    data = json.loads(body_text)
                except ValueError:
                    data = {}
                if err.code == 429 and attempt < 4:
                    time.sleep(min(15, max(1, float(data.get("retry_after", 1)))))
                    continue
                if err.code >= 500 and attempt < 4:
                    time.sleep(attempt + 1)
                    continue
                raise DiscordError("Discord HTTP %d: %s" % (err.code, str(data.get("message", "Falha de API"))[:160])) from None
            except URLError:
                if attempt < 4:
                    time.sleep(attempt + 1)
                    continue
                raise DiscordError("Sem conexão com Discord") from None
        raise DiscordError("Discord indisponível")


def find_channel(channels, name, kind, parent=None):
    for c in channels:
        if c.get("name") == name and c.get("type") == kind:
            if parent is None or c.get("parent_id") == parent:
                return c
    return None


def overwrites(existing, guild_id, category, readonly=False):
    """Preserva outros cargos e permissões existentes; apenas adiciona bloqueios."""
    all_overwrites = [dict(p) for p in existing or []]
    everyone = next((p for p in all_overwrites if p["id"] == guild_id and p["type"] == 0), None)
    if everyone is None:
        everyone = {"id": guild_id, "type": 0, "allow": "0", "deny": "0"}
        all_overwrites.append(everyone)
    deny = INVITE | MENTION_ALL
    if category == "SEGURANÇA":
        deny |= VIEW
    if readonly:
        deny |= SEND
    everyone["deny"] = str(int(everyone.get("deny", 0)) | deny)
    everyone["allow"] = str(int(everyone.get("allow", 0)) & ~deny)
    return all_overwrites


def automod(name, trigger_type, log_id):
    spec = {
        "name": name, "event_type": 1, "trigger_type": trigger_type, "enabled": True,
        "actions": [
            {"type": 1, "metadata": {"custom_message": "Mensagem bloqueada pela segurança do Wired Paradise."}},
            {"type": 2, "metadata": {"channel_id": log_id}},
        ],
    }
    if trigger_type == 5:
        spec["trigger_metadata"] = {"mention_total_limit": 5, "mention_raid_protection_enabled": True}
        spec["actions"].append({"type": 3, "metadata": {"duration_seconds": 120}})
    return spec


def main():
    mode = os.getenv("WP_MODE", "preview")
    confirm = os.getenv("WP_CONFIRMATION", "")
    token = os.getenv("DISCORD_BOT_TOKEN", "").strip()
    guild_id = os.getenv("DISCORD_GUILD_ID", "").strip()
    if mode not in ("preview", "apply"):
        sys.exit("Modo inválido")
    if mode == "apply" and confirm != "APLICAR":
        sys.exit("Falta confirmação APLICAR; nada foi alterado")
    if not token or not guild_id.isdigit():
        sys.exit("Cadastre DISCORD_BOT_TOKEN e DISCORD_GUILD_ID em GitHub Actions Secrets")
    api = API(token)
    # Use the ID copied directly from the user's Wired Paradise server.
    # Names can include emojis, styling, or later be renamed.
    if guild_id != "1568895510096519208":
        sys.exit("ID diferente do Wired Paradise autorizado; operação cancelada")
    guild = api.call("GET", "/guilds/" + guild_id)
    print("Servidor confirmado pelo ID:", guild.get("name", "(sem nome)"), "(" + guild_id + ")")
    channels = api.call("GET", "/guilds/" + guild_id + "/channels")
    if mode == "preview":
        print("PRÉVIA — NENHUMA ALTERAÇÃO NO DISCORD")
        for category, specs in CHANNELS.items():
            existing = find_channel(channels, category, 4)
            print(("EXISTE" if existing else "CRIAR") + " categoria " + category)
            for name, typ, _, _, readonly in specs:
                found = find_channel(channels, name, typ, existing["id"]) if existing else None
                print(" ", "EXISTE" if found else "CRIAR", name,
                      "(somente equipe publica)" if readonly else "")
        print("Também: restrições @everyone, verificação Alta, filtro de mídia, AutoMod anti-spam e menções.")
        print("Para executar: apply + APLICAR")
        return

    problems = []
    log_id = None
    for category, specs in CHANNELS.items():
        cat = find_channel(channels, category, 4)
        if cat is None:
            cat = api.call("POST", "/guilds/" + guild_id + "/channels", {
                "name": category, "type": 4, "permission_overwrites": overwrites([], guild_id, category)
            })
            channels.append(cat)
            print("Categoria criada:", category)
        else:
            new_permissions = overwrites(cat.get("permission_overwrites"), guild_id, category)
            if new_permissions != cat.get("permission_overwrites"):
                api.call("PATCH", "/channels/" + cat["id"], {"permission_overwrites": new_permissions})
                cat["permission_overwrites"] = new_permissions
            print("Categoria existente:", category)
        for name, typ, topic, slow, readonly in specs:
            ch = find_channel(channels, name, typ, cat["id"])
            if ch is None:
                data = {
                    "name": name, "type": typ, "parent_id": cat["id"],
                    "permission_overwrites": overwrites([], guild_id, category, readonly)
                }
                if typ == 0:
                    data.update({"topic": topic, "rate_limit_per_user": slow})
                ch = api.call("POST", "/guilds/" + guild_id + "/channels", data)
                channels.append(ch)
                print("Canal criado:", name)
            else:
                patch = {}
                ow = overwrites(ch.get("permission_overwrites"), guild_id, category, readonly)
                if ow != ch.get("permission_overwrites"):
                    patch["permission_overwrites"] = ow
                if typ == 0 and int(ch.get("rate_limit_per_user", 0)) < slow:
                    patch["rate_limit_per_user"] = slow
                if patch:
                    api.call("PATCH", "/channels/" + ch["id"], patch)
                    ch.update(patch)
                print("Canal existente:", name)
            if name == "logs-de-seguranca":
                log_id = ch["id"]

    try:
        roles = api.call("GET", "/guilds/" + guild_id + "/roles")
        everyone = next(r for r in roles if r["id"] == guild_id)
        previous = int(everyone["permissions"])
        reduced = previous & ~INVITE & ~MENTION_ALL
        if previous != reduced:
            api.call("PATCH", "/guilds/" + guild_id + "/roles/" + guild_id, {"permissions": str(reduced)})
        print("Permissões globais de membros conferidas.")
    except (DiscordError, StopIteration) as err:
        problems.append("Cargo @everyone: " + str(err))

    try:
        patch = {}
        if guild.get("verification_level", 0) < 3:
            patch["verification_level"] = 3
        if guild.get("explicit_content_filter", 0) < 2:
            patch["explicit_content_filter"] = 2
        if patch:
            api.call("PATCH", "/guilds/" + guild_id, patch)
        print("Verificação e filtro de mídia conferidos.")
    except DiscordError as err:
        problems.append("Verificação / filtro: " + str(err))

    if log_id and "COMMUNITY" in guild.get("features", []):
        try:
            api.call("PATCH", "/guilds/" + guild_id, {"safety_alerts_channel_id": log_id})
        except DiscordError as err:
            problems.append("Canal de alertas de segurança: " + str(err))

    try:
        rules = api.call("GET", "/guilds/" + guild_id + "/auto-moderation/rules")
        for name, trigger in (("WP | Anti-spam", 3), ("WP | Anti-raid de menções", 5)):
            existing = next((r for r in rules if r.get("name") == name), None)
            if existing is None and any(r.get("trigger_type") == trigger for r in rules):
                print("Regra AutoMod do mesmo tipo já existe; mantida:", name)
                continue
            spec = automod(name, trigger, log_id)
            try:
                if existing:
                    spec.pop("trigger_type")
                    api.call("PATCH", "/guilds/" + guild_id + "/auto-moderation/rules/" + existing["id"], spec)
                else:
                    api.call("POST", "/guilds/" + guild_id + "/auto-moderation/rules", spec)
                print("AutoMod conferido:", name)
            except DiscordError as err:
                problems.append("AutoMod " + name + ": " + str(err))
    except DiscordError as err:
        problems.append("Leitura AutoMod: " + str(err))

    print("\nCONCLUÍDO — confira canais e proteções nativas no Discord.")
    if problems:
        for p in problems:
            print("ATENÇÃO:", p)
        sys.exit(2)
    print("Sem falhas de API reportadas. Proteção anti-raid não é garantia absoluta.")


if __name__ == "__main__":
    try:
        main()
    except DiscordError as err:
        sys.exit("Falha: " + str(err))
