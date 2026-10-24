#!/usr/bin/env python3
"""
Daily Heat Index poster - cloud edition.

Rebuilds the Fibertech "Daily Heat Index" poster without any on-site machine:

  1. Pulls tomorrow's hourly forecast for Elberfeld, IN from the National
     Weather Service (NWS Paducah grid PAH 170,106).
  2. Computes the NWS heat index for every hour from 8 AM to 8 PM and takes
     the peak. Zone: White (90 and below), Red (91-114), Black (115+).
  3. Renders the poster PNG (same layout as the Word-based poster), writes a
     metadata JSON (same fields the Power Automate flow already reads), and
     optionally posts the Teams adaptive card through a Workflows webhook.

Usage
  python scripts/heat_poster.py --out heat-posters            # tomorrow
  python scripts/heat_poster.py --out heat-posters --date 2026-10-27
  python scripts/heat_poster.py --post-json heat-posters/10.27.26.json

Environment
  NWS_USER_AGENT          identifies us to api.weather.gov (NWS asks for one)
  TEAMS_HEAT_WEBHOOK_URL  Teams Workflows "webhook request received" URL

Offline testing
  --hourly-json / --daily-json load saved api.weather.gov responses instead
  of calling the network.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import os
import sys
import time
from pathlib import Path
from zoneinfo import ZoneInfo

from PIL import Image, ImageDraw, ImageFont

# --------------------------------------------------------------------------- #
# Site configuration
# --------------------------------------------------------------------------- #
TZ = ZoneInfo("America/Chicago")
LOCATION = "Elberfeld, IN"
NWS_OFFICE, GRID_X, GRID_Y = "PAH", 170, 106
HOURLY_URL = f"https://api.weather.gov/gridpoints/{NWS_OFFICE}/{GRID_X},{GRID_Y}/forecast/hourly"
DAILY_URL = f"https://api.weather.gov/gridpoints/{NWS_OFFICE}/{GRID_X},{GRID_Y}/forecast"
WINDOW_START_HOUR, WINDOW_END_HOUR = 8, 20          # 8 AM .. 8 PM inclusive
PEAK_WINDOW_TOLERANCE_F = 1.0                       # hours within 1 F of the peak form the "hottest" window
RAW_BASE_URL = "https://raw.githubusercontent.com/Bholder78/sds/main/heat-posters/"

REPO_ROOT = Path(__file__).resolve().parent.parent
ASSETS = REPO_ROOT / "assets"
FONT_DIR = ASSETS / "fonts"
LOGO_PATH = ASSETS / "fibertech_logo.png"

ZONE_ACTION = {
    "White": "Normal operations.",
    "Red": ("Extra 10-minute break between the start of shift and the 1st break. "
            "Extra 10-minute break between lunch and the 2nd break. "
            "An added 5 minutes on the 1st and 2nd breaks."),
    "Black": ("Extra 10-minute break between the start of shift and the 1st break. "
              "Extra 10-minute break between lunch and the 2nd break. "
              "An added 5 minutes on the 1st and 2nd breaks. "
              "Management will monitor work and employees. "
              "Rotating tasks/duties may be implemented. "
              "(Electrolytes, PPE, cancellation of certain tasks.)"),
}

# --------------------------------------------------------------------------- #
# Heat index math (NWS / Rothfusz, exactly as the NWS calculator applies it)
# --------------------------------------------------------------------------- #
def heat_index(temp_f: float, rh: float) -> float:
    t, r = float(temp_f), float(rh)
    simple = 0.5 * (t + 61.0 + (t - 68.0) * 1.2 + r * 0.094)
    if (simple + t) / 2.0 < 80.0:
        return simple
    hi = (-42.379 + 2.04901523 * t + 10.14333127 * r - 0.22475541 * t * r
          - 0.00683783 * t * t - 0.05481717 * r * r + 0.00122874 * t * t * r
          + 0.00085282 * t * r * r - 0.00000199 * t * t * r * r)
    if r < 13 and 80 <= t <= 112:
        hi -= ((13 - r) / 4.0) * math.sqrt((17 - abs(t - 95)) / 17.0)
    elif r > 85 and 80 <= t <= 87:
        hi += ((r - 85) / 10.0) * ((87 - t) / 5.0)
    return hi


def zone_for(hi: float) -> str:
    v = round(hi, 1)
    if v >= 115.0:
        return "Black"
    if v >= 91.0:
        return "Red"
    return "White"


def hour_label(hour: int) -> str:
    h12 = hour % 12 or 12
    return f"{h12} {'AM' if hour < 12 else 'PM'}"


def short_date(d: dt.date) -> str:
    return f"{d.month}.{d.day}.{d.strftime('%y')}"       # 10.23.26  (file names)


def slash_date(d: dt.date) -> str:
    return f"{d.month}/{d.day}/{d.strftime('%y')}"       # 10/23/26  (card title)


# --------------------------------------------------------------------------- #
# NWS fetch + parse
# --------------------------------------------------------------------------- #
def fetch_json(url: str, retries: int = 4) -> dict:
    import requests  # imported here so offline tests do not need it
    headers = {
        "User-Agent": os.environ.get("NWS_USER_AGENT", "fibertech-heat-poster (github.com/Bholder78/sds)"),
        "Accept": "application/geo+json",
    }
    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            r = requests.get(url, headers=headers, timeout=40)
            if r.status_code == 429 or r.status_code >= 500:
                raise RuntimeError(f"NWS {r.status_code}: {r.text[:200]}")   # transient, retry
            if r.status_code >= 400:
                raise SystemExit(f"NWS {r.status_code} for {url}: {r.text[:200]}")  # permanent, stop now
            return r.json()
        except SystemExit:
            raise
        except Exception as e:  # noqa: BLE001 - timeouts, connection errors, 5xx
            last_err = e
            if attempt < retries - 1:
                wait = 15 * (attempt + 1)
                print(f"NWS fetch failed ({e}); retrying in {wait}s", file=sys.stderr)
                time.sleep(wait)
    raise SystemExit(f"NWS fetch failed after {retries} attempts: {last_err}")


def forecast_age_hours(data: dict) -> float | None:
    """Hours since NWS generated this forecast, or None if the response does not say."""
    p = (data or {}).get("properties", {})
    stamp = p.get("updateTime") or p.get("generatedAt") or p.get("updated")
    if not stamp:
        return None
    try:
        issued = dt.datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except ValueError:
        return None
    return (dt.datetime.now(dt.timezone.utc) - issued).total_seconds() / 3600.0


def parse_hourly(data: dict) -> list[dict]:
    hours = []
    for p in data["properties"]["periods"]:
        start = dt.datetime.fromisoformat(p["startTime"]).astimezone(TZ)
        temp = float(p["temperature"])
        if p.get("temperatureUnit", "F") == "C":
            temp = temp * 9 / 5 + 32
        rh = (p.get("relativeHumidity") or {}).get("value")
        hours.append({
            "time": start,
            "temp": temp,
            "rh": None if rh is None else float(rh),
            "short": p.get("shortForecast", ""),
        })
    return hours


def parse_daily(data: dict) -> dict[dt.date, dict]:
    """Daytime period per date -> {'high_f', 'short'}."""
    out: dict[dt.date, dict] = {}
    for p in data.get("properties", {}).get("periods", []):
        if not p.get("isDaytime"):
            continue
        d = dt.datetime.fromisoformat(p["startTime"]).astimezone(TZ).date()
        temp = float(p["temperature"])
        if p.get("temperatureUnit", "F") == "C":
            temp = temp * 9 / 5 + 32
        out[d] = {"high_f": int(round(temp)), "short": p.get("shortForecast", "")}
    return out


# --------------------------------------------------------------------------- #
# Day summary
# --------------------------------------------------------------------------- #
def summarize_day(hours: list[dict], date: dt.date, daily: dict[dt.date, dict] | None = None) -> dict | None:
    window = [h for h in hours
              if h["time"].date() == date
              and WINDOW_START_HOUR <= h["time"].hour <= WINDOW_END_HOUR
              and h["rh"] is not None]
    if not window:
        return None
    # Hours the forecast did not give us (not in the response, or humidity missing).
    # The caller decides whether a partial window is acceptable; it is never silent.
    missing = sorted(set(range(WINDOW_START_HOUR, WINDOW_END_HOUR + 1)) - {h["time"].hour for h in window})
    for h in window:
        h["hi"] = heat_index(h["temp"], h["rh"])
    peak = max(window, key=lambda h: h["hi"])           # first hour wins a tie
    peak_hi = round(peak["hi"], 1)

    near = {h["time"].hour for h in window if h["hi"] >= peak["hi"] - PEAK_WINDOW_TOLERANCE_F}
    lo = hi_hour = peak["time"].hour
    while lo - 1 in near:
        lo -= 1
    while hi_hour + 1 in near:
        hi_hour += 1
    if lo == hi_hour:
        hottest = f"around {hour_label(lo)}"
    else:
        hottest = f"{hour_label(lo)} – {hour_label(hi_hour)}"

    all_day = [h for h in hours if h["time"].date() == date]
    day = (daily or {}).get(date) or {}
    high_f = day.get("high_f", int(round(max(h["temp"] for h in all_day))))
    short = day.get("short") or peak["short"]

    return {
        "date": date,
        "heat_index": peak_hi,
        "zone": zone_for(peak["hi"]),
        "peak_time": peak["time"],
        "peak_temp_f": int(round(peak["temp"])),
        "peak_humidity": int(round(peak["rh"])),
        "hottest": hottest,
        "forecast_high_f": high_f,
        "short_forecast": short,
        "missing_hours": [hour_label(h) for h in missing],
        # Every hour that went into the decision, kept for the record.
        "hours": [{"time": h["time"].strftime("%I:%M %p").lstrip("0"), "temp_f": int(round(h["temp"])),
                   "humidity": int(round(h["rh"])), "heat_index": round(h["hi"], 1),
                   "zone": zone_for(h["hi"]), "forecast": h["short"]} for h in window],
    }


def archive_folder(d: dt.date) -> str:
    """Year/month folder the laptop job uses on SharePoint, e.g. '2026/10. October'."""
    return f"{d.year}/{d.month}. {d.strftime('%B')}"


def nws_provenance(hourly: dict, daily: dict) -> dict:
    """When NWS generated the forecasts we used (so a record can be traced back)."""
    def pick(data: dict) -> dict:
        p = (data or {}).get("properties", {})
        return {k: p[k] for k in ("generatedAt", "updateTime", "updated") if k in p}
    return {"hourly_forecast": pick(hourly), "daily_forecast": pick(daily),
            "grid": f"{NWS_OFFICE}/{GRID_X},{GRID_Y}", "hourly_url": HOURLY_URL, "daily_url": DAILY_URL}


def rest_of_week_dates(target: dt.date) -> list[dt.date]:
    out, d = [], target + dt.timedelta(days=1)
    while d.weekday() <= 4:                              # through Friday
        out.append(d)
        d += dt.timedelta(days=1)
    return out


# --------------------------------------------------------------------------- #
# Teams adaptive card (same shape the Power Automate flow posts today)
# --------------------------------------------------------------------------- #
def build_card(summary: dict, week: list[dict], poster_url: str) -> dict:
    body: list[dict] = [
        {"type": "TextBlock", "size": "Large", "weight": "Bolder", "wrap": True,
         "text": f"Heat Index {slash_date(summary['date'])}"},
        {"type": "FactSet", "facts": [
            {"title": "Heat Index", "value": f"{summary['heat_index']:.1f}"},
            {"title": "Zone", "value": summary["zone"]},
            {"title": "Hottest part of day", "value": summary["hottest"]},
        ]},
    ]
    if week:
        cols = []
        for w in week:
            cols.append({"type": "Column", "width": "stretch", "items": [
                {"type": "TextBlock", "text": f"{w['day']} {w['date'].month}/{w['date'].day}",
                 "size": "Small", "weight": "Bolder", "horizontalAlignment": "Center", "wrap": True},
                {"type": "TextBlock", "text": f"{w['heat_index']:.1f}", "size": "ExtraLarge",
                 "weight": "Bolder", "color": "Default", "horizontalAlignment": "Center", "spacing": "None"},
                {"type": "TextBlock", "text": w["zone"], "size": "Small", "color": "Default",
                 "horizontalAlignment": "Center", "spacing": "None"},
            ]})
        body.append({"type": "Container", "spacing": "Medium", "separator": True, "items": [
            {"type": "TextBlock", "text": "Rest of the week", "weight": "Bolder", "wrap": True},
            {"type": "TextBlock", "wrap": True, "size": "Small", "isSubtle": True, "spacing": "None",
             "text": "Peak heat index 8 AM to 8 PM from the NWS forecast. Each day's flag is still set the day before."},
            {"type": "ColumnSet", "columns": cols},
        ]})
    body.append({"type": "Image", "url": poster_url, "size": "Stretch",
                 "altText": f"Daily Heat Index poster {slash_date(summary['date'])}",
                 "msTeams": {"allowExpand": True}})
    return {"type": "AdaptiveCard", "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            "version": "1.4", "body": body}


def webhook_payload(meta: dict) -> dict:
    """Body sent to the Teams Workflows webhook.

    'metadata' is the complete day record, card included, so the flow can write it
    to SharePoint as '<M.D.YY> metadata.json' - the same file the laptop job drops,
    which is what the existing "post the card" flow is watching for. 'attachments'
    is only used if a flow chooses to post the card itself instead.
    """
    record = dict(meta)
    return {
        "type": "message",
        "attachments": [{"contentType": "application/vnd.microsoft.card.adaptive",
                         "contentUrl": None, "content": meta["card"]}],
        "date": meta["date"],
        "date_short": meta["date_short"],
        "heat_index": meta["heat_index"],
        "zone": meta["zone"],
        "poster_name": meta["poster"],
        "poster_url": meta["poster_url"],
        "metadata_name": meta["poster"].replace(".png", " metadata.json"),
        "archive_folder": meta["archive_folder"],
        "metadata": record,
    }


def post_card(meta: dict, webhook_url: str, retries: int = 3) -> None:
    import requests
    payload = webhook_payload(meta)
    last = None
    for attempt in range(retries):
        try:
            r = requests.post(webhook_url, json=payload, timeout=30)
            if r.status_code == 429 or r.status_code >= 500:
                raise RuntimeError(f"webhook {r.status_code}: {r.text[:200]}")
            if r.status_code >= 400:
                raise SystemExit(f"Teams flow rejected the request ({r.status_code}): {r.text[:200]}")
            print(f"Sent to the Teams flow ({r.status_code}).")
            return
        except SystemExit:
            raise
        except Exception as e:  # noqa: BLE001
            last = e
            if attempt < retries - 1:
                time.sleep(10 * (attempt + 1))
    raise SystemExit(f"Teams post failed after {retries} attempts: {last}")


# --------------------------------------------------------------------------- #
# Poster rendering (1210 x 935, matches the Word poster)
# --------------------------------------------------------------------------- #
W, H = 1210, 935
BLUE = (47, 85, 151)
RED = (255, 0, 0)
DARK_RED = (192, 0, 0)
GOLD = (138, 109, 26)
GOLD_BORDER = (184, 150, 46)
HEADER_FILL = (189, 215, 238)
INK = (0, 0, 0)
GRID = (60, 60, 60)


def _font(style: str, size: int) -> ImageFont.FreeTypeFont:
    names = {"r": "Carlito-Regular.ttf", "b": "Carlito-Bold.ttf",
             "i": "Carlito-Italic.ttf", "bi": "Carlito-BoldItalic.ttf"}
    path = FONT_DIR / names[style]
    if path.exists():
        return ImageFont.truetype(str(path), size)
    fallback = {"r": "DejaVuSans.ttf", "b": "DejaVuSans-Bold.ttf",
                "i": "DejaVuSans-Oblique.ttf", "bi": "DejaVuSans-BoldOblique.ttf"}[style]
    return ImageFont.truetype(fallback, size)


def _text_w(draw: ImageDraw.ImageDraw, text: str, font) -> float:
    return draw.textlength(text, font=font)


def draw_rich(draw, x, y, max_w, segments, line_h, start_x=None):
    """Flow [(text, font, color), ...] into lines of width max_w. Returns y after last line."""
    cx = start_x if start_x is not None else x
    space_cache: dict[int, float] = {}
    for text, font, color in segments:
        words = text.split(" ")
        for i, word in enumerate(words):
            if word == "":
                continue
            sp = space_cache.setdefault(id(font), _text_w(draw, " ", font))
            ww = _text_w(draw, word, font)
            if cx > x and cx + ww > x + max_w:
                cx, y = x, y + line_h
            draw.text((cx, y), word, font=font, fill=color)
            cx += ww + sp
    return y + line_h


def _wrap_lines(draw, text: str, font, max_w: float) -> list[str]:
    lines, cur = [], ""
    for word in text.split():
        trial = f"{cur} {word}".strip()
        if cur and _text_w(draw, trial, font) > max_w:
            lines.append(cur)
            cur = word
        else:
            cur = trial
    if cur:
        lines.append(cur)
    return lines


def _centered(draw, box, text, font, fill):
    x0, y0, x1, y1 = box
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(((x0 + x1 - tw) / 2 - bbox[0], (y0 + y1 - th) / 2 - bbox[1]), text, font=font, fill=fill)


def render_poster(summary: dict, out_path: Path) -> None:
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    zone = summary["zone"]
    hi_txt = f"{summary['heat_index']:.1f}"

    # Logo + title
    if LOGO_PATH.exists():
        logo = Image.open(LOGO_PATH).convert("RGBA")
        scale = 58 / logo.height
        logo = logo.resize((int(logo.width * scale), 58), Image.LANCZOS)
        img.paste(logo, (116, 62), logo)
    d.text((222, 58), "Daily Heat Index", font=_font("r", 78), fill=INK)

    # Big number box (white / red / black)
    box = (783, 40, 1088, 170)
    fill = {"White": "white", "Red": RED, "Black": INK}[zone]
    d.rectangle(box, fill=fill, outline=INK, width=2)
    _centered(d, box, hi_txt, _font("r", 118), "white" if zone == "Black" else INK)

    d.text((122, 150), f"Date: {summary['date'].strftime('%m/%d/%Y')}", font=_font("r", 40), fill=INK)
    d.text((122, 203), "Hydration and Rest Guidelines", font=_font("bi", 24), fill=BLUE)
    hp = f"Hottest part of day: {summary['hottest']}"
    f_hp = _font("b", 19)
    d.text((995 - _text_w(d, hp, f_hp), 206), hp, font=f_hp, fill=INK)

    # Guideline table
    cols = [120, 340, 652, 995]
    rows = [250, 286, 322, 358, 395]
    d.rectangle((cols[0], rows[0], cols[-1], rows[1]), fill=HEADER_FILL)
    d.rectangle((cols[0], rows[2], cols[-1], rows[3]), fill=RED)
    d.rectangle((cols[0], rows[3], cols[-1], rows[4]), fill=INK)
    table = [
        (["Heat Index", "Zone", "Water (qt/hr)"], _font("b", 21), INK),
        (["90 & below", "White", "¾"], _font("r", 21), INK),
        (["91 – 114", "Red", "1"], _font("r", 21), INK),
        (["115 +", "Black", "1"], _font("r", 21), "white"),
    ]
    for ri, (cells, font, color) in enumerate(table):
        for ci, cell in enumerate(cells):
            _centered(d, (cols[ci], rows[ri], cols[ci + 1], rows[ri + 1]), cell, font, color)
    for y in rows:
        d.line((cols[0], y, cols[-1], y), fill=GRID, width=1)
    for x in cols:
        d.line((x, rows[0], x, rows[-1]), fill=GRID, width=1)
    d.text((122, 400), "Figure 2.", font=_font("i", 14), fill=INK)

    # Legend
    f_lab, f_txt, lh = _font("bi", 18), _font("i", 18), 24
    d.rectangle((123, 429, 135, 441), outline=INK, width=1)
    draw_rich(d, 122, 424, 430, [("White (90 & below)", f_lab, INK), (" Normal operations.", f_txt, INK)], lh, start_x=143)
    d.rectangle((123, 466, 135, 478), fill=RED)
    draw_rich(d, 122, 461, 432, [("Red (91 - 114)", f_lab, INK), (" " + ZONE_ACTION["Red"], f_txt, INK)], lh, start_x=143)
    d.rectangle((584, 430, 596, 442), fill=INK)
    draw_rich(d, 583, 425, 420, [("Black (115+)", f_lab, INK), (" " + ZONE_ACTION["Black"], f_txt, INK)], lh, start_x=604)

    # Today's heat response. The box keeps its normal place (660-742) for one or two
    # lines of text; a Black day needs three, so the box grows upward into the white
    # space above it and keeps clear of the two boxes at y=755.
    f_h, f_body, body_lh = _font("b", 17), _font("r", 15), 18
    lines = _wrap_lines(d, ZONE_ACTION[zone], f_body, 850)
    box_h = max(82, 32 + len(lines) * body_lh + 10)
    top = min(660, 746 - box_h)
    d.rectangle((122, top, 995, top + box_h), outline=(34, 34, 34), width=2)
    head = "TODAY'S HEAT RESPONSE — "
    d.text((132, top + 7), head, font=f_h, fill=INK)
    sx = 132 + _text_w(d, head, f_h)
    sq = (sx, top + 11, sx + 13, top + 24)
    if zone == "White":
        d.rectangle(sq, outline=INK, width=1)
    else:
        d.rectangle(sq, fill=RED if zone == "Red" else INK)
    d.text((sx + 20, top + 7), f"{zone.upper()}  (Heat Index {hi_txt})", font=f_h, fill=INK)
    for i, line in enumerate(lines):
        d.text((132, top + 32 + i * body_lh), line, font=f_body, fill=INK)

    # Heat exhaustion / heat stroke boxes
    d.rectangle((122, 755, 545, 900), fill=(255, 248, 225), outline=GOLD_BORDER, width=2)
    d.text((131, 762), "HEAT EXHAUSTION — go to HSE / supervisor", font=_font("b", 16), fill=GOLD)
    y = draw_rich(d, 131, 786, 402, [("Heavy sweating, cold or clammy skin, headache, dizziness, nausea, "
                                        "muscle cramps, weak or fast pulse.", _font("i", 14), INK)], 18)
    draw_rich(d, 131, y + 2, 402, [("DO: move to A/C, sit down, sip water, loosen clothing, cool with a wet cloth.",
                                     _font("bi", 14), GOLD)], 18)

    d.rectangle((583, 755, 995, 900), fill=(253, 236, 234), outline=DARK_RED, width=2)
    d.text((594, 762), "HEAT STROKE — CALL 911 NOW", font=_font("b", 16), fill=DARK_RED)
    y = draw_rich(d, 594, 786, 392, [("Confusion, slurred speech, hot or red skin, NOT sweating, very high "
                                        "temperature, fainting or seizures.", _font("i", 14), INK)], 18)
    draw_rich(d, 594, y + 2, 392, [("DO: call 911. Move to a cool area, cool aggressively (water, ice), and stay with them.",
                                     _font("bi", 14), DARK_RED)], 18)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, "PNG", optimize=True)


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def gh_output(**kv) -> None:
    path = os.environ.get("GITHUB_OUTPUT")
    if not path:
        return
    with open(path, "a", encoding="utf-8") as fh:
        for k, v in kv.items():
            fh.write(f"{k}={v}\n")


STALE_FORECAST_HOURS = 12.0


def build(target: dt.date, out_dir: Path, hourly: dict, daily: dict, force: bool,
          allow_partial: bool = False) -> dict | None:
    png = out_dir / f"{short_date(target)}.png"
    meta_path = out_dir / f"{short_date(target)}.json"
    if png.exists() and not force:
        print(f"{png.name} already exists; nothing to do (use --force to rebuild).")
        gh_output(built="false", date_short=short_date(target))
        return None

    hours = parse_hourly(hourly)
    days = parse_daily(daily) if daily else {}
    summary = summarize_day(hours, target, days)
    if summary is None:
        raise SystemExit(f"NWS hourly forecast has no data for {target} between "
                         f"{hour_label(WINDOW_START_HOUR)} and {hour_label(WINDOW_END_HOUR)}.")
    warnings: list[str] = []
    if summary["missing_hours"]:
        msg = (f"forecast for {target} is missing {len(summary['missing_hours'])} of 13 hours "
               f"({', '.join(summary['missing_hours'])}); the peak may be understated")
        if not allow_partial:
            raise SystemExit(f"Refusing to build: {msg}. Re-run with --allow-partial to build anyway "
                             f"(the record will say which hours were missing).")
        print(f"WARNING: {msg}", file=sys.stderr)
        warnings.append(msg)
    age = forecast_age_hours(hourly)
    if age is not None and age > STALE_FORECAST_HOURS:
        msg = f"NWS hourly forecast is {age:.0f} hours old (issued {hourly['properties'].get('updateTime') or hourly['properties'].get('generatedAt')})"
        print(f"WARNING: {msg}", file=sys.stderr)
        warnings.append(msg)

    week = []
    for wd in rest_of_week_dates(target):
        s = summarize_day(hours, wd, days)
        if s is None:
            continue
        if s["missing_hours"]:
            print(f"Rest of week: skipping {wd} ({len(s['missing_hours'])} hours not in the forecast yet).")
            continue
        week.append({"date": wd, "day": wd.strftime("%a"), "heat_index": s["heat_index"],
                     "zone": s["zone"], "high_f": s["forecast_high_f"], "short_forecast": s["short_forecast"]})

    render_poster(summary, png)
    poster_url = RAW_BASE_URL + png.name
    card = build_card(summary, week, poster_url)
    meta = {
        "date": target.strftime("%m/%d/%Y"),
        "date_short": slash_date(target),
        "heat_index": f"{summary['heat_index']:.1f}",
        "zone": summary["zone"],
        "peak_hour": summary["peak_time"].strftime("%I:%M %p").lstrip("0"),
        "peak_temp_f": summary["peak_temp_f"],
        "peak_humidity": summary["peak_humidity"],
        "forecast_high_f": summary["forecast_high_f"],
        "short_forecast": summary["short_forecast"],
        "location": LOCATION,
        "week": [{"date": w["date"].strftime("%m/%d/%Y"), "day": w["day"], "heat_index": f"{w['heat_index']:.1f}",
                  "zone": w["zone"], "high_f": w["high_f"], "short_forecast": w["short_forecast"]} for w in week],
        "hottest_part_of_day": summary["hottest"],
        "hours": summary["hours"],
        "missing_hours": summary["missing_hours"],
        "poster": png.name,
        "poster_url": poster_url,
        "archive_folder": archive_folder(target),
        "method": (f"Peak NWS heat index, {hour_label(WINDOW_START_HOUR)} to {hour_label(WINDOW_END_HOUR)}, "
                   f"from the hourly forecast for {LOCATION}. Zones: White 90 and below, Red 91-114, Black 115+."),
        "source": nws_provenance(hourly, daily),
        "warnings": warnings,
        "card": card,
        "generated_at": dt.datetime.now(TZ).isoformat(timespec="seconds"),
        "generated_by": "github-actions/heat-poster",
    }
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    # latest.json always points at the newest poster date, even if an older day is rebuilt.
    latest = out_dir / "latest.json"
    try:
        latest_date = dt.datetime.strptime(json.loads(latest.read_text(encoding="utf-8"))["date"], "%m/%d/%Y").date()
    except (OSError, ValueError, KeyError, json.JSONDecodeError):
        latest_date = None
    if latest_date is None or target >= latest_date:
        latest.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(f"Built {png.name}: heat index {meta['heat_index']} ({meta['zone']}), hottest {summary['hottest']}")
    gh_output(built="true", png=str(png), json=str(meta_path), date_short=short_date(target),
              zone=meta["zone"], heat_index=meta["heat_index"])
    return meta


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--date", help="poster date YYYY-MM-DD (default: tomorrow, America/Chicago)")
    ap.add_argument("--out", default="heat-posters", help="output folder")
    ap.add_argument("--force", action="store_true", help="rebuild even if the PNG exists")
    ap.add_argument("--allow-partial", action="store_true",
                    help="build even if some 8 AM-8 PM hours are missing from the forecast (recorded in the JSON)")
    ap.add_argument("--hourly-json", help="saved NWS hourly forecast (offline test)")
    ap.add_argument("--daily-json", help="saved NWS daily forecast (offline test)")
    ap.add_argument("--post", action="store_true", help="post the Teams card after building")
    ap.add_argument("--post-json", help="post the Teams card from an existing metadata JSON and exit")
    args = ap.parse_args(argv)

    if args.post_json:
        url = os.environ.get("TEAMS_HEAT_WEBHOOK_URL", "").strip()
        if not url:
            print("TEAMS_HEAT_WEBHOOK_URL is not set; skipping Teams post.")
            return 0
        meta = json.loads(Path(args.post_json).read_text(encoding="utf-8"))
        post_card(meta, url)
        return 0

    today = dt.datetime.now(TZ).date()
    target = dt.date.fromisoformat(args.date) if args.date else today + dt.timedelta(days=1)

    if args.hourly_json:
        hourly = json.loads(Path(args.hourly_json).read_text(encoding="utf-8"))
        daily = json.loads(Path(args.daily_json).read_text(encoding="utf-8")) if args.daily_json else {}
    else:
        hourly = fetch_json(HOURLY_URL)
        try:
            daily = fetch_json(DAILY_URL, retries=2)
        except SystemExit:
            print("Daily forecast unavailable; using hourly data for the high/summary.", file=sys.stderr)
            daily = {}

    meta = build(target, Path(args.out), hourly, daily, args.force, allow_partial=args.allow_partial)
    if meta and args.post:
        url = os.environ.get("TEAMS_HEAT_WEBHOOK_URL", "").strip()
        if url:
            post_card(meta, url)
        else:
            print("TEAMS_HEAT_WEBHOOK_URL is not set; skipping Teams post.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
