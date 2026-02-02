import discord
from discord.ext import commands
import tls_client
import asyncio
import json
import os

# ===================== CONFIG =====================
SCAN_DELAY = 1  # 🔥 1 Sekunde pro Channel
DATA_DIR = "/data"
CHANNELS_FILE = f"{DATA_DIR}/channel_urls.json"

os.makedirs(DATA_DIR, exist_ok=True)

active_snipers = {}

# ===================== LOAD JSON =====================
if os.path.exists(CHANNELS_FILE):
    with open(CHANNELS_FILE, "r") as f:
        channels_data = json.load(f)
else:
    channels_data = {}

# ===================== POOL SNIPER =====================
class ChannelPoolSniper:
    def __init__(self, channel_id, urls):
        self.channel_id = int(channel_id)
        self.urls = [self.convert_url(u) for u in urls]
        self.index = 0
        self.seen_items = set()

        self.session = tls_client.Session(
            client_identifier="chrome_112"
        )

        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "de-DE,de;q=0.9",
            "Referer": "https://www.vinted.de/"
        }

    def convert_url(self, url):
        if "api/v2/catalog/items" in url:
            return url

        base = "https://www.vinted.de/api/v2/catalog/items?"
        params = url.split("?")[-1]

        if "order=" not in params:
            params += "&order=newest_first"

        return base + params

    async def send_to_discord(self, item, bot):
        price = float(item["total_item_price"]["amount"])
        item_id = item["id"]

        embed = discord.Embed(
            title=f"🔥 {item['title']}",
            url=f"https://www.vinted.de/items/{item_id}",
            color=0x09b1ba,
            timestamp=discord.utils.utcnow()
        )

        embed.add_field(name="💶 Preis", value=f"{price:.2f} €", inline=True)
        embed.add_field(name="📏 Größe", value=item.get("size_title", "N/A"), inline=True)

        photos = item.get("photos", [])
        if photos:
            embed.set_image(url=photos[0]["url"].replace("/medium/", "/full/"))

        channel = bot.get_channel(self.channel_id)
        if channel:
            await channel.send(embed=embed)

    async def run(self, bot):
        print(f"🎯 Pool-Scan gestartet | Channel {self.channel_id} | URLs: {len(self.urls)}")

        while True:
            try:
                url = self.urls[self.index]
                self.index = (self.index + 1) % len(self.urls)

                r = self.session.get(url, headers=self.headers)

                if r.status_code == 200:
                    for item in r.json().get("items", []):
                        if item["id"] not in self.seen_items:
                            if self.seen_items:
                                await self.send_to_discord(item, bot)
                            self.seen_items.add(item["id"])

                elif r.status_code == 403:
                    print(f"⚠️ 403 | Channel {self.channel_id}")
                    await asyncio.sleep(5)

                await asyncio.sleep(SCAN_DELAY)

            except Exception as e:
                print(f"❌ Fehler Channel {self.channel_id}:", e)
                await asyncio.sleep(3)

# ===================== DISCORD BOT =====================
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.command()
async def startscan(ctx, url: str):
    cid = str(ctx.channel.id)

    if cid in active_snipers:
        await ctx.send("⚠️ Scan läuft hier bereits")
        return

    channels_data[cid] = {"urls": [url]}
    with open(CHANNELS_FILE, "w") as f:
        json.dump(channels_data, f, indent=4)

    sniper = ChannelPoolSniper(cid, [url])
    active_snipers[cid] = sniper
    bot.loop.create_task(sniper.run(bot))

    await ctx.send("✅ Pool-Scan gestartet")

@bot.event
async def on_ready():
    print(f"🤖 Eingeloggt als {bot.user}")
    print("📦 Geladene Channels:", channels_data)

    for cid, data in channels_data.items():
        if cid in active_snipers:
            continue

        urls = data.get("urls", [])
        if not urls:
            continue

        sniper = ChannelPoolSniper(cid, urls)
        active_snipers[cid] = sniper
        bot.loop.create_task(sniper.run(bot))

# ===================== START =====================
TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN fehlt")

bot.run(TOKEN)
