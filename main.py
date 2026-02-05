import tls_client
import time
import json
import os
from flask import Flask
from threading import Thread

# ==========================================
# KONFIGURATION
# ==========================================
WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "DEINE_WEBHOOK_URL_HIER_EINFUEGEN_WENN_LOKAL")
BROWSER_URL = os.environ.get("BROWSER_URL", "DEINE_VINTED_URL_HIER")
# ==========================================

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot läuft! 🚀"

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def convert_url(url):
    if "api/v2/catalog/items" in url: return url
    base_api = "https://www.vinted.de/api/v2/catalog/items?"
    params = url.split('?')[-1]
    if params == url: return base_api + "per_page=20&order=newest_first"
    if "order=" not in params: params += "&order=newest_first"
    return base_api + params

class VintedSniper:
    def __init__(self, target_url):
        self.api_url = convert_url(target_url)
        self.session = tls_client.Session(client_identifier="chrome_112")
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
        }
        self.seen_items = []

    def fetch_cookie(self):
        print("[*] Verbindung wird aufgebaut...")
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

    def send_to_discord(self, item):
        p = item.get('total_item_price')
        price_val = float(p.get('amount')) if isinstance(p, dict) else float(p)
        total_price = round(price_val + 0.70 + (price_val * 0.05) + 3.99, 2)
        item_id = item.get('id')
        item_url = item.get('url') or f"https://www.vinted.de/items/{item_id}"
        brand = item.get('brand_title') or "Keine Marke"
        status = self.get_clean_status(item)
        photos = item.get('photos', [])
        if not photos and item.get('photo'): photos = [item.get('photo')]
        image_urls = [img.get('url', '').replace("/medium/", "/full/") for img in photos if img.get('url')]
        main_img = image_urls[0] if image_urls else ""

        data = {
            "username": "Vinted Sniper PRO",
            "embeds": [{
                "title": f"🔥 {item.get('title')}",
                "url": item_url,
                "color": 0x09b1ba,
                "fields": [
                    {"name": "💶 Preis", "value": f"**{price_val:.2f} €**", "inline": True},
                    {"name": "🚚 Gesamt ca.", "value": f"**{total_price:.2f} €**", "inline": True},
                    {"name": "📏 Größe", "value": item.get('size_title', 'N/A'), "inline": True},
                    {"name": "🏷️ Marke", "value": brand, "inline": True},
                    {"name": "✨ Zustand", "value": status, "inline": True},
                    {"name": "⏰ Gefunden", "value": f"<t:{int(time.time())}:R>", "inline": True},
                    {"name": "⚡ Aktionen", "value": f"[🛒 Kaufen](https://www.vinted.de/transaction/buy/new?item_id={item_id}) | [💬 Nachricht]({item_url}#message)", "inline": False}
                ],
                "image": {"url": main_img},
                "footer": {"text": "Live Sniper • Alle Bilder & Details"},
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            }]
        }
        if len(image_urls) > 1:
            for extra in image_urls[1:4]:
                data["embeds"].append({"url": item_url, "image": {"url": extra}})

        try: self.session.post(WEBHOOK_URL, json=data)
        except Exception as e: print(f"Sende-Fehler: {e}")

    def run(self):
        self.fetch_cookie()
        print(f"🎯 Sniper aktiv! Scan alle 10 Sek.")
        while True:
            try:
                response = self.session.get(self.api_url, headers=self.headers)
                if response.status_code == 200:
                    items = response.json().get("items", [])
                    for item in items:
                        if item["id"] not in self.seen_items:
                            if len(self.seen_items) > 0:
                                self.send_to_discord(item)
                                print(f"✅ NEU: {item.get('title')}")
                            self.seen_items.append(item["id"])
                    if len(self.seen_items) > 500: self.seen_items = self.seen_items[-200:]
                elif response.status_code == 403:
                    print("⚠️ Blockiert! Warte 2 Min...")
                    time.sleep(120)
                time.sleep(10) # Wartezeit zwischen Scans
            except Exception as e:
                print(f"❌ Fehler: {e}")
                time.sleep(10)

if __name__ == "__main__":
    # Webserver in eigenem Thread starten
    t = Thread(target=run_web_server)
    t.start()
    
    # Bot starten
    bot = VintedSniper(BROWSER_URL)
    bot.run()
