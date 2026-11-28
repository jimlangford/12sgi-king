/* ============================================================
   govOS — Charter Government OS · data layer
   ------------------------------------------------------------
   The operating system of a charter government. Five civic loops,
   the departments (mapped to the 28-article Sovereign Charter),
   the live integrity watch fleet (kilo-aupuni), and the
   multi-jurisdiction tenancy model.

   Status vocabulary — honest about what exists:
     live    — running on the machine right now (watchers, feeds)
     built   — a surface exists in this project (links out)
     wired   — data pipeline exists; dedicated surface pending
     planned — designed, not yet built

   Snapshot: 2026-06-12. Only Maui County 001 is a real tenant;
   the other jurisdiction tiers are the instancing MODEL / roadmap.
   ============================================================ */
(function () {
  // The civic loop — the government's operating heartbeat.
  var LOOP = [
    { k: "forecast", nm: "Forecast", haw: "Nānā mua", glyph: "◷",
      d: "See what's coming. Sunshine Law (HRS §92-7) posts agendas ≥6 days out; bills run weeks. The queue is the calendar.",
      tool: "council-watch", status: "live", href: null },
    { k: "inform", nm: "Inform", haw: "Hoʻonaʻauao", glyph: "⚖",
      d: "Turn each item into facts — governing statute + dollars + charter article. No opinion, only record.",
      tool: "Charter ⇄ Law Crosswalk", status: "built", href: "../title19-crosswalk/Title19 Crosswalk.html" },
    { k: "decide", nm: "Decide", haw: "Hoʻoholo", glyph: "✋",
      d: "Testimony, council votes, moku approval, recusal tracking. The people and the law in the room.",
      tool: "votes-watch", status: "live", href: null },
    { k: "publish", nm: "Publish", haw: "Hoʻolaha", glyph: "📡",
      d: "Explainer videos + public record, 3–4 days before the vote, inside the testimony window.",
      tool: "Agenda Explainer", status: "built", href: "../agenda-explainer/Agenda Explainer.html" },
    { k: "audit", nm: "Audit", haw: "Loiloi", glyph: "🛡",
      d: "Glyph audit + watch fleet + RAIS ledger. Every claim carries its source. Correlations are questions.",
      tool: "14th Stone · kilo-aupuni", status: "live", href: null },
  ];

  // Departments / modules — grouped by branch, mapped to charter articles.
  var BRANCHES = [
    { id: "leg", nm: "Legislative & Direct Democracy", haw: "Ka ʻAha Kānāwai", modules: [
      { nm: "Council & Agendas", haw: "Ka ʻAha Kūkā", art: ["V", "XXVII"], law: "HRS §92 Sunshine · Charter Art.3", status: "live", metric: "38 agendas tracked", tool: "council-watch" },
      { nm: "Voting & Recusals", haw: "Koho Balota", art: ["V", "X"], law: "Charter Art.3 · HRS Ch.84 ethics", status: "live", metric: "9 officials · 1 recusal", tool: "votes-watch" },
      { nm: "Petition & Initiative", haw: "Ka Noi Kānāwai", art: ["XXVII"], law: "Charter Art.13 · HRS Ch.11", status: "planned", metric: "60% threshold", tool: null },
      { nm: "Agenda Explainer", haw: "Wehewehe ʻĀpana", art: ["XXVII", "XII"], law: "Sunshine §92-7 window", status: "built", metric: "forecast → fact-card video", tool: null, href: "../agenda-explainer/Agenda Explainer.html" },
      { nm: "County Code & Rules", haw: "Nā ʻĀpana Kānāwai", art: ["I", "V"], law: "MCC Titles 1–20 · Council Rules", status: "built", metric: "14 titles · 7 committees", tool: null, href: "../county-code/Maui County Code & Rules.html" },
      { nm: "State Law Index", haw: "Nā Kānāwai Mokuʻāina", art: ["I", "XI"], law: "Const. + HRS · the parent corpus", status: "built", metric: "18 articles · 28 HRS titles", tool: null, href: "../state-law/State of Hawaiʻi Law Index.html" },
    ] },
    { id: "fin", nm: "Executive & Finance", haw: "Ka Waihona Kālā", modules: [
      { nm: "Budget Transparency", haw: "Ka ʻOiaʻiʻo Kālā", art: ["X"], law: "Charter Art.9 · MCC Title 3", status: "built", metric: "FY2027 · $1.6B", tool: null, href: "../budget-transparency/Budget Transparency.html" },
      { nm: "Procurement & Bids", haw: "Nā Koina", art: ["X", "XVIII"], law: "HRS Ch.103D", status: "live", metric: "2,014 bids", tool: "bids-watch" },
      { nm: "Money Behind Officials", haw: "Ke Kālā Hūnā", art: ["X"], law: "HI CSC SODA · HRS Ch.11", status: "live", metric: "$256K RE/dev money", tool: "donor-watch" },
      { nm: "Generational Wealth Trust", haw: "Ka Waiwai Hanauna", art: ["XVIII"], law: "HRS Ch.103D · Ch.554", status: "planned", metric: "12.5% of contracts", tool: null },
    ] },
    { id: "land", nm: "Land, Water & Environment", haw: "Ka ʻĀina me ka Wai", modules: [
      { nm: "Charter ⇄ Law Crosswalk", haw: "Ke Kānāwai Pili", art: ["XI"], law: "MCC Title 19 · HRS Ch.205/205A", status: "built", metric: "28 arts · 6 law bodies", tool: null, href: "../title19-crosswalk/Title19 Crosswalk.html" },
      { nm: "Hawaiʻi County Crosswalk", haw: "HAW-002 · ⬢", art: ["XI", "XXIII"], law: "County Charter · HCC Ch.25 · HRS · Sovereign overlay", status: "built", metric: "13 functions · lava-hazard", tool: "HAW-002", href: "../hawaii-crosswalk/Hawaiʻi County Crosswalk.html" },
      { nm: "Permits & Land Use", haw: "Nā ʻAe Hana", art: ["XI"], law: "MCC Title 19 · §205A SMA", status: "live", metric: "834 permits/30d · 114 Lahaina", tool: "mapps-watch" },
      { nm: "Water Sovereignty", haw: "Wai Kapu", art: ["VI"], law: "HRS Ch.174C · Const XI §7", status: "wired", metric: "Bill 37 flagged", tool: "kilo-aupuni" },
      { nm: "Environmental Review", haw: "Ka Pono Kaiapuni", art: ["XVII"], law: "HRS Ch.343 · MCC Title 20", status: "planned", metric: "EIS pipeline", tool: null },
    ] },
    { id: "safe", nm: "Safety, Housing & Resilience", haw: "Ka Palekana", modules: [
      { nm: "Housing & Rebuild", haw: "Ka Hale Hoʻihoʻi", art: ["VIII"], law: "CDBG-DR 42 USC §5301 · Ch.201H", status: "wired", metric: "$1.639B · Bill 32 flagged", tool: "kilo-aupuni" },
      { nm: "Emergency & Fire", haw: "Ka Pio i ka Pōʻino", art: ["XXIII"], law: "HRS Ch.127A · MCC Title 16", status: "planned", metric: "firebreak · MEMA", tool: null },
      { nm: "Peacekeeper Network", haw: "Nā Kiai Maluhia", art: ["II"], law: "HRS Ch.52D · Charter Art.8", status: "planned", metric: "restorative", tool: null },
    ] },
    { id: "people", nm: "Culture, Justice & People", haw: "Ka Lāhui", modules: [
      { nm: "Sage Realm", haw: "Ka Pāʻani Naʻauao", art: ["XV", "XXVI"], law: "Sage Game canon · 54-node cosmology", status: "built", metric: "54 nodes · songs ↔ deck", tool: null, href: "../sage-realm/Sage Realm.html" },
      { nm: "Sacred Sites & Burial", haw: "Nā Wāhi Kapu", art: ["VII"], law: "HRS §6E-43.5 · NAGPRA", status: "planned", metric: "island burial councils", tool: null },
      { nm: "Restorative Justice", haw: "Hoʻoponopono", art: ["IX", "XIII"], law: "HRS Ch.706 · Ch.571", status: "planned", metric: "justice circles", tool: null },
      { nm: "Cultural Preservation", haw: "Ka Mālama Moʻomeheu", art: ["XV"], law: "HRS §5-7.5 · Const XV §4", status: "planned", metric: "ʻōlelo · hula · kapa", tool: null },
      { nm: "Healthcare Sovereignty", haw: "Ka Olakino", art: ["XXV"], law: "HRS Ch.321 · §453-2(b)(4)", status: "planned", metric: "lāʻau lapaʻau", tool: null },
    ] },
    { id: "rec", nm: "Records & Integrity", haw: "Ka Waihona ʻIke", modules: [
      { nm: "RAIS Ledger", haw: "Ka Puke Sovereign", art: ["XII", "XIV"], law: "HRS Ch.92F UIPA", status: "wired", metric: "agenda → scroll", tool: "RAIS" },
      { nm: "14th Stone Glyph Audit", haw: "Ka Pohaku ʻUmikūmāhā", art: ["XIV"], law: "facts + source · integrity gate", status: "wired", metric: "every output tagged", tool: "kilo-aupuni" },
      { nm: "Data Sovereignty", haw: "Ka ʻIkepili", art: ["XII", "XXI"], law: "HRS Ch.487N · Const I §6", status: "planned", metric: "privacy + custody", tool: null },
      { nm: "Personnel Digital Twin", haw: "Nā Kiaʻi Kikohoʻe", art: ["XIV", "XXI"], law: "votes-watch · dispatch · HRS Ch.76", status: "built", metric: "9 seats · 11 agents · owner console", tool: null },
    ] },
  ];

  // Kilo Aupuni — the live integrity watch fleet.
  var FLEET = [
    { nm: "council-watch", d: "CivicClerk agendas + money trail", metric: "38 agendas", status: "live" },
    { nm: "votes-watch", d: "minutes → votes & recusals", metric: "9 officials · 1 recusal", status: "live" },
    { nm: "mapps-watch", d: "EnerGov building permits", metric: "834 / 30d", status: "live" },
    { nm: "bids-watch", d: "county procurement bids", metric: "2,014 bids", status: "live" },
    { nm: "donor-watch", d: "HI CSC campaign finance", metric: "$256K tracked", status: "live" },
    { nm: "rpa-watch", d: "qPublic real-property assessments", metric: "qPublic 403", status: "planned" },
    { nm: "docs-watch", d: "official documents & filings", metric: "queued", status: "planned" },
  ];

  // Multi-jurisdiction tenancy — the State of Hawaiʻi is the parent (000); the
  // four counties instance beneath it: Maui 001 · Hawaiʻi 002 · Kauaʻi 003 ·
  // Honolulu 004. The same OS instances for any municipality by swapping its
  // charter, code, feeds, zones and seal (see TIERS for the general model).
  var TENANTS = [
    { id: "HI-000", nm: "State of Hawaiʻi", region: "USA", status: "active", seal: "✦", jtier: "state", parent: null,
      governing: "Governor + Lt. Governor · Legislature (25 Senate · 51 House) · Judiciary",
      charter: "Constitution of the State of Hawaiʻi (1959, amended)",
      code: "Hawaiʻi Revised Statutes + Hawaiʻi Administrative Rules",
      zones: "4 counties · State Land Use districts — Urban · Rural · Ag · Conservation",
      pop: "1,440,000", feed: "Capitol (legislature) · data.hawaii.gov · eHawaii",
      anchor: "Parent jurisdiction — Maui & Honolulu instance beneath it",
      bodies: ["Land Use Commission", "DLNR / BLNR", "Office of Hawaiian Affairs", "Public Utilities Commission", "Dept of Health", "Dept of Taxation", "Office of Planning & Sustainable Development"],
      legal: [["Haw. Const.", "State constitution — all articles"], ["HRS", "Hawaiʻi Revised Statutes"], ["HAR", "Administrative rules"], ["Ch.205", "State land use districts"], ["Ch.343", "Environmental impact statements"], ["Ch.92 / 92F", "Sunshine + UIPA"]],
      loads: [
        ["Charter", "Constitution of the State of Hawaiʻi"],
        ["Law crosswalk", "Hawaiʻi Revised Statutes + Administrative Rules"],
        ["Feed adapters", "Capitol · data.hawaii.gov · eHawaii"],
        ["Zones", "4 counties · State Land Use districts"],
        ["Seal & register", "✦ gold · ʻōlelo Hawaiʻi diacritics"],
      ] },
    { id: "MAU-001", nm: "Maui County", region: "Hawaiʻi, USA", status: "active", seal: "⚖", jtier: "county", parent: "HI-000",
      governing: "Mayor + Managing Director · County Council (9 residency seats) · 9 moku councils",
      charter: "12 Stones Sovereign Charter v5 · County Charter (1983)",
      code: "Maui County Code + Hawaiʻi Revised Statutes",
      zones: "Mauka · Kula · Makai", pop: "165,000", feed: "CivicClerk · EnerGov · HI CSC SODA", anchor: null,
      bodies: ["Dept of Planning", "Dept of Water Supply", "Fire & Public Safety / MEMA", "Housing & Human Concerns", "Cultural Resources Commission", "Dept of Finance"],
      legal: [["Charter", "County Charter (1983) + Sovereign Charter v5"], ["MCC", "Maui County Code Titles 1–20"], ["HRS", "Hawaiʻi Revised Statutes"], ["Ch.205A", "Coastal Zone / SMA"], ["§6E", "Historic preservation / burials"]],
      loads: [
        ["Charter", "12 Stones Sovereign Charter v5 + County Charter"],
        ["Law crosswalk", "Maui County Code + Hawaiʻi Revised Statutes"],
        ["Feed adapters", "CivicClerk · EnerGov · HI CSC SODA"],
        ["Zones", "Mauka · Kula · Makai"],
        ["Seal & register", "⚖ gold · ʻōlelo Hawaiʻi diacritics"],
      ] },
    { id: "HON-004", nm: "City & County of Honolulu", region: "Oʻahu, Hawaiʻi", status: "active", seal: "◈", jtier: "county", parent: "HI-000",
      governing: "Mayor + Managing Director · City Council (9 districts) · 33 Neighborhood Boards",
      charter: "Revised Charter of the City & County of Honolulu",
      code: "Revised Ordinances of Honolulu (ROH) + HRS · LUO Ch.21",
      zones: "8 community-plan areas — Primary Urban Center · ʻEwa · Central Oʻahu · East Honolulu · North Shore · Waiʻanae · Koʻolau Loa · Koʻolau Poko",
      pop: "1,000,000", feed: "Honolulu Granicus · DPP permits · honolulu.gov open data", anchor: null,
      bodies: ["Dept of Planning & Permitting (DPP)", "Board of Water Supply (BWS)", "HART — rail transit", "Honolulu Police / Fire", "Budget & Fiscal Services", "Ethics Commission"],
      legal: [["RCH", "Revised Charter of Honolulu"], ["ROH", "Revised Ordinances of Honolulu"], ["ROH Ch.21", "Land Use Ordinance (LUO)"], ["HRS Ch.205A", "Coastal Zone / SMA"], ["HRS Ch.46", "County powers"]],
      loads: [
        ["Charter", "Revised Charter of the City & County of Honolulu"],
        ["Law crosswalk", "Revised Ordinances of Honolulu (ROH) + HRS"],
        ["Feed adapters", "Honolulu Granicus · DPP · honolulu.gov open data"],
        ["Zones", "8 community-plan areas across Oʻahu"],
        ["Seal & register", "◈ gold · ʻōlelo Hawaiʻi diacritics"],
      ] },
    { id: "HAW-002", nm: "County of Hawaiʻi", region: "Hawaiʻi Island", status: "active", seal: "⬢", jtier: "county", parent: "HI-000",
      governing: "Mayor + Managing Director · County Council (9 districts) · seat at Hilo",
      charter: "Charter of the County of Hawaiʻi",
      code: "Hawaiʻi County Code + HRS · Zoning Ch.25",
      zones: "9 districts — Puna · Hilo · Hāmākua · N/S Kohala · N/S Kona · Kaʻū · lava-hazard overlay",
      pop: "200,000", feed: "Hawaiʻi County Granicus · ePlans · county open data", anchor: "Active Civil Defense — Kīlauea lava & tsunami hazard",
      bodies: ["Planning Dept", "Dept of Water Supply", "Fire Dept", "Police Dept", "Civil Defense Agency", "Environmental Management"],
      legal: [["Charter", "Charter of the County of Hawaiʻi"], ["HCC", "Hawaiʻi County Code"], ["HCC Ch.25", "Zoning"], ["HRS Ch.205A", "Coastal Zone / SMA"], ["§6E", "Historic preservation"]],
      loads: [
        ["Charter", "Charter of the County of Hawaiʻi"],
        ["Law crosswalk", "Hawaiʻi County Code + HRS"],
        ["Feed adapters", "Hawaiʻi County Granicus · ePlans · open data"],
        ["Zones", "9 council districts · lava-hazard overlay"],
        ["Seal & register", "⬢ gold · ʻōlelo Hawaiʻi diacritics"],
      ] },
    { id: "KAU-003", nm: "County of Kauaʻi", region: "Kauaʻi & Niʻihau", status: "active", seal: "❖", jtier: "county", parent: "HI-000",
      governing: "Mayor + Managing Director · County Council (7 at-large) · seat at Līhuʻe",
      charter: "Charter of the County of Kauaʻi",
      code: "Kauaʻi County Code (1987) + HRS · Comprehensive Zoning Ordinance",
      zones: "Districts — Waimea · Kōloa · Līhuʻe · Kawaihau · Hanalei · heavy SMA shoreline",
      pop: "73,000", feed: "Kauaʻi County Granicus · Planning Dept · open data", anchor: null,
      bodies: ["Planning Dept", "Dept of Water", "Fire Dept", "Police Dept", "Office of Economic Development", "Civil Defense Agency"],
      legal: [["Charter", "Charter of the County of Kauaʻi"], ["KCC", "Kauaʻi County Code (1987)"], ["CZO", "Comprehensive Zoning Ordinance"], ["HRS Ch.205A", "Coastal Zone / SMA"], ["§6E", "Historic preservation"]],
      loads: [
        ["Charter", "Charter of the County of Kauaʻi"],
        ["Law crosswalk", "Kauaʻi County Code + HRS"],
        ["Feed adapters", "Kauaʻi County Granicus · Planning · open data"],
        ["Zones", "5 districts · SMA shoreline overlay"],
        ["Seal & register", "❖ gold · ʻōlelo Hawaiʻi diacritics"],
      ] },
    { id: "NY-000", nm: "State of New York", region: "USA", status: "model", seal: "⬥", jtier: "state", parent: null,
      governing: "Governor + Lt. Governor · Legislature (63 Senate · 150 Assembly) · Judiciary",
      charter: "Constitution of the State of New York (1894, amended)",
      code: "NY Consolidated Laws + NYCRR (administrative rules)",
      zones: "62 counties · 932 towns · 62 cities · villages", pop: "19,600,000",
      feed: "data.ny.gov (Socrata) · NYSenate API · NYS Board of Elections · OpenStates", anchor: "Second-state instance — proves the OS scales beyond Hawaiʻi",
      bodies: ["Dept of State", "Board of Elections", "Comptroller (Open Book NY)", "Dept of Environmental Conservation", "Attorney General"],
      legal: [["NY Const.", "State constitution"], ["Consolidated Laws", "all NY statutes"], ["NYCRR", "administrative rules"], ["POL Art.7", "Open Meetings Law"], ["POL Art.6", "FOIL — public records"]],
      loads: [
        ["Charter", "Constitution of the State of New York"],
        ["Law crosswalk", "NY Consolidated Laws + NYCRR"],
        ["Feed adapters", "data.ny.gov (Socrata) · NYSenate API · NYSBOE · OpenStates"],
        ["Zones", "62 counties · towns · cities · villages"],
        ["Seal & register", "⬥ slate · English · Open Meetings + FOIL"],
      ] },
    { id: "NYC-001", nm: "City of New York", region: "New York, USA", status: "model", seal: "◈", jtier: "city-county", parent: "NY-000",
      governing: "Mayor · City Council (51 districts) · 5 borough presidents · 59 community boards",
      charter: "New York City Charter",
      code: "NYC Administrative Code + Rules of the City of NY (RCNY) · Zoning Resolution",
      zones: "5 boroughs · 59 community districts · the Zoning Resolution", pop: "8,300,000",
      feed: "data.cityofnewyork.us (Socrata · 1 of the largest) · NYC Council Legistar · NYC Campaign Finance Board · Checkbook NYC", anchor: "Largest US municipal open-data portal — plugs into our Socrata + Legistar adapters as-is",
      bodies: ["City Planning (DCP)", "Dept of Buildings", "Campaign Finance Board", "Comptroller (Checkbook NYC)", "Conflicts of Interest Board", "Dept of Investigation"],
      legal: [["NYC Charter", "New York City Charter"], ["Admin Code", "NYC Administrative Code"], ["RCNY", "Rules of the City of NY"], ["Zoning Resolution", "land use"], ["POL Art.6/7", "FOIL + Open Meetings"]],
      loads: [
        ["Charter", "New York City Charter"],
        ["Law crosswalk", "NYC Administrative Code + Zoning Resolution"],
        ["Feed adapters", "NYC Open Data (Socrata) · Council Legistar · CFB · Checkbook NYC"],
        ["Zones", "5 boroughs · 59 community districts"],
        ["Seal & register", "◈ slate · English · FOIL + Open Meetings"],
      ] },
    { id: "NY-LIV-002", nm: "Village of Liverpool", region: "New York, USA", status: "provisioning", seal: "◆", jtier: "municipal", parent: "NY-000",
      governing: "Mayor + Board of Trustees (4) · Village Clerk-Treasurer",
      charter: "NY Municipal Home Rule (Const. Art. IX) · Village Law",
      code: "Village of Liverpool Code + NY Consolidated Laws",
      zones: "Village · Town of Salina · Onondaga County", pop: "2,400",
      feed: "Village clerk · Onondaga County · NYS Open Data", anchor: "American High Studios — former A.V. Zogg School · ties to 12sgi Film",
      bodies: ["Village Board of Trustees", "Planning Board", "Zoning Board of Appeals", "Code Enforcement", "Village Clerk-Treasurer"],
      legal: [["MHRL", "NY Municipal Home Rule Law"], ["Village Law", "NY Village Law Art. 7 (zoning)"], ["Liverpool Code", "Village local laws"], ["POL Art.7", "Open Meetings Law"], ["POL Art.6", "FOIL"]],
      loads: [
        ["Charter", "NY Municipal Home Rule Law · Village Law Art. 7"],
        ["Law crosswalk", "Village of Liverpool Code + NY Consolidated Laws"],
        ["Feed adapters", "Village clerk · NYS Open Data · Onondaga GIS"],
        ["Zones", "Village · Town of Salina · Onondaga County"],
        ["Seal & register", "◆ slate · English · Open Meetings + FOIL"],
      ] },
  ];
  var TIERS = [
    { tier: "T0", nm: "State tier", ex: "State of Hawaiʻi (000) — live parent jurisdiction", model: "constitution + HRS + HAR · counties instance beneath", status: "live" },
    { tier: "T1", nm: "Hawaiʻi counties", ex: "All 4 — Maui (001) · Hawaiʻi (002) · Kauaʻi (003) · Honolulu (004)", model: "same HRS spine · swap county code + charter", status: "live" },
    { tier: "T2", nm: "Out-of-state instances", ex: "New York (000) · NYC (001) · Liverpool (002) — Socrata + Legistar adapters plug in as-is", model: "swap state statutes + local code + home-rule charter", status: "model" },
    { tier: "T3", nm: "Global charter jurisdictions", ex: "indigenous & sovereign bodies", model: "swap legal corpus + zones + seal · UNDRIP layer", status: "model" },
  ];

  window.GOVOS = {
    meta: { snapshot: "2026-06-12", version: "v4.1.0", tenant: "MAU-001" },
    loop: LOOP, branches: BRANCHES, fleet: FLEET, tenants: TENANTS, tiers: TIERS,
  };
})();
