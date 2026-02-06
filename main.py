import discord
from discord.ext import commands
import tls_client
import time
import json
import asyncio
import random
import os
from dotenv import load_dotenv

# Lade Umgebungsvariablen
load_dotenv()

# ===================== CONFIG =====================
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

# WICHTIG: Höhere Pausen, um 429-Fehler zu vermeiden
SCAN_MIN = 45     # Mindestens 45 Sekunden Pause
SCAN_MAX = 80     # Bis zu 80 Sekunden Pause
CHANNELS_FILE = "channel_urls.json"

active_snipers = {}

# Lade gespeicherte URLs
if os.path.exists(CHANNELS_FILE):
    try:
        with open(CHANNELS_FILE, "r") as f:
            channels_data = json.load(f)
    except:
        channels_data = {}
else:
    channels_data = {}

# ==========================================
class VintedSniper:
    def __init__(self, url, channel_id):
        self.channel_id = int(channel_id)
        self.url = url
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
        """Holt frische Cookies von der Vinted-Seite"""
        try:
            self.session.get("https://www.vinted.de", headers=self.headers)
            print(f"🍪 Cookies für Channel {self.channel_id} geladen.")
        except:
            pass

    async def send_to_discord(self, item, bot):
        try:
            price = float(item["total_item_price"]["amount"])
            total = round(price + 0.70 + (price * 0.05) + 3.99, 2)
            item_id = item["id"]
            url = f"https://www.vinted.de/items/{item_id}"

            embed = discord.Embed(
                title=f"🔥 {item.get('title', 'Vinted Fund')}",
                url=url,
                color=0x09b1ba,
                timestamp=discord.utils.utcnow()
            )
            embed.add_field(name="💶 Preis", value=f"{price:.2f} €", inline=True)
            embed.add_field(name="📏 Größe", value=item.get("size_title", "N/A"), inline=True)
            embed.add_field(name="⚡ Aktion", value=f"[🛒 Kaufen](https://www.vinted.de/transaction/buy/new?item_id={item_id})", inline=False)

            photos = item.get("photos", [])
            if photos:
                embed.set_image(url=photos[0]["url"].replace("/medium/", "/full/"))

            channel = bot.get_channel(self.channel_id)
            if channel:
                await channel.send(embed=embed)
        except Exception as e:
            print(f"Embed Fehler: {e}")

    async def run(self, bot):
        self.warmup()
        print(f"🎯 Scan aktiv für Channel {self.channel_id}")
        
        # Erster Scan zum Initialisieren der IDs
        try:
            r = self.session.get(self.api_url, headers=self.headers)
            if r.status_code == 200:
                for item in r.json().get("items", []):
                    self.seen_items.add(item["id"])
        except:
            pass

        while True:
            try:
                r = self.session.get(self.api_url, headers=self.headers)

                if r.status_code == 200:
                    data = r.json()
                    for item in data.get("items", []):
                        if item["id"] not in self.seen_items:
                            await self.send_to_discord(item, bot)
                            self.seen_items.add(item["id"])
                            print(f"✅ NEU gefunden in Channel {self.channel_id}")

                elif r.status_code == 429:
                    print(f"⚠️ 429 Rate Limit in {self.channel_id}. IP gesperrt! Warte 10 Min...")
                    await asyncio.sleep(600) # 10 Minuten Zwangspause
                
                elif r.status_code == 403:
                    print(f"⛔ 403 Forbidden in {self.channel_id}. Warte 5 Min...")
                    await asyncio.sleep(300)

                # Zufällige Pause zwischen den Scans
                await asyncio.sleep(random.uniform(SCAN_MIN, SCAN_MAX))

            except Exception as e:
                print(f"❌ Loop Fehler in {self.channel_id}: {e}")
                await asyncio.sleep(30)

# ==========================================
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

def save_data():
    with open(CHANNELS_FILE, "w") as f:
        json.dump(channels_data, f, indent=4)

@bot.event
async def on_ready():
    print(f"🤖 Costello Bot online als {bot.user}")
    
    for cid, data in channels_data.items():
        urls = data.get("urls", [])
        # Support für das alte Format
        if not urls and data.get("url"):
            urls = [data.get("url")]
        
        active_snipers[cid] = []
        for url in urls:
            sniper = VintedSniper(url, cid)
            active_snipers[cid].append(sniper)
            bot.loop.create_task(sniper.run(bot))

@bot.command()
async def startscan(ctx, url: str):
    cid = str(ctx.channel.id)
    
    if cid not in channels_data:
        channels_data[cid] = {"urls": []}
    
    if url in channels_data[cid].get("urls", []):
        await ctx.send("⚠️ Diese URL wird hier bereits gescannt.")
        return

    # In Liste speichern
    if "urls" not in channels_data[cid]:
        channels_data[cid]["urls"] = []
    
    channels_data[cid]["urls"].append(url)
    save_data()
    
    sniper = VintedSniper(url, cid)
    if cid not in active_snipers:
        active_snipers[cid] = []
    active_snipers[cid].append(sniper)
    
    bot.loop.create_task(sniper.run(bot))
    await ctx.send(f"✅ Suche hinzugefügt! (Aktive Suchen in diesem Channel: {len(channels_data[cid]['urls'])})")

@bot.command()
async def stopall(ctx):
    cid = str(ctx.channel.id)
    if cid in channels_data:
        channels_data[cid]["urls"] = []
        save_data()
        await ctx.send("✅ Alle Suchen für diesen Channel gelöscht. Starte den Bot bei Railway neu, um die laufenden Prozesse zu killen.")

if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)
