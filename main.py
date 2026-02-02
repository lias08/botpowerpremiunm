import discord
from discord.ext import commands
import tls_client
import asyncio
import random
import json
import os

# ===================== CONFIG =====================
SCAN_MIN = 12
SCAN_MAX = 18

DATA_DIR = "/data"
CHANNELS_FILE = f"{DATA_DIR}/channel_urls.json"
active_snipers = {}

os.makedirs(DATA_DIR, exist_ok=True)

# ===================== LOAD CHANNELS =====================
if os.path.exists(CHANNELS_FILE):
    with open(CHANNELS_FILE, "r") as f:
        channels_data = json.load(f)
else:
    channels_data = {}

# ===================== SNIPER =====================
class VintedSniper:
    def __init__(self, url, channel_id):
        self.channel_id = int(channel_id)
        self.api_url = self.convert_url(url)
        self.seen_items = set()

        self.session = tls_client.Session(
            client_identifier="chrome_112"
        )

        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "de-DE,de;q=0.9",
            "Referer": "https://www.vinted.de/"
        }

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

        embed = discord.Embed(
            title=f"🔥 {item['title']}",
            url=f"https://www.vinted.de/items/{item_id}",
            color=0x09b1ba,
            timestamp=discord.utils.utcnow()
        )

        embed.add_field(name="💶 Preis", value=f"{price:.2f} €")
        embed.add_field(name="🚚 Gesamt ca.", value=f"{total:.2f} €")
        embed.add_field(name="📏 Größe", value=item.get("size_title", "N/A"))

        photos = item.get("photos", [])
        if photos:
            embed.set_image(url=photos[0]["url"].replace("/medium/", "/full/"))

        channel = bot.get_channel(self.channel_id)
        if channel:
            await channel.send(embed=embed)

    async def run(self, bot):
        self.warmup()
        print(f"🎯 Scan gestartet für Channel {self.channel_id}")

        while True:
            try:
                r = self.session.get(self.api_url, headers=self.headers)
                if r.status_code == 200:
                    for item in r.json().get("items", []):
                        if item["id"] not in self.seen_items:
                            if self.seen_items:
                                await self.send_to_discord(item, bot)
                            self.seen_items.add(item["id"])

                elif r.status_code == 403:
                    print("⚠️ 403 – Pause 3 Minuten")
                    await asyncio.sleep(180)

                await asyncio.sleep(random.uniform(SCAN_MIN, SCAN_MAX))

            except Exception as e:
                print("❌ Fehler:", e)
                await asyncio.sleep(15)

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

    channels_data[cid] = {"url": url}
    with open(CHANNELS_FILE, "w") as f:
        json.dump(channels_data, f)

    sniper = VintedSniper(url, cid)
    active_snipers[cid] = sniper
    bot.loop.create_task(sniper.run(bot))

    await ctx.send("✅ Scan gestartet")

@bot.event
async def on_ready():
    print(f"🤖 Eingeloggt als {bot.user}")

    for cid, data in channels_data.items():
        if cid not in active_snipers:
            sniper = VintedSniper(data["url"], cid)
            active_snipers[cid] = sniper
            bot.loop.create_task(sniper.run(bot))

# ===================== START =====================
TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN fehlt!")

bot.run(TOKEN)
