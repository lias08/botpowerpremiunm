import discord
from discord.ext import commands
import tls_client
import time
import json
import asyncio
import random
import os

# ===================== CONFIG =====================
DISCORD_TOKEN = "DEIN_DISCORD_BOT_TOKEN"  # Hier den Token aus deinen Umgebungsvariablen oder Secret holen

SCAN_MIN = 12     # nicht unter 12s
SCAN_MAX = 18
# ==================================================

CHANNELS_FILE = "channel_urls.json"
active_snipers = {}

# Lade gespeicherte URLs
if os.path.exists(CHANNELS_FILE):
    with open(CHANNELS_FILE, "r") as f:
        channels_data = json.load(f)
else:
    channels_data = {}

# ==========================================
class VintedSniper:
    def __init__(self, url, channel_id):
        self.channel_id = int(channel_id)
        self.api_url = self.convert_url(url)

        self.session = tls_client.Session(client_identifier="chrome_112")

        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
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
        self.warmup()
        print(f"🎯 Scan läuft für Channel {self.channel_id}")

        while True:
            try:
                r = self.session.get(self.api_url, headers=self.headers)

                if r.status_code == 200:
                    for item in r.json().get("items", []):
                        if item["id"] not in self.seen_items:
                            await self.send_to_discord(item, bot)
                            print("✅ NEU:", item["title"])
                            self.seen_items.add(item["id"])

                elif r.status_code == 403:
                    print("⚠️ 403 – Pause")
                    await asyncio.sleep(180)

                await asyncio.sleep(random.uniform(SCAN_MIN, SCAN_MAX))

            except Exception as e:
                print("❌ Fehler:", e)
                await asyncio.sleep(15)

# ==========================================
intents = discord.Intents.default()
intents.message_content = True  # Muss True sein, um Nachrichteninhalte zu lesen
bot = commands.Bot(command_prefix="!", intents=intents)

# Kommandos & Events
@bot.command(name="startscan")
async def startscan(ctx, url: str):
    # Debug: Zeigt den Befehl an
    print(f"🔍 Startscan für Channel {ctx.channel.id} mit URL: {url}")

    cid = str(ctx.channel.id)

    if cid in active_snipers:
        await ctx.send("⚠️ Scan läuft hier bereits.")
        return

    channels_data[cid] = {"url": url}
    with open(CHANNELS_FILE, "w") as f:
        json.dump(channels_data, f, indent=4)

    sniper = VintedSniper(url, cid)
    active_snipers[cid] = sniper
    bot.loop.create_task(sniper.run(bot))

    await ctx.send("✅ Scan gestartet & gespeichert.")

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
    if message.author == bot.user:
        return

    # Debug: Zeigt empfangene Nachricht an
    print(f"📩 Neue Nachricht empfangen: {message.content}")

    # Wenn der Befehl !startscan empfangen wird
    if message.content.startswith("!startscan"):
        print("✔️ Befehl erkannt: !startscan")
        args = message.content.split(" ", 1)
        if len(args) == 2:
            url = args[1]
            await startscan(message.channel, url)
        else:
            await message.channel.send("⚠️ Bitte gib eine gültige URL an.")

    await bot.process_commands(message)

bot.run(DISCORD_TOKEN)
