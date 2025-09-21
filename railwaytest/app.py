from fastapi import FastAPI
from scrapers import scraper_öffentlich_spotify
import asyncio

app = FastAPI()

@app.post("/scrape/spotify")
async def scrape_spotify():
    await scraper_öffentlich_spotify.main()
    return {"status": "ok"}
