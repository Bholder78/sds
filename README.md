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
