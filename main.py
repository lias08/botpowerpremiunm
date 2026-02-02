import discord
from discord.ext import commands
import tls_client
import json
import asyncio
import random
import os

# ===================== CONFIG =====================
# Holt den Token aus den Railway Umgebungsvariablen
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

# Scan-Intervalle (Sekunden)
SCAN_MIN = 12
SCAN_MAX = 18

# ===================== STORAGE SETUP =====================
# Speicherpfad für Railway (Volume) oder lokal
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
        except:
            return {}
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
        if "api/v2/catalog/items" in url:
            return url
        base = "https://www.vinted.de/api/v2/catalog/items?"
        params = url.split("?")[-1]
        if params == url:
            return base + "order=newest_first&per_page=20"
        if "order=" not in params:
            params += "&order=newest_first"
        return base + params

    async def run(self, bot):
        print(f"🎯 Scan gestartet für Channel {self.channel_id}")
        while True:
            try:
                # Kurzer Warmup/Cookie-Check
                self.session.get("https://www.vinted.de", headers=self.headers)
                
                r = self.session.get(self.api_url, headers=self.headers)
                if r.status_code == 200:
                    data = r.json()
                    items = data.get("items", [])
                    for item in items:
                        item_id = item["id"]
                        if item_id not in self.seen_items:
                            # Beim ersten Durchlauf nur IDs sammeln, nicht spammen
                            if self.seen_items:
                                await self.send_to_discord(item, bot)
                            self.seen_items.add(item_id)
                elif r.status_code == 403:
                    print(f"⚠️ 403 Forbidden für {self.channel_id}. IP eventuell blockiert.")
                    await asyncio.sleep(60)
                
                await asyncio.sleep(random.uniform(SCAN_MIN, SCAN_MAX))
            except Exception as e:
                print(f"❌ Fehler im Sniper-Loop: {e}")
                await asyncio.sleep(20)

    async def send_to_discord(self, item, bot):
        try:
            price = float(item["total_item_price"]["amount"])
            # Ungefähre Käuferschutz-Rechnung
            total = round(price + 0.70 + (price * 0.05) + 3.99, 2)
            url = f"https://www.vinted.de/items/{item['id']}"
            
            embed = discord.Embed(
                title=f"🔥 {item['title'][:250]}",
                url=url,
                color=0x09b1ba,
                timestamp=discord.utils.utcnow()
            )
            embed.add_field(name="💶 Preis", value=f"{price:.2f} €", inline=True)
            embed.add_field(name="🚚 Gesamt ca.", value=f"{total:.2f} €", inline=True)
            embed.add_field(name="📏 Größe", value=item.get("size_title", "N/A"), inline=True)
            embed.add_field(name="⚡ Aktion", value=f"[🛒 Direkt Kaufen](https://www.vinted.de/transaction/buy/new?item_id={item['id']})")
            
            if item.get("photos"):
                img = item["photos"][0]["url"].replace("/medium/", "/full/")
                embed.set_image(url=img)

            channel = bot.get_channel(self.channel_id)
            if channel:
                await channel.send(embed=embed)
        except Exception as e:
            print(f"❌ Fehler beim Senden des Embeds: {e}")

# ===================== BOT SETUP =====================
intents = discord.Intents.default()
intents.message_content = True  # ZWINGEND ERFORDERLICH
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print("-" * 30)
    print(f"✅ Bot ist online: {bot.user.name}")
    print(f"📂 Datenpfad: {CHANNELS_FILE}")
    print("-" * 30)

    # Automatisch gespeicherte Scans neu starten
    for cid, data in channels_data.items():
        if cid not in active_snipers:
            url = data.get("url")
            sniper = VintedSniper(url, cid)
            active_snipers[cid] = sniper
            bot.loop.create_task(sniper.run(bot))

@bot.event
async def on_message(message):
    # Debug-Log: Zeigt in Railway an, wenn der Bot eine Nachricht sieht
    if not message.author.bot:
        print(f"📩 Nachricht von {message.author}: {message.content}")
    await bot.process_commands(message)

@bot.command()
async def startscan(ctx, url: str):
    cid = str(ctx.channel.id)
    if cid in active_snipers:
        return await ctx.send("⚠️ In diesem Kanal läuft bereits ein Scan.")

    if "vinted.de" not in url:
        return await ctx.send("❌ Bitte gib eine gültige Vinted.de URL an.")

    channels_data[cid] = {"url": url}
    save_channels(channels_data)

    sniper = VintedSniper(url, cid)
    active_snipers[cid] = sniper
    bot.loop.create_task(sniper.run(bot))
    
    await ctx.send(f"✅ Scan für diesen Kanal wurde gestartet!\nZiel-URL: <{url}>")

@bot.command()
async def stopscan(ctx):
    cid = str(ctx.channel.id)
    if cid in active_snipers:
        # Ein Neustart des Bots ist sauberer zum Stoppen, 
        # aber hier löschen wir ihn aus der Datenbank:
        del channels_data[cid]
        save_channels(channels_data)
        await ctx.send("🛑 Scan gestoppt und aus Speicher gelöscht. (Bot-Neustart erforderlich zum finalen Beenden)")
    else:
        await ctx.send("❌ Hier läuft kein aktiver Scan.")

@bot.command()
async def ping(ctx):
    await ctx.send(f"🏓 Pong! Latenz: {round(bot.latency * 1000)}ms")

# ===================== START =====================
if __name__ == "__main__":
    if not DISCORD_TOKEN:
        print("❌ FEHLER: DISCORD_TOKEN Umgebungsvariable fehlt!")
    else:
        bot.run(DISCORD_TOKEN)
