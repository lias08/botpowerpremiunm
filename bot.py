# ================= AUDIOOP FIX =================
import sys, types
sys.modules["audioop"] = types.ModuleType("audioop")
# ===============================================

import discord
from discord.ext import commands
import asyncio
import json
import os
import tls_client

# ================= CONFIG =================
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN") or "DEIN_TOKEN_HIER"
CHANNELS_FILE = "channel_urls.json"
SCAN_DELAY = 1.2  # Sekunden pro URL
# ==========================================

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

active_tasks = {}

# ---------- VINTED SCANNER ----------
class VintedScanner:
    def __init__(self, channel_id, url):
        self.channel_id = int(channel_id)
        self.api_url = self.convert_url(url)
        self.session = tls_client.Session(client_identifier="chrome_112")
        self.seen = set()

    def convert_url(self, url):
        if "api/v2/catalog/items" in url:
            return url
        base = "https://www.vinted.de/api/v2/catalog/items?"
        params = url.split("?")[-1]
        if "order=" not in params:
            params += "&order=newest_first"
        return base + params

    async def run(self):
        print(f"🚀 Scan gestartet für Channel {self.channel_id} URL: {self.api_url}")
        channel = bot.get_channel(self.channel_id)

        while True:
            try:
                r = self.session.get(self.api_url)
                if r.status_code == 200:
                    for item in r.json().get("items", []):
                        if item["id"] not in self.seen:
                            self.seen.add(item["id"])
                            if channel:
                                await channel.send(
                                    f"🔥 **{item['title']}**\n"
                                    f"💶 {item['price']['amount']}€\n"
                                    f"https://www.vinted.de/items/{item['id']}"
                                )
                await asyncio.sleep(SCAN_DELAY)
            except Exception as e:
                print(f"❌ Fehler in Channel {self.channel_id}: {e}")
                await asyncio.sleep(5)

# ---------- DISCORD EVENTS ----------
@bot.event
async def on_ready():
    print(f"🤖 Bot online als {bot.user}")

    if not os.path.exists(CHANNELS_FILE):
        print("⚠️ Keine channel_urls.json gefunden")
        return

    with open(CHANNELS_FILE, "r") as f:
        data = json.load(f)

    print(f"🔥 {len(data)} Channels geladen")

    for cid, cfg in data.items():
        urls = cfg.get("urls", [])
        if not urls:
            urls = [cfg.get("url")] if cfg.get("url") else []

        for url in urls:
            key = f"{cid}_{hash(url)}"  # eindeutiger Task-Key
            if key in active_tasks:
                continue
            scanner = VintedScanner(cid, url)
            task = asyncio.create_task(scanner.run())
            active_tasks[key] = task

    print("🚀 Alle Scans laufen")

# ---------- COMMAND ----------
@bot.command()
async def startscan(ctx, url: str):
    cid = str(ctx.channel.id)

    # Lade existierende Daten
    data = {}
    if os.path.exists(CHANNELS_FILE):
        with open(CHANNELS_FILE, "r") as f:
            data = json.load(f)

    # Update oder erstelle Channel-Eintrag
    if cid not in data:
        data[cid] = {"url": url, "urls": [url]}
    else:
        if url not in data[cid].get("urls", []):
            data[cid]["urls"].append(url)
            data[cid]["url"] = url  # letzte URL als Haupt-URL speichern

    with open(CHANNELS_FILE, "w") as f:
        json.dump(data, f, indent=4)

    # Starte Scan
    key = f"{cid}_{hash(url)}"
    if key in active_tasks:
        await ctx.send("⚠️ Scan für diese URL läuft bereits")
        return

    scanner = VintedScanner(cid, url)
    active_tasks[key] = asyncio.create_task(scanner.run())
    await ctx.send("✅ Scan gestartet & gespeichert")

# ---------- START ----------
bot.run(DISCORD_TOKEN)
