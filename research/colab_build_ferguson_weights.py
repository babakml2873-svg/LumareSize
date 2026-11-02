# -*- coding: utf-8 -*-
"""
Build.com / FergusonHome.com product-weight lookup — for Google Colab.

Polite, low-volume lookup by exact part number:
  * reads robots.txt and skips disallowed paths
  * 1 request every DELAY seconds (default 8 s), with backoff on 429
  * stops immediately on 403 / CAPTCHA / bot challenge (does NOT try to bypass it)
  * accepts a weight only if the page contains the exact part number
  * saves progress after every SKU, so re-running resumes

Input: one or more of the CSVs from output/missing_weights_by_brand/ (columns: Part Number, Description).
       The brand is taken from the file name (e.g. ELCO_Lighting.csv -> "ELCO Lighting").
Output: build_weights.csv  (part_number, brand, site, url, weight_text, weight_lb, weight_kg, weight_label)

In Colab:
  1) Runtime > Run all (or paste this file into a cell)
  2) Upload the CSV files when prompted
  3) Download build_weights.csv at the end and send it back for merging
"""
import csv, json, os, re, time, html, urllib.parse, urllib.robotparser
import requests

SITES = ["https://www.build.com", "https://www.fergusonhome.com"]
DELAY = 8                 # seconds between requests (keep it slow)
MAX_PER_RUN = 500         # SKUs per run; re-run to continue
OUT = "build_weights.csv"
UA = "Mozilla/5.0 (compatible; product-weight-research; contact: your-email@example.com)"  # identify yourself honestly

session = requests.Session()
session.headers.update({"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"})

class Blocked(Exception):
    pass

# ---------- robots.txt ----------
robots = {}
def allowed(url):
    base = "{0.scheme}://{0.netloc}".format(urllib.parse.urlparse(url))
    if base not in robots:
        rp = urllib.robotparser.RobotFileParser()
        try:
            r = session.get(base + "/robots.txt", timeout=20)
            rp.parse(r.text.splitlines() if r.status_code == 200 else [])
        except Exception:
            rp.parse([])
        robots[base] = rp
    return robots[base].can_fetch(UA, url)

# ---------- polite GET ----------
_last = [0.0]
def get(url):
    if not allowed(url):
        return None
    wait = DELAY - (time.time() - _last[0])
    if wait > 0:
        time.sleep(wait)
    for attempt in range(4):
        _last[0] = time.time()
        r = session.get(url, timeout=30, allow_redirects=True)
        if r.status_code == 429:
            time.sleep(60 * (attempt + 1)); continue
        text = r.text or ""
        if r.status_code == 403 or re.search(r"captcha|just a moment|verify you are (a )?human|access denied|px-captcha", text[:5000], re.I):
            raise Blocked(f"{r.status_code} at {url}")
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r
    return None

# ---------- parsing ----------
WEIGHT_PATTERNS = [
    # "Product Weight: 2.5 lbs", "Weight (lbs.) 2.5", "Shipping Weight 3 lb"
    r"((?:product|item|net|unit|shipping|ship|gross)?\s*weight)\s*(?:\(lbs?\.?\))?\s*[:\-]?\s*</?[^>]{0,80}>?\s*([\d]+(?:\.\d+)?)\s*(lbs?|pounds?|oz|kg|g)?\b",
]
def norm(s):
    return re.sub(r"[^A-Z0-9]", "", str(s).upper())

def parse_weight(page_html):
    # 1) JSON-LD Product.weight
    for block in re.findall(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', page_html, re.S | re.I):
        try:
            data = json.loads(html.unescape(block))
        except Exception:
            continue
        items = data if isinstance(data, list) else [data]
        for it in items:
            if isinstance(it, dict) and it.get("@type") in ("Product", ["Product"]) and it.get("weight"):
                w = it["weight"]
                val = w.get("value") if isinstance(w, dict) else w
                unit = (w.get("unitCode") or w.get("unitText") or "lb") if isinstance(w, dict) else "lb"
                try:
                    return float(val), unit, "weight (JSON-LD)", f"{val} {unit}"
                except Exception:
                    pass
    # 2) visible spec table text
    text = re.sub(r"\s+", " ", html.unescape(page_html))
    for pat in WEIGHT_PATTERNS:
        for m in re.finditer(pat, text, re.I):
            label, val, unit = m.group(1).strip(), m.group(2), (m.group(3) or "lb")
            if "font" in label.lower():
                continue
            try:
                return float(val), unit, label, m.group(0)[:120]
            except Exception:
                continue
    return None

def to_lb(val, unit):
    u = unit.lower()
    if u.startswith("kg"): return val / 0.45359237
    if u == "g": return val / 453.59237
    if u.startswith("oz"): return val / 16
    return val

def find_product_url(site, brand, part):
    q = urllib.parse.quote_plus(f"{brand} {part}")
    r = get(f"{site}/search?term={q}")
    if r is None:
        return None, None
    # search may redirect straight to the product page
    if norm(part) in norm(r.text) and "/s" in r.url and "search" not in r.url:
        return r.url, r.text
    links = re.findall(r'href="(/[^"#?]+/s\d+[^"]*)"', r.text)
    for href in dict.fromkeys(links):
        if norm(part)[:6] in norm(href):
            p = get(site + href)
            if p is not None and norm(part) in norm(p.text):
                return p.url, p.text
    return None, None

# ---------- main ----------
def load_inputs():
    try:
        from google.colab import files
        up = files.upload()
        names = list(up.keys())
    except Exception:
        names = [f for f in os.listdir(".") if f.endswith(".csv") and f != OUT]
    rows = []
    for fn in names:
        brand = os.path.splitext(os.path.basename(fn))[0].replace("_", " ")
        with open(fn, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                if r.get("Part Number"):
                    rows.append((brand, r["Part Number"].strip()))
    return rows

def main():
    todo = load_inputs()
    done = set()
    if os.path.exists(OUT):
        with open(OUT, newline="", encoding="utf-8") as f:
            done = {(r["brand"], r["part_number"]) for r in csv.DictReader(f)}
    new = not os.path.exists(OUT)
    out = open(OUT, "a", newline="", encoding="utf-8")
    w = csv.writer(out)
    if new:
        w.writerow(["part_number", "brand", "site", "url", "weight_text", "weight_lb", "weight_kg", "weight_label"])
    n = 0
    blocked_sites = set()
    for brand, part in todo:
        if (brand, part) in done or n >= MAX_PER_RUN:
            continue
        n += 1
        result = None
        for site in SITES:
            if site in blocked_sites:
                continue
            try:
                url, page = find_product_url(site, brand, part)
            except Blocked as e:
                print("BLOCKED – stopping use of", site, "|", e)
                blocked_sites.add(site); continue
            if page:
                pw = parse_weight(page)
                if pw:
                    val, unit, label, raw = pw
                    lb = to_lb(val, unit)
                    result = [part, brand, site, url, raw, round(lb, 4), round(lb * 0.45359237, 4), label]
                    break
        # record the attempt (empty weight = not found) so a re-run skips it
        w.writerow(result or [part, brand, "", "", "", "", "", "not found"])
        out.flush()
        print(n, brand, part, "->", result[5] if result else "not found")
        if len(blocked_sites) == len(SITES):
            print("Both sites are blocking automated access from this machine. Stopping.")
            break
    out.close()
    try:
        from google.colab import files
        files.download(OUT)
    except Exception:
        pass

if __name__ == "__main__":
    main()
