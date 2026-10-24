# Fibertech SDS Tracker

A searchable online library of Safety Data Sheets. Employees open the website,
type a product name (or CAS #), and view or print the full SDS — from any phone
or computer, no login needed.

## How to ADD a new SDS (takes ~1 minute)

1. Go to this repository on **github.com** and open the **`sds`** folder.
2. Click **Add file → Upload files** (top right).
3. Drag the PDF in, then click **Commit changes**.
4. Done. Within ~2 minutes the robot reads the sheet, fills in the register
   (product name, CAS #, hazards, pictograms, PPE…), and the website updates itself.

Tips:
- Name the file after the product, e.g. `WD-40.pdf` — the filename is the
  fallback product name if the PDF can't be read.
- New entries are marked **"verify"** in Notes. Skim them once to confirm the
  robot read the sheet correctly.

## How to REMOVE / replace an SDS

- **Replace (new revision):** upload the new PDF with the **same filename** —
  then delete its row's old data by removing the file first if you want a fresh
  re-read (delete, wait for the site to update, then upload the new one).
- **Remove:** open the file in the `sds` folder on github.com, click the trash
  icon, commit. The chemical stays in the register marked **ARCHIVED** (so your
  30-year record is kept) but is hidden from the main list.

## How to CORRECT a detail (product name, location, etc.)

Open `data/sds_data.json` on github.com, click the pencil icon, edit the text,
commit. The robot never overwrites your manual edits.

## Where things live

| Path | What it is |
|---|---|
| `index.html` | The search page employees see |
| `sds/` | The SDS PDF files — **this is the only folder you normally touch** |
| `data/sds_data.json` | The register (auto-built, manually correctable) |
| `scripts/build_index.py` | The robot that reads new PDFs |
| `.github/workflows/build.yml` | Tells GitHub to run the robot on every upload |

## Daily Heat Index poster (runs in the cloud)

Every Sunday–Thursday at about noon, GitHub builds **tomorrow's** Daily Heat Index
poster from the National Weather Service forecast for Elberfeld, commits it to
`heat-posters/`, and posts the Teams card. Nothing has to be switched on at the plant.

| What | Where |
|---|---|
| The poster | `heat-posters/<M.D.YY>.png` (e.g. `10.23.26.png`) |
| The numbers behind it | `heat-posters/<M.D.YY>.json`, and `heat-posters/latest.json` for the newest day |
| The job | `.github/workflows/heat-poster.yml` (schedule + "Run workflow" button) |
| The code | `scripts/heat_poster.py` (offline checks: `python scripts/test_heat_poster.py`) |

How the number is picked: NWS hourly forecast, heat index for each hour from 8 AM to
8 PM, highest one wins. Zones: White 90 and below, Red 91–114, Black 115 and up.

**Run it by hand:** GitHub → Actions → "Daily heat poster" → Run workflow. Leave the
date blank for tomorrow, or type one (YYYY-MM-DD). Tick "force" to rebuild a day that
already exists.

**Teams card:** add a repository secret named `TEAMS_HEAT_WEBHOOK_URL` (Settings →
Secrets and variables → Actions) holding the URL from a Teams workflow
"Post to a channel when a webhook request is received". Without the secret the
poster still builds and commits; only the card is skipped.

**If the laptop job also runs:** the cloud job starts five minutes later and skips any
date that already has a poster, so there are never two posters or two cards.
