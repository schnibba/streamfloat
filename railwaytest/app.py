from fastapi import FastAPI
from scrapers import soundcloud_7Dstreams, spotify_7Dstreams
import asyncio

@app.post("/scrape/spotify")
async def scrape_spotify():
    await spotify_scraper.main()
    return {"status": "ok"}

@app.post("/scrape/soundcloud")
async def scrape_soundcloud():
    await soundcloud_scraper.main()
    return {"status": "ok"}
