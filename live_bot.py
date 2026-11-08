#!/usr/bin/env python3
"""Opcional: bot online que bane pelo AutoMod da mensagem '.' somente no #spam.

Este programa NÃO é executado pelo GitHub Actions e NÃO inicia sozinho.
Requer hospedar um bot, discord.py 2.x, MANAGE_GUILD e BAN_MEMBERS.
Não requer Message Content Intent: usa evento de execução do AutoMod.
"""
import hashlib
import hmac
import os
import discord

FINGERPRINT = "cf1a67632a67f690daacb0e2b2c11c7156d8f59d6dc27bb85c5d1114e58ad02e"
RULE_NAME = "WP | Ponto no spam"

intents = discord.Intents.none()
intents.guilds = True
intents.auto_moderation_execution = True
client = discord.Client(intents=intents)


def authorized(guild_id):
    return hmac.compare_digest(
        hashlib.sha256(str(guild_id).encode("ascii")).hexdigest(), FINGERPRINT
    )


@client.event
async def on_ready():
    print("Bot de moderação conectado. Nenhum ID ou token será exibido.")


@client.event
async def on_automod_action(execution):
    # Somente bloqueio da regra específica no canal específico.
    if not authorized(execution.guild_id):
        return
    if execution.action.type != discord.AutoModRuleActionType.block_message:
        return
    guild = client.get_guild(execution.guild_id)
    if not guild or execution.user_id == guild.owner_id:
        return
    channel = guild.get_channel(execution.channel_id)
    if not channel or channel.name != "spam":
        return
    if not channel.category or channel.category.name != "COMUNIDADE":
        return

    try:
        rule = await execution.fetch_rule()
    except discord.HTTPException as error:
        print("Não foi possível validar a regra AutoMod:", type(error).__name__)
        return
    if rule.name != RULE_NAME or not rule.enabled or rule.id != execution.rule_id:
        return

    # Verifica se o filtro ainda está configurado para o ponto isolado.
    patterns = tuple(getattr(rule.trigger, "regex_patterns", ()) or ())
    if patterns != (r"^\.$",):
        print("Filtro alterado; ban automático suspenso para evitar falsos positivos.")
        return
    try:
        await guild.ban(discord.Object(id=execution.user_id),
                        reason="WiredParadise: mensagem apenas '.' no #spam",
                        delete_message_seconds=0)
        print("Regra de ponto aplicada: membro banido no canal spam.")
    except discord.Forbidden:
        print("Falha ao banir: falta de permissão ou hierarquia de cargos.")
    except discord.HTTPException as error:
        print("Falha ao banir:", type(error).__name__)


if __name__ == "__main__":
    token = os.environ.get("DISCORD_BOT_TOKEN", "").strip()
    if not token:
        raise SystemExit("Defina DISCORD_BOT_TOKEN na configuração segura do host.")
    client.run(token, log_handler=None)
