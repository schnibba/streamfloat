from fastapi import FastAPI
from scrapers import scraper1, scraper2
import asyncio

app = FastAPI()

@app.post("/run-scraper1")
async def run_scraper1():
    await scraper1.main()
    return {"status": "ok"}

@app.post("/run-scraper2")
async def run_scraper2():
    await scraper2.main()
    return {"status": "ok"}
