import asyncio
import os
import re
import json
import urllib.parse
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
import nodriver as uc

# ---------------------------
# Funktionen für Streams (SVG-basierte Berechnung)
# ---------------------------

def get_conversion_factor(soup):
    """
    Ermittelt den Umrechnungsfaktor basierend auf den Y-Achsen-Ticks.
    Beispiel: Wenn der Tick "0" bei y=290 und der Tick "120" bei y=50 liegt,
    dann beträgt der Faktor 120 / (290 - 50) = 0.5.
    """
    y_axis = soup.find("g", class_=lambda c: c and "MuiChartsAxis-directionY" in c)
    if not y_axis:
        return 0.5

    ticks = y_axis.find_all("g", class_=lambda c: c and "MuiChartsAxis-tickContainer" in c)
    if len(ticks) < 2:
        return 0.5

    positions = []
    values = []
    for tick in ticks:
        transform = tick.get("transform")
        if not transform:
            continue
        try:
            content = transform.replace("translate(", "").replace(")", "")
            parts = content.split(",") if "," in content else content.split()
            if len(parts) < 2:
                continue
            y_coord = float(parts[1].strip())
        except Exception:
            continue

        tick_text = tick.find("text")
        if tick_text:
            try:
                value = float(tick_text.get_text(strip=True))
                positions.append(y_coord)
                values.append(value)
            except Exception:
                continue

    if len(positions) < 2:
        return 0.5

    min_value = min(values)
    max_value = max(values)
    min_index = values.index(min_value)
    max_index = values.index(max_value)
    pixel_diff = abs(positions[min_index] - positions[max_index])
    value_diff = abs(max_value - min_value)
    if pixel_diff == 0:
        return 0.5
    return value_diff / pixel_diff

def get_chart_bottom(soup):
    """
    Extrahiert den y-Wert des unteren Rands des Diagramms aus der X-Achse.
    Beispiel: Aus dem transform-Attribut "translate(0, 290)" wird 290 ermittelt.
    """
    x_axis = soup.find("g", class_=lambda c: c and "MuiChartsAxis-directionX" in c)
    if x_axis and x_axis.has_attr("transform"):
        transform_val = x_axis["transform"]
        m = re.search(r"translate\([^,]+,\s*([^)]+)\)", transform_val)
        if m:
            try:
                return float(m.group(1))
            except Exception:
                pass
    return 290.0

def extract_bar_height_from_transform(bar, chart_bottom):
    """
    Parst den y-Wert aus dem transform-Attribut des Balkens. 
    Die tatsächliche Balkenhöhe entspricht dann: chart_bottom - y_position.
    Beispiel: translate3d(100.914286px, 166px, 0px) -> Höhe = 290 - 166 = 124.
    """
    style_str = bar.get("style", "")
    m = re.search(r"translate3d\([^,]+,\s*([0-9.]+)px", style_str)
    if m:
        try:
            bar_y = float(m.group(1))
            return chart_bottom - bar_y
        except Exception:
            return 0
    return 0

async def scroll_page(page):
    """Scrollt bis zum Ende der Seite, um lazy-loaded Inhalte zu laden."""
    previous_height = await page.evaluate("document.body.scrollHeight")
    while True:
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await asyncio.sleep(1)
        new_height = await page.evaluate("document.body.scrollHeight")
        if new_height == previous_height:
            break
        previous_height = new_height

async def extract_streams(driver, url):
    """
    Lädt die Insights-URL, parst den HTML-Content und berechnet
    die Streamzahlen basierend auf dem SVG-Chart.
    """
    page = await driver.get(url)
    await asyncio.sleep(10)
    await scroll_page(page)
    
    html_content = await page.evaluate("document.documentElement.outerHTML")
    soup = BeautifulSoup(html_content, "html.parser")
    
    conversion_factor = get_conversion_factor(soup)
    chart_bottom = get_chart_bottom(soup)
    
    total_streams = 0
    daily_data = {}
    stats_svg = soup.find("svg", class_=lambda c: c and "mui-1ht4czs" in c)
    if stats_svg:
        try:
            bars = stats_svg.select('g[clip-path] rect.MuiBarElement-root')
            provided_labels = soup.find_all("text", class_=lambda c: c and "MuiChartsAxis-tickLabel" in c)
            if len(provided_labels) != len(bars):
                parsed = urllib.parse.urlparse(url)
                qparams = urllib.parse.parse_qs(parsed.query)
                try:
                    from_ts = int(qparams.get('from', [0])[0])
                    from_date = datetime.fromtimestamp(from_ts / 1000)
                except Exception:
                    from_date = datetime.now() - timedelta(days=len(bars) - 1)
                generated_labels = [(from_date + timedelta(days=i)).strftime("%b %d") for i in range(len(bars))]
            else:
                generated_labels = [label.get_text(strip=True) for label in provided_labels]
            
            for bar, label in zip(bars, generated_labels):
                try:
                    day = label
                    bar_height = extract_bar_height_from_transform(bar, chart_bottom)
                    daily_streams = int(round(bar_height * conversion_factor))
                    total_streams += daily_streams
                    daily_data[day] = daily_streams
                except Exception:
                    pass
        except Exception:
            pass
    
    output_data = {
        "timestamp": datetime.now().isoformat(),
        "total": total_streams,
        "daily": daily_data,
        "source": url
    }
    
    return output_data

# ---------------------------
# Funktionen für Tooltip-Extraktion (12 Monate)
# ---------------------------

async def extract_tooltip_data(driver, url):
    """
    Lädt die Insights-URL, ermittelt die Balken und extrahiert beim Hover den Text
    aus dem span-Element mit der Klasse "mui-141fd84" innerhalb des Tooltip-Divs.
    Zusätzlich wird der Monatsnamen aus dem div-Element extrahiert.
    """
    page = await driver.get(url)
    await asyncio.sleep(10)
    
    bars = await page.query_selector_all("g[clip-path] rect.MuiBarElement-root")
    tooltip_data = {}
    
    for i, bar in enumerate(bars):
        await bar.mouse_move()
        await asyncio.sleep(2)
        
        try:
            # Extrahiere den Spielzähler
            tooltip_span = await page.query_selector('div[role="tooltip"] span.mui-141fd84')
            plays_text = tooltip_span.text if tooltip_span else None
            
            # Extrahiere den Monatsnamen
            month_div = await page.query_selector('div[role="tooltip"] div.mui-8euwhr > div:first-child')
            month_text = month_div.text if month_div else None
            
            tooltip_data[f"Bar_{i+1}"] = {
                "plays": plays_text,
                "month": month_text
            }
        except Exception:
            tooltip_data[f"Bar_{i+1}"] = {
                "plays": None,
                "month": None
            }

    return tooltip_data

# ---------------------------
# Gemeinsame Funktion zum Erstellen eines Drivers (inkl. Login)
# ---------------------------

async def get_driver():
    driver = await uc.start(no_sandbox=True)
    if os.path.exists(".session.dat"):
        await driver.cookies.load()
    else:
        signin_page = await driver.get("https://soundcloud.com/signin")
        await signin_page.reload()
        await asyncio.sleep(5)
        await asyncio.to_thread(input, "Drücke Enter, wenn du eingeloggt bist...")
        await driver.cookies.save()
    return driver

# ---------------------------
# Hauptfunktion: Paralleles Ausführen der drei Scrapes
# ---------------------------

async def main():
    now = datetime.now()
    
    # Streams für 7 Tage (Zeitraum: letzte 7 Tage, Resolution: DAY)
    streams7_to = int(now.timestamp()) * 1000
    streams7_from = int((now - timedelta(days=7)).timestamp()) * 1000
    streams7_url = f"https://insights-ui.soundcloud.com/?timewindow=DAYS_7&from={streams7_from}&to={streams7_to}&resolution=DAY"
    
    # Streams für 30 Tage (Zeitraum: letzte 30 Tage, Resolution: DAY)
    streams30_to = int(now.timestamp()) * 1000
    streams30_from = int((now - timedelta(days=30)).timestamp()) * 1000
    streams30_url = f"https://insights-ui.soundcloud.com/?timewindow=DAYS_30&from={streams30_from}&to={streams30_to}&resolution=DAY"
    
    # Tooltip-Daten für 12 Monate (Zeitraum: letzte 12 Monate, Resolution: MONTH)
    tooltip_to = int(now.timestamp()) * 1000
    tooltip_from = int((now - timedelta(days=365)).timestamp()) * 1000
    tooltip_url = f"https://insights-ui.soundcloud.com/?timewindow=MONTHS_12&from={tooltip_from}&to={tooltip_to}&resolution=MONTH"
    
    # Starte 3 separate Browser-Instanzen parallel
    driver_streams7, driver_streams30, driver_tooltip = await asyncio.gather(get_driver(), get_driver(), get_driver())
    
    # Erstelle Tasks für die drei Scrapes
    streams7_task = asyncio.create_task(extract_streams(driver_streams7, streams7_url))
    streams30_task = asyncio.create_task(extract_streams(driver_streams30, streams30_url))
    tooltip_task  = asyncio.create_task(extract_tooltip_data(driver_tooltip, tooltip_url))
    
    # Warte auf alle Tasks
    streams7_result, streams30_result, tooltip_result = await asyncio.gather(streams7_task, streams30_task, tooltip_task)
    
    # Kombinierte Daten für eine einzige JSON-Datei
    combined_results = {
        "timestamp": datetime.now().isoformat(),
        "streams7days": streams7_result,
        "streams30days": streams30_result,
        "tooltip12months": {
            "data": tooltip_result,
            "source": tooltip_url
        }
    }
    
    # Speichern der Ergebnisse
    json_dir = "/Users/schnibba/spotify-dashboard/json_files/soundcloud/Gesamtstreams"
    os.makedirs(json_dir, exist_ok=True)
    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Kombinierte JSON-Datei speichern
    combined_json_path = os.path.join(json_dir, f"SoundcloudStreams_{timestamp_str}.json")
    
    with open(combined_json_path, "w") as f:
        json.dump(combined_results, f, indent=2)
    print(f"Ergebnisse wurden in {combined_json_path} gespeichert.")
    
    # Browser beenden (mit korrekter Methode)
    try:
        await asyncio.gather(driver_streams7.close(), driver_streams30.close(), driver_tooltip.close())
    except Exception:
        pass

if __name__ == "__main__":
    asyncio.run(main())