#!/usr/bin/env python3
"""Configuração explícita, idempotente e auditável do WiredParadise via Discord API v10."""
import hashlib
import hmac
import json
import os
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

BASE = "https://discord.com/api/v10"
# Identificador de servidor por fingerprint (não é criptografia, nem credencial).
AUTHORIZED_GUILD_SHA256 = "cf1a67632a67f690daacb0e2b2c11c7156d8f59d6dc27bb85c5d1114e58ad02e"

INVITE = 1 << 0
ADMIN = 1 << 3
VIEW = 1 << 10
SEND = 1 << 11
MANAGE_MESSAGES = 1 << 13
EMBED = 1 << 14
ATTACH = 1 << 15
HISTORY = 1 << 16
MENTION_ALL = 1 << 17
MODERATE_MEMBERS = 1 << 40
CREATE_PUBLIC_THREADS = 1 << 35
CREATE_PRIVATE_THREADS = 1 << 36
SEND_IN_THREADS = 1 << 38

# (nome, tipo Discord, tópico, modo lento em segundos, política)
CHANNELS = {
    "COMUNIDADE": [
        ("anuncios", 0, "Avisos oficiais: somente o dono publica.", 0, "owner"),
        ("chat-geral", 0, "Converse por texto. Anexos e prévias de links desativados.", 5, "chat"),
        ("midias", 0, "Imagens, vídeos, arquivos e conversa liberados.", 2, "media"),
        ("spam", 0, "Conversa livre. Mensagem contendo apenas um ponto será bloqueada pelo AutoMod.", 2, "spam"),
        ("cargos", 0, "Informações dos cargos; somente o dono publica.", 0, "owner"),
    ],
    "MEUS PROJETOS": [
        ("meus-scripts", 0, "Scripts oficiais: somente o dono publica.", 0, "owner"),
        ("metodos-de-qualidade", 0, "Métodos oficiais: somente o dono publica.", 0, "owner"),
    ],
    "VOZ": [("Call Geral", 2, None, 0, "voice")],
    "SEGURANÇA": [
        ("logs-de-seguranca", 0, "Alertas automáticos do Discord; visível para dono e moderação.", 0, "logs")
    ],
}

# Cargos sem ADMINISTRADOR. A conta proprietária já tem privilégios inerentes.
ROLE_SPECS = (
    ("👑 Dono", 0xED4245, 0, True),
    ("Moderação", 0x3498DB, MANAGE_MESSAGES | MODERATE_MEMBERS, True),
    ("Membro", 0xFFFFFF, 0, False),
    ("Cargo Boost", 0xFF73FA, 0, True),
    ("Sigma 67", 0x9B59B6, 0, True),
)


class DiscordError(Exception):
    pass


class API:
    def __init__(self, token):
        self.token = token

    def call(self, method, path, body=None):
        payload = json.dumps(body, ensure_ascii=False).encode() if body is not None else None
        headers = {
            "Authorization": "Bot " + self.token,
            "User-Agent": "WiredParadiseSetup/2.0",
            "Content-Type": "application/json",
            "X-Audit-Log-Reason": quote("Configuração autorizada WiredParadise"),
        }
        for attempt in range(5):
            request = Request(BASE + path, data=payload, method=method, headers=headers)
            try:
                with urlopen(request, timeout=25) as response:
                    raw = response.read().decode("utf-8")
                    return json.loads(raw) if raw else {}
            except HTTPError as error:
                raw_error = error.read().decode("utf-8", errors="replace")
                try:
                    info = json.loads(raw_error)
                except ValueError:
                    info = {}
                if error.code == 429 and attempt < 4:
                    time.sleep(min(15, max(1, float(info.get("retry_after", 1)))))
                    continue
                if error.code >= 500 and attempt < 4:
                    time.sleep(attempt + 1)
                    continue
                raise DiscordError(
                    "Discord HTTP %s: %s" % (error.code, str(info.get("message", "Erro de API"))[:160])
                ) from None
            except URLError:
                if attempt < 4:
                    time.sleep(attempt + 1)
                    continue
                raise DiscordError("Sem conexão com a API do Discord") from None
        raise DiscordError("Discord indisponível")


def find_channel(channels, name, kind, parent=None):
    return next(
        (c for c in channels if c.get("name") == name and c.get("type") == kind
         and (parent is None or c.get("parent_id") == parent)),
        None,
    )


def set_overwrite(overwrites_list, target_id, target_type, allow=0, deny=0, enforce_exclusive=0):
    item = next(
        (p for p in overwrites_list if str(p.get("id")) == str(target_id)
         and p.get("type") == target_type),
        None,
    )
    if item is None:
        item = {"id": str(target_id), "type": target_type, "allow": "0", "deny": "0"}
        overwrites_list.append(item)
    old_allow = int(item.get("allow", 0))
    old_deny = int(item.get("deny", 0))
    item["allow"] = str((old_allow & ~deny) | allow)
    item["deny"] = str((old_deny & ~allow) | deny)
    if enforce_exclusive:
        item["allow"] = str(int(item["allow"]) & ~enforce_exclusive)
    return item


def overwrites(existing, guild_id, policy, owner_id=None, moderator_id=None):
    """Garante política do canal sem apagar outras permissões não relacionadas."""
    result = [dict(p) for p in (existing or [])]
    deny = INVITE | MENTION_ALL
    allow = 0
    if policy == "owner":
        deny |= SEND | SEND_IN_THREADS | CREATE_PUBLIC_THREADS | CREATE_PRIVATE_THREADS
    elif policy in ("chat", "media", "spam"):
        allow |= SEND
    if policy == "chat":
        deny |= ATTACH | EMBED
    elif policy == "media":
        allow |= ATTACH | EMBED
    elif policy == "logs":
        deny |= VIEW
    set_overwrite(result, guild_id, 0, allow=allow, deny=deny)

    # Não deixar outros cargos concederem escrita em canais exclusivos,
    # nem anexos em chat ou VISUALIZAR em logs privados.
    exclusive = (SEND | SEND_IN_THREADS | CREATE_PUBLIC_THREADS | CREATE_PRIVATE_THREADS) if policy == "owner" else (ATTACH | EMBED if policy == "chat" else (VIEW if policy == "logs" else 0))
    if exclusive:
        for overwrite in result:
            oid = str(overwrite.get("id"))
            if oid == str(guild_id) or (owner_id and oid == str(owner_id)):
                continue
            if policy == "logs" and moderator_id and oid == str(moderator_id):
                continue
            overwrite["allow"] = str(int(overwrite.get("allow", 0)) & ~exclusive)

    if owner_id and policy in ("owner", "logs"):
        owner_access = (SEND | SEND_IN_THREADS | VIEW | HISTORY | CREATE_PUBLIC_THREADS | CREATE_PRIVATE_THREADS) if policy == "owner" else VIEW | HISTORY
        set_overwrite(result, owner_id, 1, allow=owner_access)
    if moderator_id and policy == "logs":
        set_overwrite(result, moderator_id, 0, allow=VIEW | HISTORY)
    return result


def role_spec(name):
    return next((r for r in ROLE_SPECS if r[0] == name), None)


def ensure_roles(api, guild_id, guild, problems):
    roles = api.call("GET", "/guilds/" + guild_id + "/roles")
    found = {}
    native_booster = next((r for r in roles if "premium_subscriber" in r.get("tags", {})), None)
    for name, color, perms, hoist in ROLE_SPECS:
        if name == "Cargo Boost" and native_booster:
            found[name] = native_booster
            print("Cargo de Booster nativo identificado: atribuição automática do Discord.")
            continue
        role = next((r for r in roles if r.get("name") == name), None)
        if role is None:
            spec = {
                "name": name,
                "color": color,
                "permissions": str(perms),
                "hoist": hoist,
                "mentionable": False,
            }
            if name == "👑 Dono" and "ROLE_ICONS" in guild.get("features", []):
                spec["unicode_emoji"] = "👑"
            try:
                role = api.call("POST", "/guilds/" + guild_id + "/roles", spec)
                roles.append(role)
                print("Cargo criado:", name)
            except DiscordError as error:
                problems.append("Criar cargo " + name + ": " + str(error))
                continue
        elif role.get("managed"):
            problems.append("Cargo não editável com nome reservado: " + name)
            continue
        else:
            patch = {}
            if int(role.get("color", 0)) != color:
                patch["color"] = color
            if bool(role.get("hoist", False)) != hoist:
                patch["hoist"] = hoist
            if bool(role.get("mentionable", False)):
                patch["mentionable"] = False
            # Não aumentamos permissões de um cargo antigo automaticamente.
            if patch:
                try:
                    api.call("PATCH", "/guilds/" + guild_id + "/roles/" + role["id"], patch)
                    role.update(patch)
                except DiscordError as error:
                    problems.append("Atualizar cargo " + name + ": " + str(error))
            print("Cargo existente:", name)
        if int(role.get("permissions", 0)) & ADMIN:
            problems.append("ATENÇÃO: cargo existente com ADMINISTRADOR: " + name)
        found[name] = role

    owner_id = guild.get("owner_id")
    if not owner_id:
        problems.append("Servidor não informou ID do proprietário; cargos exclusivos não atribuídos.")
        return found
    for name in ("👑 Dono", "Sigma 67"):
        if name not in found:
            continue
        try:
            api.call("PUT", "/guilds/" + guild_id + "/members/" + owner_id + "/roles/" + found[name]["id"])
            print("Cargo exclusivo atribuído ao proprietário:", name)
        except DiscordError as error:
            problems.append("Atribuir " + name + " ao proprietário: " + str(error))
    if native_booster is None:
        print("AVISO: Cargo Boost personalizado criado; atribuição automática a boosters exige bot online ou automação separada.")
    return found


def automod(name, trigger_type, log_id):
    spec = {
        "name": name,
        "event_type": 1,
        "trigger_type": trigger_type,
        "enabled": True,
        "actions": [{"type": 1, "metadata": {
            "custom_message": "Mensagem bloqueada pela segurança do WiredParadise."
        }}],
    }
    if log_id:
        spec["actions"].append({"type": 2, "metadata": {"channel_id": log_id}})
    if trigger_type == 5:
        spec["trigger_metadata"] = {
            "mention_total_limit": 5, "mention_raid_protection_enabled": True
        }
        spec["actions"].append({"type": 3, "metadata": {"duration_seconds": 120}})
    return spec


def dot_rule(log_id, channels, spam_id):
    """AutoMod nativo impede mensagem exatamente '.', NÃO bane usuário."""
    exempt = [
        c["id"] for c in channels if c.get("type") in (0, 5, 11, 12, 15, 16)
        and c.get("id") != spam_id
    ]
    if len(exempt) > 50:
        raise ValueError("Há canais demais para limitar o filtro ao spam com segurança")
    rule = automod("WP | Ponto no spam", 1, log_id)
    rule["trigger_metadata"] = {"regex_patterns": [r"^\.$"]}
    rule["exempt_channels"] = exempt
    rule["actions"].append({"type": 3, "metadata": {"duration_seconds": 60}})
    return rule


def apply_automod(api, guild_id, channels, problems):
    log = next((c for c in channels if c.get("name") == "logs-de-seguranca" and c.get("type") == 0), None)
    spam = next((c for c in channels if c.get("name") == "spam" and c.get("type") == 0
                 and any(p.get("name") == "COMUNIDADE" and c.get("parent_id") == p["id"] for p in channels)), None)
    try:
        rules = api.call("GET", "/guilds/" + guild_id + "/auto-moderation/rules")
    except DiscordError as error:
        problems.append("Ler regras AutoMod: " + str(error))
        return
    specs = [
        automod("WP | Anti-spam", 3, log["id"] if log else None),
        automod("WP | Anti-raid de menções", 5, log["id"] if log else None),
    ]
    if spam:
        try:
            specs.append(dot_rule(log["id"] if log else None, channels, spam["id"]))
        except ValueError as error:
            problems.append("Filtro de ponto: " + str(error))
    else:
        problems.append("Filtro de ponto: canal spam não encontrado")
    for spec in specs:
        existing = next((r for r in rules if r.get("name") == spec["name"]), None)
        trigger = spec["trigger_type"]
        if existing is None and trigger in (3, 5) and any(r.get("trigger_type") == trigger for r in rules):
            print("AutoMod nativo do mesmo tipo já existe; mantido:", spec["name"])
            continue
        try:
            if existing is None:
                api.call("POST", "/guilds/" + guild_id + "/auto-moderation/rules", spec)
            else:
                update = dict(spec)
                update.pop("trigger_type", None)
                api.call("PATCH", "/guilds/" + guild_id + "/auto-moderation/rules/" + existing["id"], update)
            print("AutoMod confirmado:", spec["name"])
        except DiscordError as error:
            problems.append("AutoMod " + spec["name"] + ": " + str(error))


def post_role_guide(api, channel_id, boost_native, problems):
    lines = [
        "**CARGOS DO WIREDPARADISE**",
        "👑 **Dono** — vermelho, exclusivo do proprietário.",
        "🔵 **Moderação** — azul, gerencia mensagens e pode aplicar timeout.",
        "⚪ **Membro** — branco, cargo comum.",
        "💗 **Cargo Boost** — para quem impulsiona o servidor.",
        "🟣 **Sigma 67** — exclusivo do dono.",
        "",
        "Os cargos Membro e Moderação são atribuídos pela equipe, não por esta mensagem.",
    ]
    if not boost_native:
        lines.append("O Cargo Boost personalizado ainda precisa de atribuição pela equipe.")
    try:
        api.call("POST", "/channels/" + channel_id + "/messages", {"content": "\n".join(lines),
                                                                 "allowed_mentions": {"parse": []}})
        print("Guia publicado uma única vez no canal cargos.")
    except DiscordError as error:
        problems.append("Publicar guia de cargos: " + str(error))


def validate_server(api, guild, guild_id):
    """GET somente: checagem da configuração sem modificar o servidor."""
    problems = []
    channels = api.call("GET", "/guilds/" + guild_id + "/channels")
    roles = api.call("GET", "/guilds/" + guild_id + "/roles")
    rules = api.call("GET", "/guilds/" + guild_id + "/auto-moderation/rules")
    owner_id = guild.get("owner_id")
    mods = next((r for r in roles if r.get("name") == "Moderação"), None)
    role_names = {r.get("name") for r in roles}
    if "premium_subscriber" in {tag for r in roles for tag in r.get("tags", {})}:
        role_names.add("Cargo Boost")
    for name, color, _, _ in ROLE_SPECS:
        role = next((r for r in roles if r.get("name") == name), None)
        if name == "Cargo Boost" and not role:
            role = next((r for r in roles if "premium_subscriber" in r.get("tags", {})), None)
        if not role:
            problems.append("Cargo ausente: " + name)
            continue
        if not role.get("managed") and int(role.get("color", 0)) != color:
            problems.append("Cor do cargo não confere: " + name)
        print("OK cargo:", name)
    if owner_id:
        try:
            owner = api.call("GET", "/guilds/" + guild_id + "/members/" + owner_id)
            for name in ("👑 Dono", "Sigma 67"):
                role = next((r for r in roles if r.get("name") == name), None)
                if role and role["id"] not in owner.get("roles", []):
                    problems.append("Proprietário não possui o cargo: " + name)
            print("OK cargos exclusivos atribuídos ao proprietário.")
        except DiscordError:
            print("AVISO: não foi possível conferir os cargos do proprietário por API.")
    print("AUDITORIA SOMENTE LEITURA — não altera membros nem canais.")
    for category, specs in CHANNELS.items():
        cat = find_channel(channels, category, 4)
        if not cat:
            problems.append("Categoria ausente: " + category)
            continue
        print("OK categoria:", category)
        for name, typ, _, slow, policy in specs:
            ch = find_channel(channels, name, typ, cat["id"])
            if not ch:
                problems.append("Canal ausente: " + name)
                continue
            expected = overwrites([], guild_id, policy, owner_id,
                                  mods["id"] if mods else None)
            current = ch.get("permission_overwrites") or []
            for exp in expected:
                actual = next((p for p in current if str(p["id"]) == str(exp["id"])
                               and p["type"] == exp["type"]), None)
                if not actual or int(actual.get("allow", 0)) & int(exp["allow"]) != int(exp["allow"]) or (
                    int(actual.get("deny", 0)) & int(exp["deny"]) != int(exp["deny"])
                ):
                    problems.append("Permissões não conferem: " + name)
                    break
            if typ == 0 and int(ch.get("rate_limit_per_user", 0)) < slow:
                problems.append("Slowmode insuficiente: " + name)
            print("OK canal encontrado:", name)
    base_role = next((r for r in roles if r.get("id") == guild_id), None)
    if not base_role or int(base_role.get("permissions", 0)) & (INVITE | MENTION_ALL):
        problems.append("@everyone ainda pode convidar ou mencionar globalmente")
    if guild.get("verification_level", 0) < 3:
        problems.append("Verificação abaixo de Alta")
    if guild.get("explicit_content_filter", 0) < 2:
        problems.append("Filtro de mídia insuficiente")
    dot = next((r for r in rules if r.get("name") == "WP | Ponto no spam"), None)
    spam = next((c for c in channels if c.get("name") == "spam" and c.get("type") == 0), None)
    if not dot or not dot.get("enabled") or dot.get("trigger_type") != 1 or (
        dot.get("trigger_metadata", {}).get("regex_patterns") != [r"^\\.$"]
    ):
        problems.append("Filtro do ponto no spam não está ativo")
    elif not spam:
        problems.append("Canal spam ausente para o filtro do ponto")
    elif spam["id"] in dot.get("exempt_channels", []):
        problems.append("Canal spam foi isentado acidentalmente do filtro do ponto")
    else:
        other_text = {c["id"] for c in channels if c.get("type") in (0, 5, 11, 12, 15, 16)
                      and c["id"] != spam["id"]}
        if not other_text.issubset(set(dot.get("exempt_channels", []))):
            problems.append("Filtro de ponto pode atingir canais fora do spam")
        print("OK AutoMod: ponto isolado bloqueado no spam; banimento NÃO configurado")
    for name in ("WP | Anti-spam", "WP | Anti-raid de menções"):
        if not any(r.get("name") == name and r.get("enabled") for r in rules):
            problems.append("AutoMod ausente/inativo: " + name)
        else:
            print("OK AutoMod:", name)
    if problems:
        for p in problems:
            print("ATENÇÃO:", p)
        raise DiscordError("Auditoria: " + str(len(problems)) + " pendência(s)")
    print("AUDITORIA APROVADA: estrutura e configurações encontradas.")
    print("IMPORTANTE: teste com conta comum; administradores não reproduzem permissões de membros.")


def main():
    mode = os.getenv("WP_MODE", "preview")
    confirm = os.getenv("WP_CONFIRMATION", "")
    token = os.getenv("DISCORD_BOT_TOKEN", "").strip()
    guild_id = os.getenv("DISCORD_GUILD_ID", "").strip()
    if mode not in ("preview", "apply", "audit"):
        sys.exit("Modo inválido")
    if mode == "apply" and confirm != "APLICAR":
        sys.exit("Falta confirmação APLICAR; nada foi alterado")
    if not token or not guild_id.isascii() or not guild_id.isdecimal():
        sys.exit("Secrets DISCORD_BOT_TOKEN e DISCORD_GUILD_ID ausentes ou inválidos")
    if not hmac.compare_digest(hashlib.sha256(guild_id.encode("ascii")).hexdigest(),
                               AUTHORIZED_GUILD_SHA256):
        sys.exit("ID diferente do servidor autorizado; operação cancelada")

    api = API(token)
    guild = api.call("GET", "/guilds/" + guild_id)
    print("Servidor autorizado confirmado (ID não exibido).")
    if mode == "audit":
        validate_server(api, guild, guild_id)
        return
    channels = api.call("GET", "/guilds/" + guild_id + "/channels")
    if mode == "preview":
        print("PRÉVIA: nenhuma alteração no Discord.")
        roles = api.call("GET", "/guilds/" + guild_id + "/roles")
        for name, _, _, _ in ROLE_SPECS:
            print("Cargo", "EXISTE" if any(r.get("name") == name for r in roles) else "CRIAR", name)
        for category, specs in CHANNELS.items():
            cat = find_channel(channels, category, 4)
            print("Categoria", "EXISTE" if cat else "CRIAR", category)
            for name, typ, _, _, policy in specs:
                ch = find_channel(channels, name, typ, cat["id"]) if cat else None
                print(" Canal", "EXISTE/CONFERIR" if ch else "CRIAR", name, "[" + policy + "]")
        print("Inclui permissões, atribuição de Dono e Sigma 67 ao proprietário e filtro do ponto no spam.")
        print("Ban instantâneo por ponto exige bot permanentemente online; não é feito pelo AutoMod.")
        return

    problems = []
    roles = ensure_roles(api, guild_id, guild, problems)
    owner_id = guild.get("owner_id")
    moderator_id = roles.get("Moderação", {}).get("id")
    post_guide_id = None
    for category, specs in CHANNELS.items():
        cat = find_channel(channels, category, 4)
        kind = "logs" if category == "SEGURANÇA" else "category"
        cat_ow = overwrites(cat.get("permission_overwrites", []) if cat else [],
                            guild_id, kind, owner_id, moderator_id)
        if not cat:
            cat = api.call("POST", "/guilds/" + guild_id + "/channels", {
                "name": category, "type": 4, "permission_overwrites": cat_ow
            })
            channels.append(cat)
            print("Categoria criada:", category)
        else:
            if cat_ow != cat.get("permission_overwrites", []):
                api.call("PATCH", "/channels/" + cat["id"], {"permission_overwrites": cat_ow})
                cat["permission_overwrites"] = cat_ow
            print("Categoria conferida:", category)
        for name, typ, topic, slow, policy in specs:
            ch = find_channel(channels, name, typ, cat["id"])
            target_ow = overwrites(ch.get("permission_overwrites", []) if ch else [],
                                   guild_id, policy, owner_id, moderator_id)
            if not ch:
                payload = {"name": name, "type": typ, "parent_id": cat["id"],
                           "permission_overwrites": target_ow}
                if typ == 0:
                    payload.update({"topic": topic, "rate_limit_per_user": slow})
                ch = api.call("POST", "/guilds/" + guild_id + "/channels", payload)
                channels.append(ch)
                print("Canal criado:", name)
                if name == "cargos":
                    post_guide_id = ch["id"]
            else:
                patch = {}
                if target_ow != ch.get("permission_overwrites", []):
                    patch["permission_overwrites"] = target_ow
                if typ == 0:
                    if int(ch.get("rate_limit_per_user", 0)) < slow:
                        patch["rate_limit_per_user"] = slow
                    if ch.get("topic") != topic:
                        patch["topic"] = topic
                if patch:
                    api.call("PATCH", "/channels/" + ch["id"], patch)
                    ch.update(patch)
                print("Canal conferido:", name)
    if post_guide_id:
        post_role_guide(api, post_guide_id,
                        "premium_subscriber" in {tag for r in roles.values() for tag in r.get("tags", {})},
                        problems)

    try:
        all_roles = api.call("GET", "/guilds/" + guild_id + "/roles")
        everyone = next(r for r in all_roles if r["id"] == guild_id)
        current = int(everyone.get("permissions", 0))
        reduced = current & ~INVITE & ~MENTION_ALL
        if reduced != current:
            api.call("PATCH", "/guilds/" + guild_id + "/roles/" + guild_id,
                     {"permissions": str(reduced)})
        print("Permissões de @everyone conferidas.")
    except (DiscordError, StopIteration) as error:
        problems.append("@everyone: " + str(error))
    try:
        patch = {}
        if guild.get("verification_level", 0) < 3:
            patch["verification_level"] = 3
        if guild.get("explicit_content_filter", 0) < 2:
            patch["explicit_content_filter"] = 2
        if patch:
            api.call("PATCH", "/guilds/" + guild_id, patch)
        print("Verificação e filtro de conteúdo conferidos.")
    except DiscordError as error:
        problems.append("Verificação/filtro: " + str(error))

    log = next((c for c in channels if c.get("name") == "logs-de-seguranca"
                and c.get("type") == 0), None)
    if log and "COMMUNITY" in guild.get("features", []):
        try:
            api.call("PATCH", "/guilds/" + guild_id,
                     {"safety_alerts_channel_id": log["id"]})
        except DiscordError as error:
            problems.append("Canal de alertas: " + str(error))
    apply_automod(api, guild_id, channels, problems)
    print("Configuração concluída. AutoMod do ponto BLOQUEIA e aplica timeout; não bane.")
    if problems:
        for problem in problems:
            print("ATENÇÃO:", problem)
        sys.exit("Configuração parcial: " + str(len(problems)) + " pendência(s)")
    print("SEM FALHAS DE API REPORTADAS. Execute audit para confirmar.")


if __name__ == "__main__":
    try:
        main()
    except DiscordError as error:
        sys.exit("Falha: " + str(error))
