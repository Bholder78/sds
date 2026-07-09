"""
SDS register builder — runs automatically on GitHub whenever a PDF is added.

  1. Scans sds/ for PDF files.
  2. For each NEW pdf it reads the sheet (OCR fallback for scanned PDFs) and
     best-effort fills product name, CAS#, signal word, hazard class, pictograms,
     hazard/precautionary statements, first-aid, storage, PPE, etc.
     Existing rows are never overwritten, so manual corrections are preserved.
  3. Rows whose PDF was deleted are kept but marked Archived.
  4. Writes data/sds_data.json and data/sds_data.js (used by index.html).

No arguments needed:  python scripts/build_index.py
"""
import os, re, json, io, shutil, datetime

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PDF_DIR = os.path.join(HERE, "sds")
JSONF = os.path.join(HERE, "data", "sds_data.json")
JSF = os.path.join(HERE, "data", "sds_data.js")

HEADERS = ["File", "Product Name", "Official / Chemical Name", "Manufacturer",
           "Synonyms / Common Names", "CAS #", "Signal Word", "Hazard Class", "Pictograms",
           "NFPA (H/F/R/Sp)", "HMIS (H/F/R/PPE)",
           "Hazard Statements", "Precautionary Statements", "First Aid (Sec 4)",
           "Fire-Fighting (Sec 5)", "Accidental Release (Sec 6)", "Handling & Storage (Sec 7)",
           "Exposure Controls / PPE (Sec 8)", "Required PPE", "Emergency Phone",
           "SDS Revision Date", "Location / Area", "Last Reviewed", "Status / Notes"]

H = {
 "H200":"Unstable explosive","H220":"Extremely flammable gas","H221":"Flammable gas",
 "H222":"Extremely flammable aerosol","H223":"Flammable aerosol","H224":"Extremely flammable liquid and vapour",
 "H225":"Highly flammable liquid and vapour","H226":"Flammable liquid and vapour","H228":"Flammable solid",
 "H229":"Pressurized container: may burst if heated","H240":"Heating may cause an explosion",
 "H241":"Heating may cause a fire or explosion","H242":"Heating may cause a fire",
 "H250":"Catches fire spontaneously if exposed to air","H260":"In contact with water releases flammable gases",
 "H261":"In contact with water releases flammable gases","H270":"May cause or intensify fire; oxidizer",
 "H271":"May cause fire or explosion; strong oxidizer","H272":"May intensify fire; oxidizer",
 "H280":"Contains gas under pressure; may explode if heated","H281":"Contains refrigerated gas; may cause cryogenic burns",
 "H290":"May be corrosive to metals","H300":"Fatal if swallowed","H301":"Toxic if swallowed",
 "H302":"Harmful if swallowed","H304":"May be fatal if swallowed and enters airways",
 "H310":"Fatal in contact with skin","H311":"Toxic in contact with skin","H312":"Harmful in contact with skin",
 "H314":"Causes severe skin burns and eye damage","H315":"Causes skin irritation","H316":"Causes mild skin irritation",
 "H317":"May cause an allergic skin reaction","H318":"Causes serious eye damage","H319":"Causes serious eye irritation",
 "H320":"Causes eye irritation","H330":"Fatal if inhaled","H331":"Toxic if inhaled","H332":"Harmful if inhaled",
 "H334":"May cause allergy or asthma symptoms or breathing difficulties if inhaled",
 "H335":"May cause respiratory irritation","H336":"May cause drowsiness or dizziness",
 "H340":"May cause genetic defects","H341":"Suspected of causing genetic defects",
 "H350":"May cause cancer","H351":"Suspected of causing cancer","H360":"May damage fertility or the unborn child",
 "H361":"Suspected of damaging fertility or the unborn child","H362":"May cause harm to breast-fed children",
 "H370":"Causes damage to organs","H371":"May cause damage to organs",
 "H372":"Causes damage to organs through prolonged or repeated exposure",
 "H373":"May cause damage to organs through prolonged or repeated exposure",
 "H400":"Very toxic to aquatic life","H410":"Very toxic to aquatic life with long lasting effects",
 "H411":"Toxic to aquatic life with long lasting effects","H412":"Harmful to aquatic life with long lasting effects",
 "H413":"May cause long lasting harmful effects to aquatic life",
}
PICTO = [
 (("H200","H201","H202","H203","H204","H240","H241"), "GHS01", "Exploding bomb", "Explosive"),
 (("H220","H221","H222","H223","H224","H225","H226","H228","H229","H250","H260","H261"), "GHS02", "Flame", "Flammable"),
 (("H270","H271","H272"), "GHS03", "Flame over circle", "Oxidizer"),
 (("H280","H281"), "GHS04", "Gas cylinder", "Compressed gas"),
 (("H290","H314","H318"), "GHS05", "Corrosion", "Corrosive"),
 (("H300","H301","H310","H311","H330","H331"), "GHS06", "Skull and crossbones", "Acute toxic"),
 (("H302","H312","H315","H317","H319","H332","H335","H336"), "GHS07", "Exclamation mark", "Irritant / harmful"),
 (("H304","H334","H340","H341","H350","H351","H360","H361","H370","H371","H372","H373"), "GHS08", "Health hazard", "Health hazard"),
 (("H400","H410","H411","H412","H413"), "GHS09", "Environment", "Environmental"),
]
NAME_BY_CODE = {p[1]: p[2] for p in PICTO}
CLASS_BY_CODE = {p[1]: p[3] for p in PICTO}

# ---------------- text extraction (with OCR fallback) ----------------
def find_tesseract():
    exe = shutil.which("tesseract")
    if exe:
        return exe
    for base in (os.environ.get("ProgramFiles", ""), os.environ.get("ProgramFiles(x86)", ""),
                 os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs")):
        cand = os.path.join(base, "Tesseract-OCR", "tesseract.exe")
        if base and os.path.exists(cand):
            return cand
    return None

TESS = find_tesseract()

def ocr_pdf(path, max_pages=12):
    try:
        import fitz, pytesseract
        from PIL import Image
        pytesseract.pytesseract.tesseract_cmd = TESS
        doc = fitz.open(path)
        out = []
        for i, page in enumerate(doc):
            if i >= max_pages:
                break
            pix = page.get_pixmap(dpi=300)
            img = Image.open(io.BytesIO(pix.tobytes("png")))
            out.append(pytesseract.image_to_string(img))
        return "\n".join(out)
    except Exception:
        return ""

def get_text(path):
    text = ""
    try:
        import pypdf
        r = pypdf.PdfReader(path)
        text = "\n".join((p.extract_text() or "") for p in r.pages)
    except Exception:
        text = ""
    if len(text.strip()) < 120 and TESS:
        ocr = ocr_pdf(path)
        if len(ocr.strip()) > len(text.strip()):
            return ocr, True
    return text, False

def first(patterns, text):
    for pat in patterns:
        m = re.search(pat + r"\s*[:\-–]?\s*(.+)", text, re.I)
        if m:
            val = re.split(r"\s{2,}", m.group(1).strip())[0].strip()
            if val and val.lower() not in ("none", "n/a", "not applicable", "-"):
                return val[:200]
    return ""

SEC_TITLES = {
    1: r"identification", 2: r"hazard", 3: r"composition|information\s+on\s+ingredients",
    4: r"first[\s\-]?aid", 5: r"fire[\s\-]?fighting", 6: r"accidental\s+release",
    7: r"handling\s+and\s+storage", 8: r"exposure\s+control", 9: r"physical\s+and\s+chemical",
    10: r"stability\s+and\s+reactivity", 11: r"toxicolog", 12: r"ecolog",
    13: r"disposal", 14: r"transport", 15: r"regulatory", 16: r"other\s+information",
}

def find_heads(text):
    heads = {}
    for m in re.finditer(r"(?im)^\s*section\s*0?(\d{1,2})\b.*$", text):
        heads.setdefault(int(m.group(1)), m.start())
    if len(heads) < 6:
        for m in re.finditer(r"(?im)^\s*0?(\d{1,2})[.)]\s+[A-Za-z]", text):
            num = int(m.group(1))
            if 1 <= num <= 16:
                heads.setdefault(num, m.start())
    # some PDFs extract with headers glued mid-line ("...Number 111. IdentificationProduct...")
    # or with odd bullet chars ("4 – First Aid Measures") — find any section still missing
    # by "<number> <standard title>" anywhere in the text
    for num, title in SEC_TITLES.items():
        if num in heads:
            continue
        m = (re.search(r"(?i)\b0?%d\s*[.):\-]\s*(?:%s)" % (num, title), text)
             or re.search(r"(?i)0?%d\s*[^\w\n]{0,3}\s*(?:%s)" % (num, title), text))
        if m:
            heads[num] = m.start()
    return heads

def section(text, n):
    heads = find_heads(text)
    if n not in heads:
        return ""
    start = heads[n]
    nexts = [pos for pos in heads.values() if pos > start]
    body = text[start:(min(nexts) if nexts else len(text))]
    body = re.sub(r"(?i)^\s*section\s*0?\d{1,2}\s*[:.\-–]?.*", "", body, count=1).strip()
    return re.sub(r"\n{2,}", "\n", body).strip()[:1500]

def suggest_ppe(sec8, codes):
    t = sec8.lower()
    ppe = []
    def add(x):
        if x not in ppe: ppe.append(x)
    if any(k in t for k in ("goggle", "face shield", "eye protection", "safety glasses")) \
            or any(c in codes for c in ("H318","H319","H314")):
        add("Safety glasses / goggles")
    if any(c in codes for c in ("H314","H318")):
        add("Face shield")
    if "glove" in t or any(c in codes for c in ("H314","H315","H310","H311","H317")):
        add("Chemical-resistant gloves")
    resp = re.search(r"respirator[^.\n]{0,70}", t)
    if any(c in codes for c in ("H330","H331","H334","H335","H336")) or \
            (resp and not re.search(r"\bnot\b|none|n/a", resp.group(0))):
        add("Respirator (if exposure limits exceeded)")
    if any(k in t for k in ("apron", "protective clothing", "coverall", "protective suit")) \
            or any(c in codes for c in ("H314","H310")):
        add("Protective clothing / apron")
    if "boot" in t:
        add("Safety boots")
    return "; ".join(ppe)

def ratings(text, system):
    m = re.search(system, text, re.I)
    if not m:
        return ""
    win = text[m.start():m.start() + 220]
    wl = win.lower()
    h = re.search(r"health[^0-9\n]{0,8}([0-4])", wl)
    f = re.search(r"(?:flammability|fire|flammable)[^0-9\n]{0,8}([0-4])", wl)
    r = re.search(r"(?:reactivity|instability|physical hazard)[^0-9\n]{0,8}([0-4])", wl)
    trio = re.search(r"\b([0-4])\s*[-/]\s*([0-4])\s*[-/]\s*([0-4])\b", win)
    if h and f and r:
        p = [h.group(1), f.group(1), r.group(1)]
    elif trio:
        p = [trio.group(1), trio.group(2), trio.group(3)]
    else:
        return ""
    out = f"H {p[0]} / F {p[1]} / R {p[2]}"
    if system.lower() == "nfpa":
        sp = re.search(r"(?:special|specific hazard)[^a-z0-9\n]{0,8}(ox|w|sa|cor|acid|alk)", wl)
        if sp:
            out += f" / {sp.group(1).upper()}"
    else:
        pp = re.search(r"(?:personal protection|protective equipment|ppe)[^a-z\n]{0,10}([a-kx])\b", wl)
        if pp:
            out += f" / PPE {pp.group(1).upper()}"
    return out

def despace(s):
    return re.sub(r"(?<=[a-z])(?=[A-Z])", " ", s)

def clean_name(s):
    s = despace(s)
    s = re.split(r"\s*(?:Cat(?:alog(?:ue)?)?\.?\s*No|Catalog|Product\s*Code|Product\s*Number|"
                 r"Recommended|Synonym|CAS\b|Other\s*means|Article|Item\s*No|REACH|Version|"
                 r"Issue|Revision|SDS\b|Manufacturer|Supplier)", s, maxsplit=1, flags=re.I)[0]
    return s.strip(" :;-.").strip()[:120]

def hazard_block(text):
    m = re.search(r"hazard\s*statement[s]?\s*[:\-]?", text, re.I)
    if not m:
        return ""
    tail = text[m.end():m.end() + 700]
    cut = re.search(r"(precautionary|pictogram|signal\s*word|response|prevention|storage|disposal"
                    r"|GHS|section\s*3|other\s*hazard|supplemental)", tail, re.I)
    if cut:
        tail = tail[:cut.start()]
    return re.sub(r"\s+", " ", despace(tail)).strip()[:500]

INFER = [
 (r"explosive", "GHS01"),
 (r"flammable", "GHS02"),
 (r"oxidi[sz]", "GHS03"),
 (r"gas under pressure|compressed gas|liquefied gas", "GHS04"),
 (r"corrosive|severe skin burns|serious eye damage|burns to", "GHS05"),
 (r"\bfatal\b|acute tox|toxic if (?:swallowed|inhaled)", "GHS06"),
 (r"eye irritation|skin irritation|harmful if|drowsi|dizz|respiratory irritation|allergic skin|mild skin", "GHS07"),
 (r"carcinog|cancer|mutagen|genetic defect|damage to organ|fertility|unborn|aspiration|asthma|reproductiv", "GHS08"),
 (r"aquatic|harmful to the environment", "GHS09"),
]
def infer_pictos(t):
    t = re.sub(r"non[- ]?flammable|not flammable", "", t.lower())
    found = [code for pat, code in INFER if re.search(pat, t)]
    order = ["GHS01","GHS02","GHS03","GHS04","GHS05","GHS06","GHS07","GHS08","GHS09"]
    return [c for c in order if c in found]

def extract(path):
    text, used_ocr = get_text(path)
    fname = os.path.basename(path)
    rec = {h: "" for h in HEADERS}
    rec["File"] = fname
    if len(text.strip()) < 40:
        rec["Product Name"] = os.path.splitext(fname)[0].replace("_", " ")
        rec["Status / Notes"] = ("REVIEW — no readable text" + ("" if TESS else " (and no OCR engine)")
                                 + ". Enter details manually.")
        return rec
    sec1 = section(text, 1) or text[:800]
    sec3 = section(text, 3)
    sec8 = section(text, 8)
    rec["Product Name"] = (clean_name(first([r"product\s*name", r"product\s*identifier", r"trade\s*name"], sec1))
                           or os.path.splitext(fname)[0].replace("_", " "))
    chem = first([r"chemical\s*name"], sec1)
    if not chem and sec3:
        for line in sec3.splitlines():
            mc = re.search(r"(.+?)\s+(?:CAS(?:\s*(?:No|#|Number))?\.?\s*[:\-]?\s*)?\d{2,7}-\d{2}-\d", line, re.I)
            if mc:
                chem = re.sub(r"\bCAS\b.*", "", mc.group(1), flags=re.I).strip(" :\t-")
                break
    rec["Official / Chemical Name"] = chem[:120] if chem else ""
    rec["Manufacturer"] = first([r"manufacturer", r"supplier", r"company\s*name", r"company"], sec1)
    rec["Synonyms / Common Names"] = first([r"synonyms?", r"other\s*means\s*of\s*identification", r"common\s*name"], sec1)
    mcas = re.search(r"\b(\d{2,7}-\d{2}-\d)\b", sec3 or text)
    rec["CAS #"] = mcas.group(1) if mcas else ""
    sec2 = section(text, 2)
    sw = re.search(r"signal\s*word\s*[:\-]?\s*(danger|warning)", text, re.I)
    if sw:
        rec["Signal Word"] = sw.group(1).capitalize()
    else:
        hasD = re.search(r"\bdanger\b", sec2 or text, re.I)
        hasW = re.search(r"\bwarning\b", sec2 or text, re.I)
        rec["Signal Word"] = "Danger" if (hasD and not hasW) else ("Warning" if (hasW and not hasD) else "")
    codes = sorted(set(re.findall(r"\bH\d{3}\b", text)))
    hb = ""
    if codes:
        rec["Hazard Statements"] = "\n".join(f"{c} {H.get(c,'')}".strip() for c in codes)
    pcodes = []
    src = sec2 or text
    for m in re.finditer(r"\bP\d{3}(?:\s*\+\s*P\d{3})*\b[^\n]*", src):
        line = re.sub(r"\s{2,}", " ", m.group(0)).strip()
        if line not in pcodes:
            pcodes.append(line)
    rec["Precautionary Statements"] = "\n".join(pcodes[:14])
    if codes:
        present = [code for sset, code, _, _ in PICTO if any(c in sset for c in codes)]
    else:
        hb = hazard_block(text)
        rec["Hazard Statements"] = hb
        present = infer_pictos(hb or sec2)
    rec["Pictograms"] = ", ".join(f"{NAME_BY_CODE[c]} ({c})" for c in present)
    rec["Hazard Class"] = ", ".join(sorted({CLASS_BY_CODE[c] for c in present}))
    rec["NFPA (H/F/R/Sp)"] = ratings(text, "nfpa")
    rec["HMIS (H/F/R/PPE)"] = ratings(text, "hmis")
    rec["First Aid (Sec 4)"] = section(text, 4)
    rec["Fire-Fighting (Sec 5)"] = section(text, 5)
    rec["Accidental Release (Sec 6)"] = section(text, 6)
    rec["Handling & Storage (Sec 7)"] = section(text, 7)
    rec["Exposure Controls / PPE (Sec 8)"] = sec8
    rec["Required PPE"] = suggest_ppe(sec8, codes)
    mph = re.search(r"emergency[^\n]{0,40}?(\+?[\d][\d\(\)\-\s]{6,}\d)", text, re.I)
    rec["Emergency Phone"] = mph.group(1).strip() if mph else ""
    mrev = re.search(r"(?:revision date|date of (?:issue|preparation|revision)|version date|issue date)"
                     r"\s*[:\-]?\s*(\d{1,4}[-/.]\d{1,2}[-/.]\d{1,4}|[A-Za-z]{3,9}\s+\d{1,2},?\s+\d{4})", text, re.I)
    rec["SDS Revision Date"] = mrev.group(1).strip() if mrev else ""
    base = "Imported (OCR)" if used_ocr else "Imported"
    if not codes and hb:
        rec["Status / Notes"] = base + " — verify (no H-codes; hazards text-parsed)"
    elif not codes and not rec["Hazard Statements"]:
        rec["Status / Notes"] = base + " — verify (no hazards found / may be non-hazardous)"
    else:
        rec["Status / Notes"] = base + " — verify"
    return rec

# ---------------- register maintenance ----------------
def main():
    rows = []
    if os.path.exists(JSONF):
        with open(JSONF, encoding="utf-8") as f:
            rows = json.load(f)
    by_file = {r.get("File", ""): r for r in rows}
    pdfs = sorted(f for f in os.listdir(PDF_DIR) if f.lower().endswith(".pdf"))
    today = datetime.date.today().isoformat()

    added = 0
    for fname in pdfs:
        if fname in by_file:
            # PDF returned after being archived
            r = by_file[fname]
            if r.get("Status / Notes", "").startswith("ARCHIVED"):
                r["Status / Notes"] = r["Status / Notes"].split("ARCHIVED", 1)[-1].strip(" —-") or "Restored"
            continue
        rec = extract(os.path.join(PDF_DIR, fname))
        rec["Last Reviewed"] = today
        by_file[fname] = rec
        rows.append(rec)
        added += 1
        print(f"  + added: {fname}  ->  {rec['Product Name']}")

    archived = 0
    have = set(pdfs)
    for r in rows:
        if r.get("File") not in have and not r.get("Status / Notes", "").startswith("ARCHIVED"):
            r["Status / Notes"] = f"ARCHIVED {today} (PDF removed) — " + (r.get("Status / Notes") or "")
            archived += 1
            print(f"  - archived: {r.get('File')}")

    rows.sort(key=lambda r: (r.get("Product Name") or r.get("File") or "").lower())

    os.makedirs(os.path.dirname(JSONF), exist_ok=True)
    with open(JSONF, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=1)
    meta = {"updated": today, "count": sum(1 for r in rows if not r.get("Status / Notes","").startswith("ARCHIVED"))}
    with open(JSF, "w", encoding="utf-8") as f:
        f.write("window.SDS_META = " + json.dumps(meta) + ";\n")
        f.write("window.SDS_DATA = " + json.dumps(rows, ensure_ascii=False) + ";\n")
    print(f"Done: {len(rows)} rows ({added} new, {archived} archived).")

if __name__ == "__main__":
    main()
