from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import asyncio

from scrapers import scraper_öffentlich_spotify  # dein Skript

app = FastAPI()

class ArtistRequest(BaseModel):
    artist_id: str

@app.post("/scrape/spotify")
async def scrape_spotify(data: ArtistRequest):
    artist_id = data.artist_id
    try:
        scraped_data = await scraper_öffentlich_spotify.scrape_spotify_artist_tracks(artist_id)
        return {"success": True, "data": scraped_data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
