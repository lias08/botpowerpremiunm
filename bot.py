import discord
import requests
import asyncio
import json
import os
from datetime import datetime

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json"
}

CHECK_INTERVAL = 15  # Sekunden (schneller = mehr Risiko)
TIMEOUT = 10

intents = discord.Intents.default()
client = discord.Client(intents=intents)

seen_items = set()


def load_channels():
    with open("channels.json", "r", encoding="utf-8") as f:
        return json.load(f)["channels"]


async def fetch_items(vinted_channel_id):
    url = f"https://www.vinted.de/api/v2/catalog/items?catalog_ids={vinted_channel_id}&order=newest_first&per_page=5"
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        if r.status_code != 200:
            print(f"⚠️ {vinted_channel_id} Status {r.status_code}")
            return []

        return r.json().get("items", [])
    except Exception as e:
        print(f"❌ Fehler bei {vinted_channel_id}: {e}")
        return []


async def scanner_loop():
    await client.wait_until_ready()
    channels = load_channels()

    print(f"🔥 {len(channels)} Scanner laufen")

    while True:
        for cfg in channels:
            vinted_id = cfg["vinted_channel_id"]
            discord_id = int(cfg["discord_channel_id"])
            discord_channel = client.get_channel(discord_id)

            if not discord_channel:
                continue

            items = await fetch_items(vinted_id)

            for item in items:
                item_id = item["id"]
                if item_id in seen_items:
                    continue

                seen_items.add(item_id)

                title = item.get("title", "Kein Titel")
                price = item.get("price", "0")
                url = item.get("url", "")
                img = item.get("photo", {}).get("url", "")

                embed = discord.Embed(
                    title=title,
                    url=url,
                    description=f"💰 Preis: **{price}€**",
                    color=0x2ecc71,
                    timestamp=datetime.utcnow()
                )

                if img:
                    embed.set_thumbnail(url=img)

                await discord_channel.send(embed=embed)
                print(f"✅ Neuer Artikel gepostet: {item_id}")

            await asyncio.sleep(2)  # kleiner Abstand zwischen Channels

        await asyncio.sleep(CHECK_INTERVAL)


@client.event
async def on_ready():
    print(f"🤖 Bot online als {client.user}")
    client.loop.create_task(scanner_loop())


client.run(DISCORD_TOKEN)
