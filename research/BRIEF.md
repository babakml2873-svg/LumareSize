# Brief: exact product-weight harvesting (per SKU)

Goal: for every row in your assigned vendor CSV files, find the REAL published weight of that exact product
(exact manufacturer part number = `Variant SKU`, or the model number in `Title`) and record where it came from.
We currently only have rough category estimates. The user needs accurate per-SKU weights.

Input: /tmp/claude-0/-home-user-LumareSize/4bdae89e-be9f-5b88-bcfd-cb08e1ba615f/scratchpad/vendors/<Vendor>.csv
  columns: row_id, Handle, Vendor, Title, Type, Variant SKU, Option1 Name, Option1 Value, cls, pdf
  (`pdf` = an official spec-sheet URL for some products — use it when present; it is the manufacturer's document.)
  Some rows are finish/colour variants of one model — one lookup often covers several rows.

Output (write incrementally, append, so progress is never lost):
  /tmp/claude-0/-home-user-LumareSize/4bdae89e-be9f-5b88-bcfd-cb08e1ba615f/scratchpad/results/<your_group>.csv
  columns (header once): row_id,sku,weight_value,weight_unit,weight_kg,weight_type,source_type,source_name,url,match,notes
  - weight_type: net | shipping | unknown   (use the label the source uses: "Product weight"/"Net weight" = net;
    "Shipping weight"/"Gross"/"Carton"/"Package" = shipping; Shopify `grams` = shipping-ish -> "unknown" unless page says)
  - source_type: Manufacturer | Distributor | Retailer
  - match: exact (same part no.) | variant (same model, different finish/CCT suffix) — never record anything looser
  - If the product is a multi-pack/case (e.g. "Case of 12", "(100-Pack)"), record what the source states and say in notes
    whether the weight is per piece or per pack, and the pack qty.
  - Only rows you actually found. Don't write guesses. Don't write rows with no weight.

HARD RULES
- NEVER use Lumera Electric (lumeraelectric.com, Lumera-hosted pages, or the Lumera Shopify CDN cdn.shopify.com/s/files/1/0751/5455/4925/...) as a source. Also skip eBay/marketplace listings.
- Never invent a weight, URL or match. Every weight must be parsed from the page/PDF/JSON you actually fetched.
- Convert: 1 lb = 0.45359237 kg, 1 oz = 0.0283495 kg, g/1000.
- Sanity check: reject values clearly wrong for the product (e.g. 0, or a 2-inch trim at 40 lb).

HOW (network is open; Bash curl works, use a desktop browser User-Agent):
- Priority 1: manufacturer site / spec-sheet PDF / manufacturer data feed. Many manufacturer sites are Shopify: try
  https://<domain>/products.json?limit=250&page=N (variant `grams`, `sku`) and https://<domain>/products/<handle>.json.
  PDFs: curl then `pdftotext -layout` (check `which pdftotext`; else python pypdf/pdfminer if installed) and regex "Weight".
- If a site is merely JavaScript-rendered (no bot challenge), you may render it with the pre-installed Playwright Chromium
  or use its public JSON endpoints / sitemap.xml.
- DO NOT circumvent bot protection: if a site answers 403, a Cloudflare "Just a moment" challenge, CAPTCHA, or
  similar block, treat that site as unavailable and move to another source (spec-sheet PDFs, other distributors,
  search results). No header spoofing tricks, stealth plugins, challenge solving, or proxy rotation.
- Priority 2: distributors/retailers with the exact part number (e.g. homedepot.com product pages / its specification data,
  grainger.com, graybar.com, 1000bulbs.com, ferguson.com, platt, elliottelectric, northcoastelectric, lowes, build.com, lumens.com ...).
  Bing search via curl (https://www.bing.com/search?q=...) works for finding product URLs. Use WebSearch/WebFetch sparingly
  (shared budget across agents).
- Be polite: <= ~2 requests/second per host, add small sleeps, retry with backoff on 429.
- Work vendor by vendor, biggest first. Prefer methods that scale (feeds, APIs, sitemaps, systematic URL patterns) over
  one-at-a-time manual lookups. Write a reusable script in your own work dir:
  /tmp/claude-0/-home-user-LumareSize/4bdae89e-be9f-5b88-bcfd-cb08e1ba615f/scratchpad/agents/<your_group>/
  (keep downloaded files in a separate subfolder from your scripts; run python with -I).
- Keep going until you have covered as many rows as you can. If a vendor has no reachable weight source at all, say so
  clearly (which sites you tried and what blocked you) rather than stopping early on the other vendors.

Final reply: per vendor -> rows covered / total, sources used, blockers. Keep it short.
