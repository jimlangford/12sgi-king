# Maui County Code — Full Inventory (all titles) + Harvest Status

**Updated:** 2026-06-17 · **Scope:** entire MCC + department administrative rules (digital-twin corpus). **Priority:** Title 19 / agriculture / enforcement (in progress); rest mapped + expanding.
**Source of record:** Municode — https://library.municode.com/hi/county_of_maui/codes/code_of_ordinances
**Coordination:** A "County digital-twin architecture" session (local_b2a380ef) is defining the reusable service-module schema + MCC/county-services inventory. **No schema has been posted to the dispatch log yet.** Per-title backups below use the established interoperable header format (Title / SOURCE URL / RETRIEVED / TYPE) and are deliberately schema-agnostic so they drop into whatever module schema local_b2a380ef finalizes — **provisional pending that schema; do not fork.**

## MCC titles (17) — status
| Title | Name | Status | Notes |
|---|---|---|---|
| 1 | General Provisions | mapped / expanding | code adoption & construction |
| 2 | Administration & Personnel | mapped / expanding | depts, boards/commissions, Planning Commission (2.28), General Plan (2.80B) |
| 3 | Revenue & Finance | mapped / expanding | budget, real property tax |
| 5 | Business Licenses & Regulations | mapped / expanding | incl. STR/TVR licensing cross-refs |
| 6 | Animals | mapped / expanding | |
| 8 | Health & Safety | mapped / expanding | **reached by 19.530.030 enforcement** |
| 9 | Public Peace, Morals & Welfare | mapped / expanding | |
| 10 | Vehicles & Traffic | mapped / expanding | |
| 11 | Public Transit | mapped / expanding | |
| 12 | Streets, Sidewalks & Public Places | mapped / expanding | **reached by 19.530.030** |
| 13 | Parks & Recreation | mapped / expanding | |
| 14 | Public Services | mapped / expanding | **reached by 19.530.030** (water/sewer) |
| 16 | Buildings & Construction | mapped / expanding | **reached by 19.530.030**; incl. 16.13 (cross-ref of Civil-Fines rules) |
| 18 | Subdivisions | mapped / expanding | **reached by 19.530.030**; tied to 19.30A subdivision limits |
| 19 | **Zoning** | **PARTIAL — INGESTED** | 19.30A (Ag) ✓, 19.29 (Rural) ✓, 19.530 (Enforcement) ✓; other chapters expanding |
| 20 | Environmental Protection | mapped / expanding | **reached by 19.530.030**; 20.08.260 (1%-of-project-cost fine ref) |
| 22 | Department of Agriculture | mapped / expanding | ag-priority — ingest next |

## Administrative rules (Title MC-12, Dept of Planning, + others)
| Rule | Ch. | Status |
|---|---|---|
| AG district admin rules ("Rules re: Administration of Ch. 19.30A") | MC-12 Subtitle 01, **Ch. 102** | **INGESTED ✓** (backup: corpus/raw/county_docs/ag_district_admin_rules_ch102.md; eff. 2019-01-06; §§12-102-1..-11; Declaration req §12-102-4; appeal to BVA §12-102-11; no penalty section) |
| SMA Rules — Molokaʻi | Ch. 302 | PULLED ✓ (backup saved; enforcement §12-302-23/-24; fine ≤$100,000 + ≤$10,000/day) |
| SMA Rules — Lānaʻi | Ch. 402 | PULLED ✓ (§§12-402-23/-24/-27; ≤$100,000 + ≤$10,000/day) |
| Shoreline Rules — Molokaʻi | Ch. 304 | PULLED ✓ (§12-304-14; ≤$100,000 + ≤$10,000/day) |
| Shoreline Setback Rules — Lānaʻi | Ch. 403 | PULLED ✓ (§§12-403-20/-23; ≤$10,000 + ≤$1,000/day) |
| Civil-Fines rule — **Rule §15-2** (Admin Procedures & Civil Fines for Violations of Titles 16, 18 & 19) | MC-15 Ch. 2 | **INGESTED ✓** (sourced via View/149499, text; full fine schedule §15-2-9; eff. 1993; Imp MCC §19.530.030. Supersedes OCR-blocked View/119602). Cross-tagged Titles 16/18/19. |
| Maui SMA Rules — **Ch. 202** | MC-12 Ch. 202 | **INGESTED ✓** (View/8413; §12-202-23/-25 am&comp 08/25/2024: ≤$100,000 + ≤$10,000/day; partly supersedes 2003 CC opinion) |
| Maui Shoreline Rules (§12-5) | — | TO FIND (older set; cited in 2003 CC opinion) |

## ArchiveCenter categories (legal opinions & boards) — AMID index
Corporation Counsel Legal Opinions **AMID=173** · Maui Planning Commission 85 · Molokaʻi PC 87 · Lānaʻi PC 74 · Board of Variances & Appeals 42 · Board of Code Appeals 40 · Board of Ethics 41 · Departmental Public Hearings 191 · (138 categories total; Council Land Use cmte 78/77/76/75/188/197/210/219/237; Planning cmte 94/93/92/91/184/198/211/223/238). Item 288 (2003 SMA-warnings opinion) ingested ✓.

## Extraction routes (calibrated)
- Municode code text → Claude-in-Chrome render + JS extract.
- ArchiveCenter `ViewFile/Item/<id>` + text DocumentCenter PDFs → `web_fetch`.
- Scanned/OCR DocumentCenter PDFs → BLOCKED (need PDF drop). Index pages (Archive.aspx, Regulations) → Chrome.
