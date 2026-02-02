# ===== AUDIOOP FIX (MUSS GANZ OBEN STEHEN) =====
import sys
import types

fake_audioop = types.ModuleType("audioop")
sys.modules["audioop"] = fake_audioop
# ==============================================

import discord
from discord.ext import commands
import asyncio
import os

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN") or "DEIN_TOKEN_HIER"

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"🤖 Bot online als {bot.user}")

@bot.command()
async def ping(ctx):
    await ctx.send("🏓 Pong")

bot.run(DISCORD_TOKEN)
