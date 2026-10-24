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
date that already has a poster, so there are never two posters or two cards. A second
run at 2 PM Central rebuilds the day only if the first run failed.

### Records

| Record | Where it lives | Kept by |
|---|---|---|
| Poster of record (PNG) | `heat-posters/<M.D.YY>.png` in this repo, with its commit date | GitHub, forever |
| Day record (JSON): heat index, zone, hottest window, all 13 hourly readings (temp, humidity, heat index), rest-of-week numbers, which NWS forecast run it came from | `heat-posters/<M.D.YY>.json` | GitHub, forever |
| Teams card in the Safety channel | Teams | Microsoft retention |
| SharePoint copy (poster + `<M.D.YY> metadata.json`) in `Safety/Daily Heat Index/<year>/<n. Month>/` | SharePoint | your Teams flow (recipe below) |
| Run log and a copy of the day's files | GitHub → Actions → the run | 90 days |

The Word file (`DHI.docx`), the NWS screenshot and the HIC image that the laptop job
saved are not produced in the cloud. The PNG is the poster of record and the JSON holds
the forecast data behind it, which the screenshot used to show. The 8 AM **Daily Heat
Index Log** (hourly monitoring PDF) is a separate job and still runs on the laptop.

### Teams flow recipe (no admin needed, runs as you)

1. Teams → Safety channel → ⋯ → **Workflows** → "Post to a channel when a webhook
   request is received" → name it **Heat Index** → copy the URL into the GitHub secret
   `TEAMS_HEAT_WEBHOOK_URL`. The card posts from this step alone.
2. To also file the records on SharePoint, open the flow in Power Automate and add after
   the post step (all standard connectors):
   - **SharePoint → Create file**: site *Operations*, folder
     `/Shared Documents/Safety/Daily Heat Index/` + `triggerBody()?['archive_folder']`,
     name `triggerBody()?['metadata_name']`, content `string(triggerBody()?['metadata'])`.
   - **OneDrive for Business → Upload file from URL**: URL `triggerBody()?['poster_url']`,
     path `/Heat Index Auto-Post/` + `triggerBody()?['poster_name']`, then
     **Get file content** and a second **SharePoint → Create file** into the same folder
     with name `triggerBody()?['poster_name']`.
   - Optional **Outlook → Send an email (V2)** to supervisors with `poster_url`.
   Create the new month's folder on SharePoint when a month starts (the laptop job did
   this too), or add a "Create new folder" step before the file steps.
   The webhook body also carries `date`, `heat_index` and `zone` for conditions, e.g.
   email only when `zone` is Red or Black.
