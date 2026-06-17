# Maui County Document Harvest — Directory Map + Running Inventory

**Updated:** 2026-06-17 · **Guardrails:** sourced/cited only; law vs. opinion vs. analysis labeled; no private data; CPU/web only.
**Extraction calibration (important):**
- `web_fetch` **works** on ArchiveCenter `ViewFile/Item/<id>` PDFs and on **text-based** DocumentCenter PDFs (e.g., SMA Rules Ch. 302 extracted ~53KB).
- `web_fetch` returns **empty** on **scanned/OCR** DocumentCenter PDFs (e.g., AG Rules 115656, Civil-Fines 119602) → **BLOCKED, needs PDF drop or OCR.**
- Index pages (mauicounty.gov `Archive.aspx`, `2017/Planning-Regulations`) are **JS-rendered** → enumerate via Claude-in-Chrome, not raw web_fetch.

## Directory map (the universe)
### 1. Municode — Maui County Code Title 19 (canonical law; render via Chrome)
Root: https://library.municode.com/hi/county_of_maui/codes/code_of_ordinances?nodeId=TIT19ZO
- Art. II Comprehensive Zoning Provisions → district chapters incl. 19.04 (defs), 19.08, 19.29 (Rural ✓), 19.30A (Ag ✓), 19.31 (Public/Quasi-public), residential/business/apartment/industrial chapters, 19.36B (parking), 19.40 (conditional permits), 19.510 (special use permits), 19.64/19.65/19.67 (B&B/STR/home business)
- Art. V Administration & Enforcement → 19.500, 19.510, 19.520, **19.530 (Enforcement ✓)**

### 2. Planning Regulations index (admin rules) — https://www.mauicounty.gov/2017/Planning-Regulations
Links found (DocumentCenter):
- Agriculture Rules / "Rule Amendments for Ch. 19.30A" (AG, MC-12 Subtitle 01) — /DocumentCenter/View/115656/AG-RULES-FINAL-CLEAN — **OCR, BLOCKED**
- "Rules for Administrative Procedures and Civil Fines for Violations of Ch. 16.13 & Title 19" — /DocumentCenter/View/119602/... — **OCR, BLOCKED**
- Administrative Rules Title MC-12, Chapter 103 — /DocumentCenter/View/119602/12222019-Rule-Amendments-regarding-
- SMA Rules — Molokaʻi Ch. 302 — /DocumentCenter/View/4370/Chpt-302---SMA-Rules — **TEXT OK**
- SMA Rules — Lānaʻi Ch. 402 — /DocumentCenter/View/4151/Chpt-402--Lanai-Planning-Comm-SMA-Rules
- Shoreline Rules — Molokaʻi Ch. 304 — /DocumentCenter/View/4369/Chpt-304---Shoreline-Rules-
- Shoreline Rules — Lānaʻi Ch. 403 — /DocumentCenter/View/4152/Chpt-403---LPC-Shoreline-Setback-Rules
- (TO FIND: Maui SMA Rules Ch. 202 + Maui Shoreline Rules §12-5 — cited in the 2003 CC opinion; not in filtered list)

### 3. ArchiveCenter (JS index; enumerate via Chrome) — https://www.mauicounty.gov/Archive.aspx
- Item 288 = 2003 Corp. Counsel opinion (SMA/shoreline warnings) — **INGESTED ✓**
- (TO MAP: archive categories/AIDs → CC legal opinions, enforcement memos)

### 4. Title 19 Rewrite — https://www.t19rewrite.org (web_fetch OK)
- 2018 Title 19 Audit Report + Appendices — /uploads/1/3/2/7/132796325/mcc-title-19-zoning-audit-report-and-appendices-march-2018.pdf
- Sub-pages: project-info.html, code-draft.html, events.html, helpful-info.html, faq.html
- County draft TOC (DocumentCenter) — /DocumentCenter/View/121664/...Title-19-Rewrite-Project-Draft-Table-of-Contents

### 5. Community plans (8–9 areas) — mauicounty.gov + Municode §19.06.010 / Ch. 2.80B
- West Maui, Wailuku–Kahului, Kīhei–Mākena, Makawao–Pukalani–Kula, Pāʻia–Haʻikū, Hāna, Molokaʻi, Lānaʻi (+ Lāhainā recovery)

## Running inventory
| Item | Type | Status |
|---|---|---|
| MCC 19.30A Agricultural | law | INGESTED ✓ (cited, service §4A) |
| MCC 19.29 Rural | law | INGESTED ✓ (cited, service §4A-R) |
| MCC 19.530 Enforcement | law | INGESTED ✓ (cited, service §4B) |
| 2003 CC opinion (SMA/shoreline warnings, Item 288) | dated opinion | INGESTED ✓ |
| SMA Rules Molokaʻi Ch. 302 | rule | PULLED (text) — ingest pending |
| SMA Rules Lānaʻi Ch. 402 | rule | TO PULL |
| Shoreline Rules Molokaʻi Ch. 304 / Lānaʻi Ch. 403 | rule | TO PULL |
| AG Rules MC-12 (115656) | rule | BLOCKED (OCR — needs PDF drop) |
| Civil-Fines rules (119602) | rule | BLOCKED (OCR — needs PDF drop) |
| Maui SMA Ch. 202 + Maui Shoreline §12-5 | rule | TO FIND |
| 2018 Title 19 Audit | report | TO PULL |
| Remaining Title 19 districts + 19.04/19.36B/19.40/19.510 | law | EXPANDING |
| 8 community plans | plan | EXPANDING |
