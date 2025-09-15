import nodriver as uc
import asyncio
import os
import json
import re
import datetime
from bs4 import BeautifulSoup

# 📂 Speicherort für JSON
OUTPUT_DIR = "/Users/schnibba/spotify-dashboard/json_files/spotify/Gesamtstreams"

# Künstler-ID
artist_id = "3OOeP2opYuTEm0QIU4gQ6M"

# Dynamische Berechnung der Datumswerte:
# Wir setzen das "toDate" auf gestern (einen Tag vor dem Start)
today = datetime.date.today()
yesterday = today - datetime.timedelta(days=1)
date_format = "%Y-%m-%d"

# Für 7 Tage (inklusive gestern = 7 Tage): 6 Tage zurück
from_date_7 = (yesterday - datetime.timedelta(days=6)).strftime(date_format)
to_date_7   = yesterday.strftime(date_format)

# Für 28 Tage: 27 Tage zurück
from_date_28 = (yesterday - datetime.timedelta(days=27)).strftime(date_format)
to_date_28   = yesterday.strftime(date_format)

# Für 12 Monate (angenommen 365 Tage, inkl. gestern): 364 Tage zurück
from_date_12 = (yesterday - datetime.timedelta(days=364)).strftime(date_format)
to_date_12   = yesterday.strftime(date_format)

# 🎯 Spotify Statistik-Seiten für Streams (direkte Links) mit dynamischen Daten
URLS = {
    "7 Tage Streams": f"https://artists.spotify.com/c/artist/{artist_id}/audience/stats?fromDate={from_date_7}&toDate={to_date_7}&metric=streams&country=&comparisonId=",
    "28 Tage Streams": f"https://artists.spotify.com/c/artist/{artist_id}/audience/stats?fromDate={from_date_28}&toDate={to_date_28}&metric=streams&country=&comparisonId=",
    "12 Monate Streams": f"https://artists.spotify.com/c/artist/{artist_id}/audience/stats?fromDate={from_date_12}&toDate={to_date_12}&metric=streams&country=&comparisonId="
}

async def scrape_data(driver, url, timeframe):
    """Scrape tägliche Daten aus Spotify for Artists."""
    print(f"\n📊 Scrape {timeframe}: {url}")
    page = await driver.get(url)
    await asyncio.sleep(5)

    # **HTML-Inhalt abrufen**
    html_content = await page.evaluate("document.documentElement.outerHTML")
    soup = BeautifulSoup(html_content, "html.parser")

    # **Gesamtstreams extrahieren**
    total_value = None
    stats_button = soup.find("button", {"data-testid": "hero-stats-button-streams"})
    if stats_button:
        stats_text = stats_button.find("p", {"data-encore-id": "text"})
        if stats_text:
            total_value = int(stats_text.text.replace(",", ""))

    print(f"🎧 Gesamtzahl für {timeframe}: {total_value}")

    # **Tägliche Daten extrahieren**
    daily_data = {}
    rect_elements = soup.find_all("rect", {"aria-label": True})
    for rect in rect_elements:
        aria_label = rect["aria-label"]
        match = re.match(r"([A-Za-z]+ \d{1,2}, \d{4}), ([\d,]+) Streams", aria_label)
        if match:
            date = match.group(1)
            count = int(match.group(2).replace(",", ""))
            daily_data[date] = count

    print(f"📅 Tägliche Daten ({timeframe}): {daily_data}")
    return {"timeframe": timeframe, "total": total_value, "daily": daily_data}

async def scrape_spotify_data():
    """Startet den Scraping-Prozess nach manuellem Login."""
    print("🚀 Starte nodriver für Spotify Scraping...")

    driver = None  # Initialisieren

    try:
        driver = await uc.start(no_sandbox=True)  # Browser starten

        # **Manuelles Login**
        first_url = next(iter(URLS.values()))
        print("\n🛑 Bitte logge dich manuell ein. Nach dem Login drücke Enter im Terminal.")
        await driver.get(first_url)
        await asyncio.sleep(30)

        # **Daten für alle Zeiträume scrapen**
        scraped_results = {}
        for timeframe, url in URLS.items():
            result = await scrape_data(driver, url, timeframe)
            scraped_results[timeframe] = result

        # **Daten speichern**
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        output_file = os.path.join(OUTPUT_DIR, f"spotify_streams_{timestamp}.json")
        os.makedirs(OUTPUT_DIR, exist_ok=True)

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(scraped_results, f, ensure_ascii=False, indent=4)

        print(f"\n✅ Daten wurden gespeichert: {output_file}")

    except Exception as e:
        print(f"\n❌ Fehler während des Scraping-Prozesses: {e}")

    finally:
        # **Browser sauber beenden**
        if driver:
            try:
                await driver.stop()
            except Exception as e:
                print(f"\n⚠️ Fehler beim Schließen des Browsers: {e}")

# **Skript ausführen**
if __name__ == "__main__":
    asyncio.run(scrape_spotify_data())
