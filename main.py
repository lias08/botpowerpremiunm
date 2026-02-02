import discord
from discord.ext import commands
import os
import json
import random
import asyncio
from dotenv import load_dotenv

# ===================== CONFIG =====================
load_dotenv()  # Lädt Umgebungsvariablen aus der .env-Datei

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")  # Hole den Token aus der Umgebungsvariablen
SCAN_MIN = 12     # nicht unter 12s
SCAN_MAX = 18
CHANNELS_FILE = "channel_urls.json"
active_snipers = {}

if not DISCORD_TOKEN:
    print("❌ Kein Token gefunden! Bitte stelle sicher, dass der Discord-Token in den Umgebungsvariablen gesetzt ist.")
    exit(1)

# Lade gespeicherte URLs
if os.path.exists(CHANNELS_FILE):
    with open(CHANNELS_FILE, "r") as f:
        channels_data = json.load(f)
else:
    channels_data = {}

# ============================================
class VintedSniper:
    def __init__(self, url, channel_id):
        self.channel_id = int(channel_id)
        self.api_url = self.convert_url(url)
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

    async def send_to_discord(self, item, bot):
        price = float(item["total_item_price"]["amount"])
        total = round(price + 0.70 + (price * 0.05) + 3.99, 2)
        item_id = item["id"]
        url = f"https://www.vinted.de/items/{item_id}"

        embed = discord.Embed(
            title=f"🔥 {item['title']}",
            url=url,
            color=0x09b1ba,
            timestamp=discord.utils.utcnow()
        )

        embed.add_field(name="💶 Preis", value=f"{price:.2f} €", inline=True)
        embed.add_field(name="🚚 Gesamt ca.", value=f"{total:.2f} €", inline=True)
        embed.add_field(name="📏 Größe", value=item.get("size_title", "N/A"), inline=True)
        embed.add_field(
            name="⚡ Aktionen",
            value=f"[🛒 Kaufen](https://www.vinted.de/transaction/buy/new?item_id={item_id})",
            inline=False
        )

        photos = item.get("photos", [])
        if photos:
            img = photos[0]["url"].replace("/medium/", "/full/")
            embed.set_image(url=img)

        channel = bot.get_channel(self.channel_id)
        if channel:
            await channel.send(embed=embed)

    async def run(self, bot):
        print(f"🎯 Scan läuft für Channel {self.channel_id}")

        while True:
            try:
                r = requests.get(self.api_url)

                if r.status_code == 200:
                    for item in r.json().get("items", []):
                        if item["id"] not in self.seen_items:
                            await self.send_to_discord(item, bot)
                            self.seen_items.add(item["id"])

                elif r.status_code == 403:
                    print("⚠️ 403 – Pause")
                    await asyncio.sleep(180)

                await asyncio.sleep(random.uniform(SCAN_MIN, SCAN_MAX))

            except Exception as e:
                print("❌ Fehler:", e)
                await asyncio.sleep(15)

# ============================================
intents = discord.Intents.default()
intents.message_content = True  # Damit der Bot Nachrichteninhalte lesen kann
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.command(name="startscan")
async def startscan(ctx, url: str):
    print(f"Empfange Befehl: !startscan mit URL: {url}")
    cid = str(ctx.channel.id)

    if cid in active_snipers:
        await ctx.send("⚠️ Scan läuft hier bereits")
        return

    channels_data[cid] = {"url": url}
    with open(CHANNELS_FILE, "w") as f:
        json.dump(channels_data, f, indent=4)

    sniper = VintedSniper(url, cid)
    active_snipers[cid] = sniper
    bot.loop.create_task(sniper.run(bot))

    await ctx.send("✅ Scan gestartet & gespeichert")

@bot.event
async def on_ready():
    print(f"🤖 Eingeloggt als {bot.user}")

    for cid, data in channels_data.items():
        if cid in active_snipers:
            continue
        url = data.get("url")
        if not url:
            continue

        print(f"▶️ Starte gespeicherten Scan für Channel {cid}")
        sniper = VintedSniper(url, cid)
        active_snipers[cid] = sniper
        bot.loop.create_task(sniper.run(bot))

@bot.event
async def on_message(message):
    print(f"Nachricht empfangen: {message.content}")  # Dies hilft uns zu sehen, ob der Bot Nachrichten empfängt
    await bot.process_commands(message)

bot.run(DISCORD_TOKEN)
