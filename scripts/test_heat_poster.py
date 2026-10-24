#!/usr/bin/env python3
"""Offline checks for heat_poster.py (no network). Run: python scripts/test_heat_poster.py [out_dir]"""
import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import heat_poster as hp  # noqa: E402

OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/tmp/heat_poster_test")
OUT.mkdir(parents=True, exist_ok=True)

# 1. Heat index formula vs values recorded by the laptop job (metadata.json files)
for t, rh, expected in [(72, 38, 70.7), (90, 42, 91.4), (82, 74, 87.3), (86, 57, 90.1), (83, 25, 80.8)]:
    got = round(hp.heat_index(t, rh), 1)
    assert got == expected, f"heat_index({t},{rh}) = {got}, expected {expected}"

# 2. Zone thresholds work on the rounded value shown on the poster
assert hp.zone_for(90.94) == "White" and hp.zone_for(90.96) == "Red"
assert hp.zone_for(114.94) == "Red" and hp.zone_for(114.96) == "Black"
assert hp.hour_label(8) == "8 AM" and hp.hour_label(12) == "12 PM" and hp.hour_label(20) == "8 PM" and hp.hour_label(0) == "12 AM"
assert hp.short_date(dt.date(2026, 10, 23)) == "10.23.26" and hp.slash_date(dt.date(2026, 10, 8)) == "10/8/26"
assert [d.strftime("%a") for d in hp.rest_of_week_dates(dt.date(2026, 10, 13))] == ["Wed", "Thu", "Fri"]
assert hp.rest_of_week_dates(dt.date(2026, 10, 23)) == []


# 3. Synthetic api.weather.gov responses
def make_fixtures(start: dt.date, days: int, overrides: dict, daily_over: dict):
    """overrides[(date, hour)] = (temp_f, rh); other hours follow a mild diurnal curve."""
    import math
    hourly, daily = [], []
    for n in range(days):
        d = start + dt.timedelta(days=n)
        base = daily_over.get(d, {}).get("base", 55)
        for h in range(24):
            temp = base + 12 * math.sin((h - 9) / 24 * 2 * math.pi)
            rh = 60 - 20 * math.sin((h - 9) / 24 * 2 * math.pi)
            temp, rh = overrides.get((d, h), (round(temp), round(rh)))
            hourly.append({"startTime": f"{d.isoformat()}T{h:02d}:00:00-05:00",
                           "temperature": temp, "temperatureUnit": "F",
                           "relativeHumidity": {"value": rh},
                           "shortForecast": daily_over.get(d, {}).get("short", "Sunny")})
        daily.append({"isDaytime": True, "startTime": f"{d.isoformat()}T06:00:00-05:00",
                      "temperature": daily_over.get(d, {}).get("high", round(base + 12)),
                      "temperatureUnit": "F", "shortForecast": daily_over.get(d, {}).get("short", "Sunny")})
    return {"properties": {"periods": hourly}}, {"properties": {"periods": daily}}


D = dt.date
# Scenario A - 10/23/26, White 70.7 at 3 PM, Friday so no "rest of week"
hourly, daily = make_fixtures(D(2026, 10, 22), 4, {(D(2026, 10, 23), 15): (72, 38)},
                              {D(2026, 10, 23): {"base": 58, "high": 72, "short": "Sunny"}})
a_dir = OUT / "A_white"; a_dir.mkdir(exist_ok=True)
meta = hp.build(D(2026, 10, 23), a_dir, hourly, daily, force=True)
assert meta["heat_index"] == "70.7" and meta["zone"] == "White", meta
assert meta["card"]["body"][1]["facts"][2]["value"] == "around 3 PM", meta["card"]["body"][1]
assert meta["week"] == [] and len(meta["card"]["body"]) == 3
assert meta["forecast_high_f"] == 72 and meta["peak_temp_f"] == 72 and meta["peak_humidity"] == 38

# Scenario B - 10/13/26, Red 91.4, plateau 3-5 PM, Tue so Wed/Thu/Fri follow
over = {(D(2026, 10, 13), 15): (90, 40), (D(2026, 10, 13), 16): (90, 42), (D(2026, 10, 13), 17): (89, 44),
        (D(2026, 10, 14), 13): (85, 60), (D(2026, 10, 15), 15): (84, 55), (D(2026, 10, 16), 14): (65, 40)}
dover = {D(2026, 10, 13): {"base": 75, "high": 90, "short": "Sunny"},
         D(2026, 10, 14): {"base": 72, "high": 85, "short": "Showers And Thunderstorms Likely"},
         D(2026, 10, 15): {"base": 70, "high": 84, "short": "Chance Showers And Thunderstorms"},
         D(2026, 10, 16): {"base": 52, "high": 65, "short": "Mostly Sunny"}}
hourly, daily = make_fixtures(D(2026, 10, 12), 6, over, dover)
b_dir = OUT / "B_red"; b_dir.mkdir(exist_ok=True)
meta = hp.build(D(2026, 10, 13), b_dir, hourly, daily, force=True)
assert meta["heat_index"] == "91.4" and meta["zone"] == "Red", meta
assert meta["card"]["body"][1]["facts"][2]["value"] == "3 PM – 5 PM", meta["card"]["body"][1]
assert [w["day"] for w in meta["week"]] == ["Wed", "Thu", "Fri"], meta["week"]
assert meta["week"][0]["short_forecast"] == "Showers And Thunderstorms Likely" and meta["week"][0]["high_f"] == 85
assert meta["card"]["body"][2]["type"] == "Container" and len(meta["card"]["body"][2]["items"][2]["columns"]) == 3

# Scenario C - synthetic Black day (temp 100, RH 60 -> 129.5), Monday
hourly, daily = make_fixtures(D(2026, 7, 19), 7, {(D(2026, 7, 20), 14): (100, 60), (D(2026, 7, 20), 15): (99, 60)},
                              {D(2026, 7, 20): {"base": 86, "high": 100, "short": "Hot"}})
c_dir = OUT / "C_black"; c_dir.mkdir(exist_ok=True)
meta = hp.build(D(2026, 7, 20), c_dir, hourly, daily, force=True)
assert meta["zone"] == "Black" and len(meta["week"]) == 4, (meta["zone"], meta["week"])

# 4. Skip when the poster already exists (what keeps the cloud job from fighting the laptop)
assert hp.build(D(2026, 7, 20), c_dir, hourly, daily, force=False) is None

# 5. Missing humidity hours are ignored, not fatal; a day with no usable hours returns None
hourly["properties"]["periods"][0]["relativeHumidity"] = {"value": None}
assert hp.summarize_day(hp.parse_hourly(hourly), D(2026, 7, 20)) is not None
assert hp.summarize_day(hp.parse_hourly(hourly), D(2030, 1, 1)) is None

print("all checks passed")
for p in sorted(OUT.rglob("*.png")):
    print(p)
