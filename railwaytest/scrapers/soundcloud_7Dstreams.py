import asyncio
import os
import re
import json
import urllib.parse
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
import nodriver as uc

def get_conversion_factor(soup):
    y_axis = soup.find("g", class_=lambda c: c and "MuiChartsAxis-directionY" in c)
    if not y_axis:
        return 0.5
    ticks = y_axis.find_all("g", class_=lambda c: c and "MuiChartsAxis-tickContainer" in c)
    if len(ticks) < 2:
        return 0.5
    positions, values = [], []
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
    x_axis = soup.find("g", class_=lambda c: c and "MuiChartsAxis-directionX" in c)
    if x_axis and x_axis.has_attr("transform"):
        transform_val = x_axis["transform"]
        import re
        m = re.search(r"translate\([^,]+,\s*([^)]+)\)", transform_val)
        if m:
            try:
                return float(m.group(1))
            except Exception:
                pass
    return 290.0

def extract_bar_height_from_transform(bar, chart_bottom):
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
    previous_height = await page.evaluate("document.body.scrollHeight")
    while True:
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await asyncio.sleep(1)
        new_height = await page.evaluate("document.body.scrollHeight")
        if new_height == previous_height:
            break
        previous_height = new_height

async def extract_streams(driver, url):
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

async def get_driver():
    ws_endpoint = os.getenv("BROWSERLESS_WS_URL")
    driver = await uc.start(
        remote=True,
        ws_endpoint=ws_endpoint,
        headless=True,
        no_sandbox=True
    )
    return driver


async def main():
    now = datetime.now()
    streams7_to = int(now.timestamp()) * 1000
    streams7_from = int((now - timedelta(days=7)).timestamp()) * 1000
    streams7_url = f"https://insights-ui.soundcloud.com/?timewindow=DAYS_7&from={streams7_from}&to={streams7_to}&resolution=DAY"

    streams30_to = int(now.timestamp()) * 1000
    streams30_from = int((now - timedelta(days=30)).timestamp()) * 1000
    streams30_url = f"https://insights-ui.soundcloud.com/?timewindow=DAYS_30&from={streams30_from}&to={streams30_to}&resolution=DAY"

    tooltip_to = int(now.timestamp()) * 1000
    tooltip_from = int((now - timedelta(days=365)).timestamp()) * 1000
    tooltip_url = f"https://insights-ui.soundcloud.com/?timewindow=MONTHS_12&from={tooltip_from}&to={tooltip_to}&resolution=MONTH"

    driver_streams7, driver_streams30, driver_tooltip = await asyncio.gather(get_driver(), get_driver(), get_driver())

    streams7_task = asyncio.create_task(extract_streams(driver_streams7, streams7_url))
    streams30_task = asyncio.create_task(extract_streams(driver_streams30, streams30_url))
    tooltip_task = asyncio.create_task(extract_tooltip_data(driver_tooltip, tooltip_url))

    streams7_result, streams30_result, tooltip_result = await asyncio.gather(streams7_task, streams30_task, tooltip_task)

    combined_results = {
        "timestamp": datetime.now().isoformat(),
        "streams7days": streams7_result,
        "streams30days": streams30_result,
        "tooltip12months": {
            "data": tooltip_result,
            "source": tooltip_url
        }
    }

    json_dir = "/Users/schnibba/spotify-dashboard/json_files/soundcloud/Gesamtstreams"
    os.makedirs(json_dir, exist_ok=True)
    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    combined_json_path = os.path.join(json_dir, f"SoundcloudStreams_{timestamp_str}.json")

    with open(combined_json_path, "w") as f:
        json.dump(combined_results, f, indent=2)

    print(f"Ergebnisse wurden in {combined_json_path} gespeichert.")

    try:
        await asyncio.gather(driver_streams7.close(), driver_streams30.close(), driver_tooltip.close())
    except Exception:
        pass

if __name__ == "__main__":
    asyncio.run(main())
