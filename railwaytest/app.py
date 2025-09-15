from fastapi import FastAPI
from scrapers import soundcloud_7Dstreams, spotify_7Dstreams
import asyncio

app = FastAPI()

@app.post("/run-scraper1")
async def run_scraper1():
    await soundcloud_7Dstreams.main()
    return {"status": "ok"}

@app.post("/run-scraper2")
async def run_scraper2():
    await spotify_7Dstreams.main()
    return {"status": "ok"}
