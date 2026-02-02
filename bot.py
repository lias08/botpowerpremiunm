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
from urllib.parse import urlparse, parse_qs, urlencode

TOKEN = os.getenv("DISCORD_TOKEN")
CHANNELS_FILE = "channel_urls.json"
SCAN_DELAY = 2

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

active_tasks = {}

# ---------- VINTED ----------
class VintedScanner:
    def __init__(self, channel_id: int, url: str):
        self.channel_id = channel_id
        self.api_url = self.convert(url)
        self.seen = set()
        self.session = tls_client.Session(
            client_identifier="chrome_120",
            random_tls_extension_order=True
        )

    def convert(self, url):
        parsed = urlparse(url)
        params = parse_qs(parsed.query)

        params["page"] = ["1"]
        params["per_page"] = ["20"]
        params["order"] = ["newest_first"]

        return "https://www.vinted.de/api/v2/catalog/items?" + urlencode(params, doseq=True)

    async def run(self):
        channel = bot.get_channel(self.channel_id)
        if not channel:
            print(f"❌ Channel {self.channel_id} nicht gefunden")
            return

        print(f"🚀 Starte Scan: {self.channel_id}")

        while True:
            try:
                r = self.session.get(
                    self.api_url,
                    headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                        "Accept": "application/json",
                        "Accept-Language": "de-DE,de;q=0.9",
                        "Referer": "https://www.vinted.de/",
                    }
                )

                if r.status_code != 200:
                    print(f"⚠️ {self.channel_id} Status {r.status_code}")
                    await asyncio.sleep(5)
                    continue

                data = r.json()
                items = data.get("items", [])

                if not items:
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

# ---------- DISCORD ----------
@bot.event
async def on_ready():
    print(f"🤖 Bot online als {bot.user}")

    with open(CHANNELS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    for channel_id, cfg in data.items():
        for url in cfg["urls"]:
            key = f"{channel_id}_{hash(url)}"
            if key in active_tasks:
                continue

            scanner = VintedScanner(int(channel_id), url)
            active_tasks[key] = asyncio.create_task(scanner.run())

    print(f"🔥 {len(active_tasks)} Scanner laufen")

bot.run(TOKEN)
