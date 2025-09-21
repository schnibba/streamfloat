import asyncio
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
import re
import json
import datetime

artist_id = "3OOeP2opYuTEm0QIU4gQ6M"
URL = f"https://open.spotify.com/artist/{artist_id}"

async def close_popups(page):
    print("[INFO] Prüfe auf Pop-ups...")

    # Cookie Consent akzeptieren
    try:
        consent_button = await page.query_selector('button[data-testid="cookie-policy-accept"]')
        if consent_button:
            print("[INFO] Cookie-Banner gefunden, akzeptiere...")
            await consent_button.click()
            await asyncio.sleep(1)
    except Exception as e:
        print(f"[WARN] Cookie Consent Fehler: {e}")

    # "Öffnen in App" Pop-up schließen
    try:
        app_popup_close_button = await page.query_selector('button[aria-label="Close"]')
        if app_popup_close_button:
            print("[INFO] App-Popup gefunden, schließe es...")
            await app_popup_close_button.click()
            await asyncio.sleep(1)
    except Exception as e:
        print(f"[WARN] App-Popup Fehler: {e}")

async def click_show_more(page):
    print("[INFO] Prüfe auf 'Mehr anzeigen' Button und klicke ihn, falls vorhanden...")
    try:
        await page.wait_for_selector('div.e-91000-text.encore-text-body-small-bold[data-encore-id="text"]', timeout=5000)
        await page.click('div.e-91000-text.encore-text-body-small-bold[data-encore-id="text"]')
        print("[INFO] 'Mehr anzeigen' Button wurde geklickt")
        await page.wait_for_timeout(3000)
    except Exception:
        print("[INFO] Kein 'Mehr anzeigen' Button gefunden oder Fehler beim Klicken")

async def scrape_spotify_artist_tracks():
    print(f"[INFO] Starte Scraping für Spotify Artist: {artist_id}")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        await page.goto(URL)

        await close_popups(page)

        print("[INFO] Warte auf komplettes Laden der Seite...")
        await page.wait_for_timeout(7000)

        await click_show_more(page)

        # Noch einmal Pop-ups schließen falls beim Nachladen neue auftauchen
        await close_popups(page)

        content = await page.content()
        soup = BeautifulSoup(content, "html.parser")

        data = {}

        # Monatliche Hörer auslesen
        monthly_listeners_span = soup.find("span", class_="VmDxGgs77HhmKczsLLBQ")
        if monthly_listeners_span:
            raw_text = monthly_listeners_span.text.strip()
            match = re.search(r"[\d,.]+", raw_text)
            if match:
                monthly_listeners = match.group(0).replace(".", "").replace(",", "")
                data["monthly_listeners"] = int(monthly_listeners)
                print(f"[INFO] Monatliche Hörer: {data['monthly_listeners']}")
            else:
                data["monthly_listeners"] = None
                print("[WARN] Monatliche Hörer Zahl nicht erkannt")
        else:
            data["monthly_listeners"] = None
            print("[WARN] Monatliche Hörer Element nicht gefunden")

        # Tracks und Plays auslesen
        track_names = soup.find_all("div", class_="e-91000-text encore-text-body-medium encore-internal-color-text-base eYJgrgW01l7dHKuMJidG standalone-ellipsis-one-line")
        play_counts = soup.find_all("div", class_="e-91000-text encore-text-body-small htbmhRXsxePzCR3HsX0V")

        print(f"[INFO] Gefundene Tracks: {len(track_names)}, Gefundene Playzahlen: {len(play_counts)}")

        tracks = []
        if len(track_names) == len(play_counts):
            for name_el, play_el in zip(track_names, play_counts):
                track_name = name_el.text.strip()
                play_count_raw = play_el.text.strip().replace(".", "").replace(",", "")
                try:
                    play_count = int(play_count_raw)
                except:
                    play_count = None
                tracks.append({"track_name": track_name, "play_count": play_count})
        else:
            print("[WARN] Unterschiedliche Anzahl Track-Namen und Playzahlen!")
            # Fallback: Nur Tracknamen ohne Plays hinzufügen
            for name_el in track_names:
                tracks.append({"track_name": name_el.text.strip(), "play_count": None})

        data["tracks"] = tracks

        await browser.close()

        timestamp = datetime.datetime.now().isoformat()
        print(f"[INFO] Scraping abgeschlossen: {timestamp}")

        return {"artist_id": artist_id, "scrape_time": timestamp, "data": data}

if __name__ == "__main__":
    scraped_data = asyncio.run(scrape_spotify_artist_tracks())
    print(json.dumps(scraped_data, indent=4, ensure_ascii=False))
