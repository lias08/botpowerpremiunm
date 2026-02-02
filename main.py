import discord
from discord.ext import commands
import tls_client
import json
import asyncio
import random
import os
from datetime import datetime

# ===================== CONFIG =====================
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
SCAN_MIN = 12
SCAN_MAX = 18

if os.path.exists("/data"):
    DATA_PATH = "/data"
else:
    DATA_PATH = "."

CHANNELS_FILE = os.path.join(DATA_PATH, "channel_urls.json")

def load_channels():
    if os.path.exists(CHANNELS_FILE):
        try:
            with open(CHANNELS_FILE, "r") as f:
                return json.load(f)
        except: return {}
    return {}

def save_channels(data):
    with open(CHANNELS_FILE, "w") as f:
        json.dump(data, f, indent=4)

channels_data = load_channels()
active_snipers = {}

# ===================== SNIPER LOGIK =====================
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
        if "api/v2/catalog/items" in url: return url
        base = "https://www.vinted.de/api/v2/catalog/items?"
        params = url.split("?")[-1]
        return base + params + "&order=newest_first&per_page=20"

    async def run(self, bot):
        print(f"🎯 Scan aktiv für Channel {self.channel_id}")
        while True:
            try:
                # Cookies holen
                self.session.get("https://www.vinted.de", headers=self.headers)
                r = self.session.get(self.api_url, headers=self.headers)
                
                if r.status_code == 200:
                    items = r.json().get("items", [])
                    for item in items:
                        if item["id"] not in self.seen_items:
                            if self.seen_items: # Nur bei neuen Items senden
                                await self.send_to_discord(item, bot)
                            self.seen_items.add(item["id"])
                
                await asyncio.sleep(random.uniform(SCAN_MIN, SCAN_MAX))
            except Exception as e:
                print(f" Fehler: {e}")
                await asyncio.sleep(20)

    async def send_to_discord(self, item, bot):
        try:
            price = float(item["total_item_price"]["amount"])
            # Gebühren: 0,70€ + 5% vom Preis + ca. 3,99€ Versand
            fees = 0.70 + (price * 0.05)
            total = round(price + fees + 3.99, 2)
            
            url = f"https://www.vinted.de/items/{item['id']}"
            
            # Zeitstempel für "Vor X Sekunden hochgeladen"
            upload_time = datetime.fromtimestamp(item["photo_numeric_id"] / 1000) if "photo_numeric_id" in item else datetime.utcnow()

            embed = discord.Embed(
                title=f"👕 {item['title'][:250]}",
                url=url,
                color=0x00FFCC,
                timestamp=discord.utils.utcnow()
            )
            
            embed.add_field(name="💶 Preis", value=f"**{price:.2f} €**", inline=True)
            embed.add_field(name="🚚 Gesamt ca.", value=f"{total:.2f} €", inline=True)
            embed.add_field(name="📏 Größe", value=item.get("size_title", "N/A"), inline=True)
            embed.add_field(name="✨ Zustand", value=item.get("status", "N/A"), inline=True)
            embed.add_field(name="🏢 Marke", value=item.get("brand_title", "N/A"), inline=True)
            embed.add_field(name="⏰ Upload", value=f"<t:{int(upload_time.timestamp())}:R>", inline=True)
            
            embed.add_field(
                name="🔗 Aktionen", 
                value=f"[🛒 Kaufen](https://www.vinted.de/transaction/buy/new?item_id={item['id']}) | [💬 Chat](https://www.vinted.de/items/{item['id']})", 
                inline=False
            )
            
            if item.get("photos"):
                img = item["photos"][0]["url"].replace("/medium/", "/full/")
                embed.set_image(url=img)
            
            embed.set_footer(text="Costello Vinted Sniper • Schnell zuschlagen!")

            channel = bot.get_channel(self.channel_id)
            if channel:
                await channel.send(embed=embed)
        except Exception as e:
            print(f"Embed Fehler: {e}")

# ===================== BOT SETUP =====================
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"✅ Online: {bot.user}")
    for cid, data in channels_data.items():
        sniper = VintedSniper(data["url"], cid)
        active_snipers[cid] = sniper
        bot.loop.create_task(sniper.run(bot))

@bot.event
async def on_message(message):
    if not message.author.bot:
        print(f"Nachricht: {message.content}")
    await bot.process_commands(message)

@bot.command()
async def startscan(ctx, url: str):
    cid = str(ctx.channel.id)
    channels_data[cid] = {"url": url}
    save_channels(channels_data)
    sniper = VintedSniper(url, cid)
    active_snipers[cid] = sniper
    bot.loop.create_task(sniper.run(bot))
    await ctx.send(f"🚀 **Sniper gestartet!**\nIch scanne jetzt diesen Kanal nach neuen Artikeln.")

@bot.command()
async def ping(ctx):
    await ctx.send("🏓 Pong! Ich funktioniere.")

bot.run(DISCORD_TOKEN)
