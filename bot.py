import discord
import aiohttp
import asyncio
import json
import os
from datetime import datetime

TOKEN = os.getenv("DISCORD_TOKEN")
SCAN_INTERVAL = 1.5  # Sekunden (unter 1s → 429 Risiko)

intents = discord.Intents.default()
client = discord.Client(intents=intents)

posted_cache: dict[str, set[str]] = {}

with open("channels.json", "r", encoding="utf-8") as f:
    CHANNELS = json.load(f)


async def fetch_articles(session: aiohttp.ClientSession, url: str):
    try:
        async with session.get(url, timeout=10) as r:
            if r.status != 200:
                print(f"⚠️ API Status {r.status} | {url}")
                return []

            return await r.json()

    except Exception as e:
        print(f"❌ Fetch Error {url}: {e}")
        return []


async def scanner(channel_id: str, api_url: str):
    await client.wait_until_ready()
    channel = client.get_channel(int(channel_id))

    if not channel:
        print(f"❌ Channel {channel_id} nicht gefunden")
        return

    posted_cache[channel_id] = set()
    print(f"🚀 Starte Scan: {channel_id}")

    async with aiohttp.ClientSession() as session:
        while not client.is_closed():
            articles = await fetch_articles(session, api_url)

            for item in articles:
                article_id = str(item.get("id"))
                title = item.get("title", "Neuer Artikel")
                url = item.get("url", "")

                if not article_id or article_id in posted_cache[channel_id]:
                    continue

                posted_cache[channel_id].add(article_id)

                msg = f"🆕 **{title}**\n{url}"
                await channel.send(msg)
                print(f"✅ Gesendet → {channel_id}: {title}")

            await asyncio.sleep(SCAN_INTERVAL)


@client.event
async def on_ready():
    print(f"🤖 Bot online als {client.user}")

    for ch_id, api in CHANNELS.items():
        asyncio.create_task(scanner(ch_id, api))

    print(f"🔥 {len(CHANNELS)} Scanner laufen")


client.run(TOKEN)
