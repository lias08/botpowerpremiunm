import tls_client
import time
import os
import discord
from discord.ext import tasks, commands
from flask import Flask
from threading import Thread
import asyncio

# ==========================================
# KONFIGURATION (Laden aus Umgebungsvariablen)
# ==========================================
DISCORD_TOKEN = os.environ.get("DISCORD_TOKEN")
CHANNEL_ID = int(os.environ.get("CHANNEL_ID", 0)) # Muss ein Integer sein
BROWSER_URL = os.environ.get("BROWSER_URL")
# ==========================================

# 1. Flask Webserver (Damit Render den Bot nicht killt)
app = Flask(__name__)

@app.route('/')
def home():
    return "Discord Bot läuft! 🤖"

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# 2. Discord Bot Setup
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

# 3. Vinted Logik
def convert_url(url):
    if "api/v2/catalog/items" in url: return url
    base_api = "https://www.vinted.de/api/v2/catalog/items?"
    params = url.split('?')[-1]
    if params == url: return base_api + "per_page=20&order=newest_first"
    if "order=" not in params: params += "&order=newest_first"
    return base_api + params

class VintedScanner:
    def __init__(self):
        self.session = tls_client.Session(client_identifier="chrome_112")
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
        }
        self.seen_items = []
        # Erster Verbindungsaufbau für Cookies
        try: self.session.get("https://www.vinted.de", headers=self.headers)
        except: pass

    def get_clean_status(self, item):
        raw_status = item.get('status_id') or item.get('status') or "Unbekannt"
        mapping = {
            "6": "Neu mit Etikett ✨", "new_with_tags": "Neu mit Etikett ✨",
            "1": "Neu ohne Etikett ✨", "new_without_tags": "Neu ohne Etikett ✨",
            "2": "Sehr gut 👌", "very_good": "Sehr gut 👌",
            "3": "Gut 👍", "good": "Gut 👍",
            "4": "Zufriedenstellend 🆗", "satisfactory": "Zufriedenstellend 🆗"
        }
        return mapping.get(str(raw_status).lower(), str(raw_status))

    def fetch_new_items(self):
        # Scannt Vinted und gibt eine Liste neuer Items zurück
        api_url = convert_url(BROWSER_URL)
        new_found = []
        try:
            response = self.session.get(api_url, headers=self.headers)
            if response.status_code == 200:
                items = response.json().get("items", [])
                for item in items:
                    if item["id"] not in self.seen_items:
                        # Nur hinzufügen, wenn wir schon items kennen (damit beim Start nicht 20 spammen)
                        if len(self.seen_items) > 0:
                            new_found.append(item)
                        self.seen_items.append(item["id"])
                
                # Speicher begrenzen
                if len(self.seen_items) > 500: 
                    self.seen_items = self.seen_items[-200:]
            elif response.status_code == 403:
                print("⚠️ 403 Forbidden - IP Blocked temporary")
                return "BLOCK"
        except Exception as e:
            print(f"Fehler beim Scannen: {e}")
        
        return new_found

# Instanz erstellen
scanner = VintedScanner()

# 4. Der Loop Task (Ersetzt while True)
@tasks.loop(seconds=15)
async def scraper_task():
    channel = bot.get_channel(CHANNEL_ID)
    if not channel:
        print(f"❌ Kanal ID {CHANNEL_ID} nicht gefunden!")
        return

    # Achtung: Vinted Abfrage ist synchron, blockiert kurz den Bot. 
    # Bei 15s Intervall ist das okay.
    items = scanner.fetch_new_items()

    if items == "BLOCK":
        print("Bot pausiert für 2 Minuten wegen Block...")
        await asyncio.sleep(120)
        return

    if items:
        for item in items:
            print(f"Sende Item: {item.get('title')}")
            await send_discord_embed(channel, item)
            await asyncio.sleep(1) # Kleines Delay um Rate Limits zu vermeiden

async def send_discord_embed(channel, item):
    # Daten vorbereiten
    p = item.get('total_item_price')
    price_val = float(p.get('amount')) if isinstance(p, dict) else float(p)
    total_price = round(price_val + 0.70 + (price_val * 0.05) + 3.99, 2)
    item_id = item.get('id')
    item_url = item.get('url') or f"https://www.vinted.de/items/{item_id}"
    brand = item.get('brand_title') or "Keine Marke"
    status = scanner.get_clean_status(item)
    
    # Bilder
    photos = item.get('photos', [])
    if not photos and item.get('photo'): photos = [item.get('photo')]
    image_urls = [img.get('url', '').replace("/medium/", "/full/") for img in photos if img.get('url')]
    main_img = image_urls[0] if image_urls else ""

    # Embed bauen (Discord.py Style)
    embed = discord.Embed(
        title=f"🔥 {item.get('title')}",
        url=item_url,
        color=0x09b1ba,
        timestamp=discord.utils.utcnow()
    )
    embed.add_field(name="💶 Preis", value=f"**{price_val:.2f} €**", inline=True)
    embed.add_field(name="🚚 Gesamt ca.", value=f"**{total_price:.2f} €**", inline=True)
    embed.add_field(name="📏 Größe", value=item.get('size_title', 'N/A'), inline=True)
    embed.add_field(name="🏷️ Marke", value=brand, inline=True)
    embed.add_field(name="✨ Zustand", value=status, inline=True)
    embed.add_field(name="⚡ Aktion", value=f"[🛒 Kaufen](https://www.vinted.de/transaction/buy/new?item_id={item_id})", inline=False)
    
    if main_img:
        embed.set_image(url=main_img)
    embed.set_footer(text="Vinted Bot Token Version")

    try:
        await channel.send(embed=embed)
    except Exception as e:
        print(f"Fehler beim Senden: {e}")

@scraper_task.before_loop
async def before_scraper():
    print("Warte bis Bot bereit ist...")
    await bot.wait_until_ready()

@bot.event
async def on_ready():
    print(f'Eingeloggt als {bot.user} (ID: {bot.user.id})')
    if not scraper_task.is_running():
        scraper_task.start()

if __name__ == "__main__":
    # Webserver Thread starten
    t = Thread(target=run_web_server)
    t.start()
    
    # Bot starten
    if DISCORD_TOKEN:
        bot.run(DISCORD_TOKEN)
    else:
        print("❌ FEHLER: Kein DISCORD_TOKEN gefunden!")
