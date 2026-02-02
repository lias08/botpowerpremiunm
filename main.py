import discord
from discord.ext import commands
import tls_client
import asyncio
import json
import os
import random

# ===================== CONFIG =====================
DISCORD_TOKEN = "DEIN_DISCORD_TOKEN_HIER"

SCAN_MIN = 10   # sicher
SCAN_MAX = 15   # sicher
# ==================================================

CHANNELS_FILE = "channel_urls.json"
active_snipers = {}

# ------------------ Load URLs ------------------
if os.path.exists(CHANNELS_FILE):
    with open(CHANNELS_FILE, "r", encoding="utf-8") as f:
        channels_data = json.load(f)
else:
    channels_data = {}

# ================== SNIPER ==================
class VintedSniper:
    def __init__(self, url, channel_id):
        self.channel_id = int(channel_id)
        self.api_url = self.convert_url(url)

        self.session = tls_client.Session(
            client_identifier="chrome_112"
        )

        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Accept": "application/json",
            "Referer": "https://www.vinted.de/"
        }

        self.seen_items = set()

    def convert_url(self, url):
        if "api/v2/catalog/items" in url:
            return url

        base = "https://www.vinted.de/api/v2/catalog/items?"
        params = url.split("?", 1)[1] if "?" in url else ""
        params = params.split("&search_id")[0]
        params = params.split("&time")[0]
        params = params.split("&page")[0]

        if "order=" not in params:
            params += "&order=newest_first"

        return base + params

    async def send_item(self, bot, item):
        channel = bot.get_channel(self.channel_id)
        if not channel:
            return

        price = float(item["total_item_price"]["amount"])
        item_id = item["id"]
        url = f"https://www.vinted.de/items/{item_id}"

        embed = discord.Embed(
            title=item["title"],
            url=url,
            color=0x09b1ba
        )

        embed.add_field(name="💶 Preis", value=f"{price:.2f} €", inline=True)
        embed.add_field(name="📏 Größe", value=item.get("size_title", "N/A"), inline=True)

        photos = item.get("photos", [])
        if photos:
            embed.set_image(url=photos[0]["url"])

        await channel.send(embed=embed)

    async def run(self, bot):
        print(f"🎯 Scan gestartet | Channel {self.channel_id}")

        while True:
            try:
                r = self.session.get(self.api_url, headers=self.headers)

                if r.status_code != 200:
                    print(f"⚠️ HTTP {r.status_code} – Pause")
                    await asyncio.sleep(60)
                    continue

                items = r.json().get("items", [])
                print(f"🔍 Channel {self.channel_id} | Items: {len(items)}")

                for item in items:
                    if item["id"] not in self.seen_items:
                        if self.seen_items:
                            await self.send_item(bot, item)
                            print("✅ NEU:", item["title"])

                        self.seen_items.add(item["id"])

                await asyncio.sleep(random.uniform(SCAN_MIN, SCAN_MAX))

            except Exception as e:
                print("❌ Fehler:", e)
                await asyncio.sleep(30)

# ================== DISCORD ==================
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.command()
async def startscan(ctx, url: str):
    cid = str(ctx.channel.id)

    if cid in active_snipers:
        await ctx.send("⚠️ Scan läuft hier bereits")
        return

    channels_data[cid] = {"url": url}
    with open(CHANNELS_FILE, "w", encoding="utf-8") as f:
        json.dump(channels_data, f, indent=4)

    sniper = VintedSniper(url, cid)
    active_snipers[cid] = sniper
    bot.loop.create_task(sniper.run(bot))

    await ctx.send("✅ Scan gestartet")

@bot.event
async def on_ready():
    print(f"🤖 Eingeloggt als {bot.user}")
    print(f"📦 Geladene Channels: {list(channels_data.keys())}")

    for cid, data in channels_data.items():
        if cid in active_snipers:
            continue

        url = data.get("url")
        sniper = VintedSniper(url, cid)
        active_snipers[cid] = sniper
        bot.loop.create_task(sniper.run(bot))

bot.run(DISCORD_TOKEN)
