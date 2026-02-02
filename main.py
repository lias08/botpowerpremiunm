import discord
from discord.ext import commands
import tls_client
import json
import asyncio
import random
import os

# ===================== CONFIG =====================
# Token wird jetzt aus den Umgebungsvariablen geladen (Sicherheit!)
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

SCAN_MIN = 12     
SCAN_MAX = 18

# ===================== STORAGE SETUP =====================
# Railway löscht Dateien beim Neustart, außer sie liegen in einem Volume.
# Wir prüfen, ob der Ordner /data existiert (Railway Volume).
# Wenn nicht, nutzen wir den normalen Ordner (lokal am PC).
if os.path.exists("/data"):
    DATA_PATH = "/data"
else:
    DATA_PATH = "."

CHANNELS_FILE = os.path.join(DATA_PATH, "channel_urls.json")

print(f"📂 Speicherort für Daten: {CHANNELS_FILE}")

active_snipers = {}

# Lade gespeicherte URLs
def load_channels():
    if os.path.exists(CHANNELS_FILE):
        with open(CHANNELS_FILE, "r") as f:
            return json.load(f)
    return {}

def save_channels(data):
    with open(CHANNELS_FILE, "w") as f:
        json.dump(data, f, indent=4)

channels_data = load_channels()

# ==========================================
class VintedSniper:
    def __init__(self, url, channel_id):
        self.channel_id = int(channel_id)
        self.api_url = self.convert_url(url)

        self.session = tls_client.Session(
            client_identifier="chrome_112"
        )

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
                            if self.seen_items:
                                await self.send_to_discord(item, bot)
                                print(f"✅ NEU in {self.channel_id}: {item['title']}")
                            self.seen_items.add(item["id"])

                elif r.status_code == 403:
                    print(f"⚠️ 403 Forbidden (Channel {self.channel_id}) – IP Blockiert? Pause 3 Min.")
                    await asyncio.sleep(180)

                await asyncio.sleep(random.uniform(SCAN_MIN, SCAN_MAX))

            except Exception as e:
                print(f"❌ Fehler in {self.channel_id}: {e}")
                await asyncio.sleep(15)

# ==========================================
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.command(name="startscan")
async def startscan(ctx, url: str):
    cid = str(ctx.channel.id)

    if cid in active_snipers:
        await ctx.send("⚠️ Scan läuft hier bereits")
        return

    # Speichern über die neue Funktion
    channels_data[cid] = {"url": url}
    save_channels(channels_data)

    sniper = VintedSniper(url, cid)
    active_snipers[cid] = sniper
    bot.loop.create_task(sniper.run(bot))

    await ctx.send("✅ Scan gestartet & gespeichert (Persistent)")

@bot.event
async def on_ready():
    if not DISCORD_TOKEN:
        print("❌ FEHLER: Kein Token gefunden! Bitte setze die Umgebungsvariable DISCORD_TOKEN.")
        return

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

if __name__ == "__main__":
    if DISCORD_TOKEN:
        bot.run(DISCORD_TOKEN)
    else:
        print("❌ Bitte Token in .env oder Railway Variables eintragen!")