import discord
from discord.ext import commands
import tls_client
import time
import json
import asyncio
import random
import os

# ===================== CONFIG =====================
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")  # 🔒 SECRET TOKEN
SCAN_MIN = 12
SCAN_MAX = 18
# ==================================================

if not DISCORD_TOKEN:
    raise RuntimeError("❌ DISCORD_TOKEN nicht gesetzt!")

CHANNELS_FILE = "channel_urls.json"
active_snipers = {}

# Lade gespeicherte URLs
if os.path.exists(CHANNELS_FILE):
    with open(CHANNELS_FILE, "r", encoding="utf-8") as f:
        channels_data = json.load(f)
else:
    channels_data = {}

# ==========================================
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

        self.seen_items = set()

    def convert_url(self, url):
        if "api/v2/catalog/items" in url:
            return url
        base = "https://www.vinted.de/api/v2/catalog/items?"
        params = url.split("?")[-1]
        if params == url:
            return base + "order=newest_first&per_page=20"
        if "order=" not in params:
            params += "&order=newest_first"
        return base + params

    def warmup(self):
        try:
            self.session.get("https://www.vinted.de", headers=self.headers)
        except:
            pass

    async def send_to_discord(self, item, bot):
        price = float(item["total_item_price"]["amount"])
        total = round(price + 0.70 + (price * 0.05) + 3.99, 2)
        item_id = item["id"]
        url = f"https://www.vinted.de/items/{item_id}"

        embed = discord.Embed(
            title=f"🔥 {item['title']}",
            url=url,
            color=0x09b1ba
        )

        embed.add_field(name="💶 Preis", value=f"{price:.2f} €", inline=True)
        embed.add_field(name="🚚 Gesamt ca.", value=f"{total:.2f} €", inline=True)
        embed.add_field(name="📏 Größe", value=item.get("size_title", "N/A"), inline=True)
        embed.add_field(
            name="⚡ Aktion",
            value=f"[🛒 Kaufen](https://www.vinted.de/transaction/buy/new?item_id={item_id})",
            inline=False
        )

        photos = item.get("photos", [])
        if photos:
            embed.set_image(url=photos[0]["url"].replace("/medium/", "/full/"))

        channel = bot.get_channel(self.channel_id)
        if channel:
            await channel.send(embed=embed)

    async def run(self, bot):
        self.warmup()
        print(f"🎯 Scan läuft für Channel {self.channel_id}")

        while True:
            try:
                r = self.session.get(self.api_url, headers=self.headers)

                if r.status_code == 200:
                    for item in r.j
