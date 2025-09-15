import nodriver as uc
import asyncio
import os
import json
import re
import datetime
from bs4 import BeautifulSoup

# Speicherort für JSON
OUTPUT_DIR = "/Users/schnibba/spotify-dashboard/json_files/spotify/Gesamtstreams"

# Künstler-ID
artist_id = "3OOeP2opYuTEm0QIU4gQ6M"

# Dynamische Berechnung der Datumswerte:
today = datetime.date.today()
yesterday = today - datetime.timedelta(days=1)
date_format = "%Y-%m-%d"

from_date_7 = (yesterday - datetime.timedelta(days=6)).strftime(date_format)
to_date_7 = yesterday.strftime(date_format)
from_date_28 = (yesterday - datetime.timedelta(days=27)).strftime(date_format)
to_date_28 = yesterday.strftime(date_format)
from_date_12 = (yesterday - datetime.timedelta(days=364)).strftime(date_format)
to_date_12 = yesterday.strftime(date_format)

# Spotify Statistik-URLs
URLS = {
    "7 Tage Streams": f"https://artists.spotify.com/c/artist/{artist_id}/audience/stats?fromDate={from_date_7}&toDate={to_date_7}&metric=streams&country=&comparisonId=",
    "28 Tage Streams": f"https://artists.spotify.com/c/artist/{artist_id}/audience/stats?fromDate={from_date_28}&toDate={to_date_28}&metric=streams&country=&comparisonId=",
    "12 Monate Streams": f"https://artists.spotify.com/c/artist/{artist_id}/audience/stats?fromDate={from_date_12}&toDate={to_date_12}&metric=streams&country=&comparisonId="
}

# DRIVER: Initialisiere eine Nodriver-Session über Browserless
async def get_driver():
    ws_endpoint = os.getenv("BROWSERLESS_WS_URL")
    if not ws_endpoint:
        raise RuntimeError("BROWSERLESS_WS_URL environment variable is not set!")
    driver = await uc.start(
        remote=True,
        ws_endpoint=ws_endpoint,
        headless=True,
        no_sandbox=True
    )
    return driver

# Stats-Scraping einer einzelnen Zeitspanne
async def scrape_data(driver, url, timeframe):
    print(f"\n📊 Scrape {timeframe}: {url}")
    page = await driver.get(url)
    await asyncio.sleep(5)
    html_content = await page.evaluate("document.documentElement.outerHTML")
    soup = BeautifulSoup(html_content, "html.parser")
    total_value, daily_data = None, {}
    stats_button = soup.find("button", {"data-testid": "hero-stats-button-streams"})
    if stats_button:
        stats_text = stats_button.find("p", {"data-encore-id": "text"})
        if stats_text:
            try:
                total_value = int(stats_text.text.replace(",", ""))
            except Exception:
                total_value = None
    rect_elements = soup.find_all("rect", {"aria-label": True})
    for rect in rect_elements:
        aria_label = rect["aria-label"]
        match = re.match(r"([A-Za-z]+ \d{1,2}, \d{4}), ([\d,]+) Streams", aria_label)
        if match:
            date = match.group(1)
            count = int(match.group(2).replace(",", ""))
            daily_data[date] = count
    print(f"  → Gesamt: {total_value}, Tage: {len(daily_data)}")
    return {"timeframe": timeframe, "total": total_value, "daily": daily_data}

# Komplettvorgang für alle Zeiträume
async def scrape_spotify_data():
    print("🚀 Starte nodriver für Spotify Scraping (Browserless-Modus)...")
    driver = None
    try:
        driver = await get_driver()
        # Login-Phase
        first_url = next(iter(URLS.values()))
        print("\n🛑 Manuelles Login im Browserless-Browser nötig! Nach Login ggf. mit Enter im Terminal bestätigen…")
        await driver.get(first_url)
        await asyncio.sleep(30)
        scraped_results = {}
        for timeframe, url in URLS.items():
            result = await scrape_data(driver, url, timeframe)
            scraped_results[timeframe] = result
        # Daten speichern
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        output_file = os.path.join(OUTPUT_DIR, f"spotify_streams_{timestamp}.json")
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(scraped_results, f, ensure_ascii=False, indent=4)
        print(f"\n✅ Daten wurden gespeichert: {output_file}")
    except Exception as e:
        print(f"\n❌ Fehler während des Scraping-Prozesses: {e}")
    finally:
        if driver:
            try:
                await driver.stop()
            except Exception as e:
                print(f"\n⚠️ Fehler beim Schließen des Browsers: {e}")

# API-kompatibler Entry-Point für FastAPI: async main()
async def main():
    await scrape_spotify_data()

if __name__ == "__main__":
    asyncio.run(scrape_spotify_data())
