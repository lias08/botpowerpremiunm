import discord
from discord.ext import commands
import tls_client
import json
import asyncio
import random
import os
import time

# ===================== CONFIG =====================
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")  # SECRET
SCAN_DELAY = 2.5  # stabil, kein Heartbeat‑Freeze
# =================================================

if not DISCORD_TOKEN:
    raise RuntimeError("DISCORD_TOKEN fehlt")

CHANNELS_FILE = "channel_urls.json"
active_tasks = {}

# ===================== LOAD CHANNELS =====================
if os.path.exists(CHANNELS_FILE):
    with open(CHANNELS_FILE, "r", encoding="utf-8") as f:
        channels_data = json.load(f)
else:
    channels_data = {}

# ===================== SNIPER =====================
class VintedSniper:
    def __init__(self, url, channel_id):
        self.channel_id = int(channel_id)
        self.api_url = self.convert_url(url)

        self.session = tls_client.Session(
            client_identifier="chrome_112",
            random_tls_extension_order=True
        )

        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "de-DE,de;q=0.9",
            "Referer": "https://www.vinted.de/"
        }

        self.seen = set()

    def convert_url(self, url):
        if "api/v2/catalog/items" in url:
            return url
        params = url.split("?")[-1]
        if "order=" not in params:
            params += "&order=newest_first"
        return f"https://www.vinted.de/api/v2/catalog/items?{params}&per_page=20"

    def warmup(self):
        try:
            self.session.get("https://www.vinted.de", headers=self.headers)
            time.sleep(0.5)
        except:
            pass

    async def send_item(self, bot, item):
        item_id = item["id"]
        price = float(item["total_item_price"]["amount"])
        url = f"https://www.vinted.de/items/{item_id}"

        embed = discord.Embed(
            title=item["title"],
            url=url,
            color=0x09b1ba
        )

        embed.add_field(name="💶 Preis", value=f"{price:.2f} €", inline=True)
        embed.add_field(name="📦 Zustand", value=item.get("status", "N/A"), inline=True)

        photos = item.get("photos", [])
        if photos:
            embed.set_image(url=photos[0]["url"].replace("/medium/", "/full/"))

        channel = bot.get_channel(self.channel_id)
        if channel:
            await channel.send(embed=embed)

    async def run(self, bot):
        self.warmup()
        print(f"🚀 Scan aktiv für Channel {self.channel_id}")

        while True:
            try:
                r = self.session.get(self.api_url, headers=self.headers)

                if r.status_code == 200:
                    data = r.json()
                    for item in data.get("items", []):
                        if item["id"] not in self.seen:
                            if self.seen:
                                await self.send_item(bot, item)
                            self.seen.add(item["id"])

                elif r.status_code in (401, 403):
                    print(f"⚠️ {self.channel_id} HTTP {r.status_code}")
                    await asyncio.sleep(30)

                await asyncio.sleep(SCAN_DELAY)

            except Exception as e:
                print("❌ Fehler:", e)
                await asyncio.sleep(10)

# ===================== DISCORD =====================
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print("🤖 Bot online")

    for cid, data in channels_data.items():
        if cid in active_tasks:
            continue

        sniper = VintedSniper(data["url"], cid)
        task = asyncio.create_task(sniper.run(bot))
        active_tasks[cid] = task

    print(f"🔥 {len(active_tasks)} Channels aktiv")

bot.run(DISCORD_TOKEN)
