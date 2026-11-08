#!/usr/bin/env python3
"""Guardião opcional 24/7: qualquer tentativa de escrever no #spam aciona ban.

NÃO roda no GitHub Actions, NÃO está hospedado e NÃO começa automaticamente.
Precisa de discord.py 2.x e do bot online, com MANAGE_GUILD e BAN_MEMBERS.
Não precisa da permissão privilegiada Message Content: usa autor e canal do evento.
"""
import hashlib
import hmac
import os

import discord

FINGERPRINT = "cf1a67632a67f690daacb0e2b2c11c7156d8f59d6dc27bb85c5d1114e58ad02e"
TRAP_RULE_NAME = "WP | Armadilha spam"
TRAP_PATTERN = r"[\s\S]+"
TRAP_CHANNEL = "spam"
TRAP_CATEGORY = "COMUNIDADE"
DRY_RUN = os.environ.get("WP_DRY_RUN", "").strip() == "1"

intents = discord.Intents.none()
intents.guilds = True
intents.guild_messages = True
intents.auto_moderation_execution = True
client = discord.Client(intents=intents)


def authorized(guild_id):
    return hmac.compare_digest(
        hashlib.sha256(str(guild_id).encode("ascii")).hexdigest(), FINGERPRINT
    )


def is_trap(channel):
    return (
        isinstance(channel, discord.TextChannel)
        and channel.name == TRAP_CHANNEL
        and channel.category is not None
        and channel.category.name == TRAP_CATEGORY
    )


async def ban_from_trap(guild, user_id):
    """Só bane membro não proprietário, no servidor previamente autorizado."""
    if not guild or not authorized(guild.id) or user_id == guild.owner_id:
        return
    if client.user and user_id == client.user.id:
        return
    if DRY_RUN:
        print("SIMULAÇÃO: evento da armadilha detectado; nenhum ban aplicado.")
        return
    try:
        # Remove até 1 dia de mensagens anteriores do infrator no servidor.
        # O Discord pode recusar o banimento por falta de permissão/hierarquia.
        await guild.ban(
            discord.Object(id=user_id),
            reason="WiredParadise: mensagem ou anexo enviado ao canal-armadilha #spam",
            delete_message_seconds=86400,
        )
        print("Armadilha acionada: membro banido e mensagens recentes solicitadas para exclusão.")
    except discord.Forbidden:
        print("Ban recusado: revise Ban Members e hierarquia do cargo do bot.")
    except discord.HTTPException as error:
        print("Ban falhou:", type(error).__name__)


@client.event
async def on_ready():
    print("Guardião da armadilha conectado.", "(SIMULAÇÃO)" if DRY_RUN else "(BAN ATIVO)")


@client.event
async def on_message(message):
    """Pega qualquer mensagem publicada no spam, inclusive só imagem/vídeo/sticker.

    Não consultamos content/embeds/attachments: MESSAGE_CONTENT não é necessário.
    Textos bloqueados antes do envio pelo AutoMod são tratados em on_automod_action.
    """
    if not message.guild or not authorized(message.guild.id):
        return
    if not is_trap(message.channel):
        return
    if message.webhook_id:
        # Webhooks não são membros baníveis. Tenta remover apenas a mensagem.
        if not DRY_RUN:
            try:
                await message.delete()
                print("Mensagem de webhook removida da armadilha.")
            except discord.HTTPException:
                print("Falha ao remover mensagem de webhook.")
        return
    if message.type not in (discord.MessageType.default, discord.MessageType.reply):
        return
    await ban_from_trap(message.guild, message.author.id)


@client.event
async def on_automod_action(execution):
    """O AutoMod bloqueia texto antes de publicar. Banimos pelo evento de bloqueio."""
    if not authorized(execution.guild_id):
        return
    if execution.action.type != discord.AutoModRuleActionType.block_message:
        return
    guild = client.get_guild(execution.guild_id)
    if not guild:
        return
    channel = guild.get_channel(execution.channel_id)
    if not is_trap(channel):
        return
    try:
        rule = await execution.fetch_rule()
    except discord.HTTPException:
        print("Não foi possível conferir a regra da armadilha; ban ignorado.")
        return
    if (
        rule.id != execution.rule_id
        or rule.name != TRAP_RULE_NAME
        or not rule.enabled
        or tuple(getattr(rule.trigger, "regex_patterns", ()) or ()) != (TRAP_PATTERN,)
    ):
        print("Regra da armadilha divergente; ban ignorado.")
        return
    await ban_from_trap(guild, execution.user_id)


if __name__ == "__main__":
    token = os.getenv("DISCORD_BOT_TOKEN", "").strip()
    if not token:
        raise SystemExit("Configure DISCORD_BOT_TOKEN como Secret da hospedagem.")
    client.run(token, log_handler=None)
