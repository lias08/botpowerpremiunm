# ================= AUDIOOP FIX =================
import sys, types
sys.modules["audioop"] = types.ModuleType("audioop")
# ===============================================

import discord
from discord.ext import commands
import asyncio
import json
import os
import aiohttp
from urllib.parse import urlparse, parse_qs, urlencode

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
CHANNELS_FILE = "channel_urls.json"
SCAN_DELAY = 1.0

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

active_tasks = {}

# --------- VINTED SCANNER ----------
class VintedScanner:
    def __init__(self, channel_id: int, url: str):
        self.channel_id = channel_id
        self.api_url = self.convert_url(url)
        self.seen = set()

    def convert_url(self, url: str) -> str:
        parsed = urlparse(url)
        params = parse_qs(parsed.query)

        params["page"] = ["1"]
        params["per_page"] = ["20"]
        params["order"] = ["newest_first"]

        flat = {}
        for k, v in params.items():
            for val in v:
                flat.setdefault(k, []).append(val)

        return "https://www.vinted.de/api/v2/catalog/items?" + urlencode(flat, doseq=True)

    async def run(self):
        channel = bot.get_channel(self.channel_id)
        if not channel:
            print(f"❌ Channel {self.channel_id} nicht gefunden")
            return

        print(f"🚀 Starte Scan: {self.channel_id}")

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Accept": "application/json",
            "Accept-Language": "de-DE,de;q=0.9",
            "Referer": "https://www.vinted.de/",
        }

        async with aiohttp.ClientSession(headers=headers) as session:
            while True:
                try:
                    async with session.get(self.api_url) as r:
                        if r.status != 200:
                            print(f"⚠️ {self.channel_id} Status {r.status}")
                            await asyncio.sleep(5)
                            continue

                        data = await r.json()
                        items = data.get("items", [])

                        if not items:
                            print(f"⚠️ {self.channel_id} → 0 Items")
                            await asyncio.sleep(SCAN_DELAY)
                            continue

                        for item in items:
                            item_id = item["id"]
                            if item_id in self.seen:
                                continue

                            self.seen.add(item_id)

                            await channel.send(
                                f"🔥 **{item['title']}**\n"
                                f"💶 {item['price']['amount']}€\n"
                                f"https://www.vinted.de/items/{item_id}"
                            )

                    await asyncio.sleep(SCAN_DELAY)

                except Exception as e:
                    print(f"❌ Fehler {self.channel_id}: {e}")
                    await asyncio.sleep(5)

# --------- DISCORD EVENTS ----------
@bot.event
async def on_ready():
    print(f"🤖 Bot online als {bot.user}")

    if not os.path.exists(CHANNELS_FILE):
        print("⚠️ channel_urls.json fehlt")
        return

    with open(CHANNELS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    for channel_id, cfg in data.items():
        for url in cfg.get("urls", []):
            key = f"{channel_id}_{hash(url)}"
            if key in active_tasks:
                continue

            scanner = VintedScanner(int(channel_id), url)
            active_tasks[key] = asyncio.create_task(scanner.run())

    print(f"🔥 {len(active_tasks)} Scanner laufen")

# --------- START ----------
bot.run(DISCORD_TOKEN)
