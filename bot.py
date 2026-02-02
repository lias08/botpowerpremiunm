import discord
import aiohttp
import asyncio
import json
import os
from bs4 import BeautifulSoup

TOKEN = os.getenv("DISCORD_TOKEN")
SCAN_INTERVAL = 2.0

intents = discord.Intents.default()
client = discord.Client(intents=intents)

with open("channels.json", "r", encoding="utf-8") as f:
    CHANNELS = json.load(f)

seen_items = {}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
}


async def fetch_items(session, url):
    try:
        async with session.get(url, headers=HEADERS, timeout=15) as r:
            if r.status != 200:
                print(f"⚠️ Status {r.status}")
                return []

            html = await r.text()

        soup = BeautifulSoup(html, "html.parser")
        items = []

        for a in soup.select("a[href*='/items/']"):
            href = a.get("href")
            item_id = href.split("/")[-1].split("-")[0]

            title = a.get_text(strip=True)
            link = "https://www.vinted.de" + href

            items.append((item_id, title, link))

        return items

    except Exception as e:
        print(f"❌ Fetch Error: {e}")
        return []


async def scanner(channel_id, config):
    await client.wait_until_ready()
    channel = client.get_channel(int(channel_id))

    if not channel:
        print(f"❌ Channel {channel_id} nicht gefunden")
        return

    url = config["url"]
    seen_items[channel_id] = set()

    print(f"🚀 Starte Scan: {channel_id}")

    async with aiohttp.ClientSession() as session:
        while not client.is_closed():
            items = await fetch_items(session, url)

            for item_id, title, link in items:
                if item_id in seen_items[channel_id]:
                    continue

                seen_items[channel_id].add(item_id)
                await channel.send(f"🆕 **{title}**\n{link}")
                print(f"✅ Gesendet: {item_id}")

            await asyncio.sleep(SCAN_INTERVAL)


@client.event
async def on_ready():
    print(f"🤖 Bot online als {client.user}")
    print(f"🔥 {len(CHANNELS)} Scanner laufen")

    for cid, cfg in CHANNELS.items():
        asyncio.create_task(scanner(cid, cfg))


client.run(TOKEN)
