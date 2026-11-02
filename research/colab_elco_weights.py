# ELCO Lighting – product-weight lookup on Build.com / FergusonHome.com (Google Colab, one cell)
# 1) Run the cell  2) Upload ELCO_Lighting.csv (from output/missing_weights_by_brand/)  3) elco_weights.csv downloads at the end
# Polite: obeys robots.txt, 1 request / DELAY s, stops a site on 403/CAPTCHA (no bypassing). Re-run to resume.

import csv, json, os, re, time, html, urllib.parse, urllib.robotparser, requests

SITES = ["https://www.build.com", "https://www.fergusonhome.com"]
DELAY = 8            # seconds between requests
MAX_PER_RUN = 500    # part numbers per run
OUT = "elco_weights.csv"
UA = "Mozilla/5.0 (compatible; elco-weight-research; contact: YOUR-EMAIL@example.com)"  # put your e-mail here

S = requests.Session(); S.headers.update({"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"})
class Blocked(Exception): pass
_rp, _last = {}, [0.0]

def allowed(url):
    base = "{0.scheme}://{0.netloc}".format(urllib.parse.urlparse(url))
    if base not in _rp:
        rp = urllib.robotparser.RobotFileParser()
        try:
            r = S.get(base + "/robots.txt", timeout=20)
            rp.parse(r.text.splitlines() if r.status_code == 200 else [])
        except Exception:
            rp.parse([])
        _rp[base] = rp
    return _rp[base].can_fetch(UA, url)

def get(url):
    if not allowed(url):
        print("  robots.txt disallows:", url); return None
    time.sleep(max(0, DELAY - (time.time() - _last[0])))
    for attempt in range(3):
        _last[0] = time.time()
        r = S.get(url, timeout=30)
        if r.status_code == 429:
            time.sleep(60 * (attempt + 1)); continue
        if r.status_code == 403 or re.search(r"captcha|just a moment|verify you are|access denied|px-captcha", r.text[:5000], re.I):
            raise Blocked(f"{r.status_code} {url}")
        return r if r.status_code == 200 else None
    return None

norm = lambda s: re.sub(r"[^A-Z0-9]", "", str(s).upper())

def parse_weight(page):
    for block in re.findall(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', page, re.S | re.I):
        try: data = json.loads(html.unescape(block))
        except Exception: continue
        for it in (data if isinstance(data, list) else [data]):
            if isinstance(it, dict) and it.get("weight"):
                w = it["weight"]; val = w.get("value") if isinstance(w, dict) else w
                unit = (w.get("unitText") or w.get("unitCode") or "lb") if isinstance(w, dict) else "lb"
                try: return float(val), unit, "JSON-LD weight"
                except Exception: pass
    text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html.unescape(page)))
    m = re.search(r"((?:product|item|shipping|ship|net|gross)?\s*weight)\s*(?:\(lbs?\.?\))?\s*:?\s*(\d+(?:\.\d+)?)\s*(lbs?|pounds?|oz|kg)?", text, re.I)
    if m: return float(m.group(2)), (m.group(3) or "lb"), m.group(1).strip()
    return None

def to_kg(v, u):
    u = u.lower()
    return v if u.startswith("kg") else v * 0.0283495 if u.startswith("oz") else v * 0.45359237

def lookup(site, part):
    r = get(f"{site}/search?term={urllib.parse.quote_plus('ELCO ' + part)}")
    if r is None: return None
    pages = [(r.url, r.text)] if norm(part) in norm(r.text) and "search" not in r.url else []
    if not pages:
        for href in dict.fromkeys(re.findall(r'href="(/[^"#?]*elco[^"#?]*/s\d+[^"]*)"', r.text, re.I))[:3]:
            p = get(site + href)
            if p is not None: pages.append((p.url, p.text))
    for url, page in pages:
        if norm(part) not in norm(page):      # exact part number must appear on the page
            continue
        w = parse_weight(page)
        if w: return url, w
    return None

# ---- input
try:
    from google.colab import files
    up = files.upload(); fn = list(up.keys())[0]
except Exception:
    fn = "ELCO_Lighting.csv"
parts = [r["Part Number"].strip() for r in csv.DictReader(open(fn, encoding="utf-8")) if r.get("Part Number")]
done = {r["part_number"] for r in csv.DictReader(open(OUT, encoding="utf-8"))} if os.path.exists(OUT) else set()
new = not os.path.exists(OUT)
out = open(OUT, "a", newline="", encoding="utf-8"); W = csv.writer(out)
if new: W.writerow(["part_number", "site", "url", "weight_value", "weight_unit", "weight_kg", "weight_label"])

blocked, n, found = set(), 0, 0
for part in parts:
    if part in done: continue
    if n >= MAX_PER_RUN or len(blocked) == len(SITES): break
    n += 1; res = None
    for site in SITES:
        if site in blocked: continue
        try:
            hit = lookup(site, part)
        except Blocked as e:
            print("BLOCKED – not using", site, "any more:", e); blocked.add(site); continue
        if hit:
            url, (val, unit, label) = hit
            res = [part, site, url, val, unit, round(to_kg(val, unit), 4), label]; break
    W.writerow(res or [part, "", "", "", "", "", "not found"]); out.flush()
    found += bool(res)
    print(f"{n}/{len(parts)-len(done)}  {part}  ->  {res[5] if res else 'not found'} kg")
out.close()
print(f"\nchecked {n}, found {found}" + ("  | both sites blocked this machine" if len(blocked) == len(SITES) else ""))
try: files.download(OUT)
except Exception: pass
