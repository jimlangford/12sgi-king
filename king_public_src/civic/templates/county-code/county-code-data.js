/* ============================================================
   govOS · Maui County Code & Rules — data layer
   ------------------------------------------------------------
   Structural coverage of Maui County law: the Code's titles, the
   Council's standing committees and rules, and the ordinance feed.

   HONEST FRAMING: this is a COVERAGE INDEX, not a reproduction of
   the code. Title names reflect the published structure; chapter
   detail and current amendments hydrate from the live feed —
   confirm a citation against the source before relying on it. The
   section-level citation engine is the Charter ⇄ Law Crosswalk;
   this surface tracks how much of each title that engine has
   mapped, plus the committee + rules machinery around it.

   `cov`:  mapped  — crosswalked at section level
           partial — some sections crosswalked
           indexed — listed, detail pending from feed
   Snapshot: 2026-06-12.
   ============================================================ */
(function () {
  // Maui County Code — published title structure (non-contiguous numbering
  // is the code's own). Detail + amendments via feed.
  var TITLES = [
    { n: "1",  nm: "General Provisions",            cov: "mapped",  art: ["I"],            note: "Code adoption, construction, general penalty" },
    { n: "2",  nm: "Administration & Personnel",    cov: "partial", art: ["V", "XXI"],     note: "Council, Mayor, boards & commissions, civil service, §2.80B Cultural Resources Cmn" },
    { n: "3",  nm: "Revenue & Taxation",            cov: "mapped",  art: ["X", "XVIII"],   note: "§3.48 Real property tax, fuel & TAT" },
    { n: "5",  nm: "Business Licenses & Regulation", cov: "indexed", art: [],              note: "Licensing, peddlers, regulated trades" },
    { n: "8",  nm: "Health & Sanitation",           cov: "indexed", art: ["XXV"],          note: "Sanitation, nuisances, public health" },
    { n: "10", nm: "Vehicles & Traffic",            cov: "indexed", art: [],               note: "Traffic code, parking, ROW use" },
    { n: "12", nm: "Streets, Sidewalks & Public Places", cov: "partial", art: ["XXI"],    note: "ROW, encroachment, public infrastructure" },
    { n: "13", nm: "Public Services & Utilities",   cov: "indexed", art: ["XXII"],         note: "Utility franchises, services" },
    { n: "14", nm: "Department of Water Supply",    cov: "mapped",  art: ["VI"],           note: "Water rates, service, system rules" },
    { n: "15", nm: "Building & Construction Codes",  cov: "partial", art: ["VIII"],        note: "Building, electrical, plumbing, energy codes" },
    { n: "16", nm: "Buildings & Fire Protection",   cov: "partial", art: ["VIII", "XXIII"], note: "Construction & fire-code provisions" },
    { n: "18", nm: "Subdivision",                   cov: "mapped",  art: ["XI"],           note: "Subdivision standards, lot creation" },
    { n: "19", nm: "Comprehensive Zoning",          cov: "mapped",  art: ["XI", "XVI"],    note: "Districts, §19.04 defs, §19.510 SMA — Title 19 rewrite, 97 scrolls" },
    { n: "20", nm: "Environmental Protection",      cov: "mapped",  art: ["XVII"],         note: "Erosion, grading, environmental standards" },
  ];

  // Council standing committees — subject-matter jurisdiction. Names rotate
  // each Council term; confirm current names/chairs via council-watch.
  var COMMITTEES = [
    { ab: "BFED", nm: "Budget, Finance & Economic Development", juris: "Budget, taxation, procurement, economic policy", art: ["X", "XVIII"], xref: "MCC Title 3 · HRS Ch.103D" },
    { ab: "HLU",  nm: "Housing & Land Use",                     juris: "Zoning, subdivision, SMA, housing, planning", art: ["VIII", "XI"], xref: "MCC Title 19/18 · HRS Ch.205A" },
    { ab: "WIT",  nm: "Water, Infrastructure & Transportation", juris: "Water supply, ROW, utilities, transit", art: ["VI", "XXI"], xref: "MCC Title 14 · HRS Ch.174C" },
    { ab: "DRR",  nm: "Disaster, Resilience & Recovery",        juris: "Emergency mgmt, Lahaina recovery, CDBG-DR", art: ["VIII", "XXIII"], xref: "HRS Ch.127A · 42 USC §5301" },
    { ab: "GET",  nm: "Governance, Ethics & Transparency",      juris: "Charter, ethics, open records, rules", art: ["V", "XXVII"], xref: "HRS Ch.84/92/92F" },
    { ab: "APT",  nm: "Agriculture, Environment & Public Trust", juris: "Ag lands, water trust, environment, parks", art: ["XVI", "XVII", "XX"], xref: "HRS §205-41 · Ch.343" },
    { ab: "HCC",  nm: "Human Concerns & Culture",               juris: "Health, kūpuna, youth, culture, sacred sites", art: ["VII", "XV", "XXVI"], xref: "HRS Ch.6E · §5-7.5" },
  ];

  // Rules of the Council — the procedural machinery (Rules adopted each term).
  var RULES = [
    { nm: "Organization & officers", d: "Chair, vice-chair, presiding rules, quorum", law: "Charter Art.3" },
    { nm: "Committee referral", d: "Every measure referred to a standing committee before floor action", law: "Council Rules" },
    { nm: "Agenda & posting", d: "Agendas posted ≥6 calendar days before meeting", law: "HRS §92-7 (Sunshine)" },
    { nm: "Public testimony", d: "Written eComment + in-person/online; recorded into the record", law: "HRS §92 · Council Rules" },
    { nm: "Voting & readings", d: "Two readings for ordinances; majority / supermajority thresholds", law: "Charter Art.3" },
    { nm: "Recusal & ethics", d: "Conflict-of-interest disclosure and recusal on the record", law: "HRS Ch.84 · MCC §2 ethics" },
    { nm: "Reconsideration & amendment", d: "Motions to reconsider, amend, defer, continue", law: "Council Rules" },
  ];

  // Ordinance / bill ledger — recent measures (full book via feed).
  var ORDS = [
    { id: "Bill 55–56", t: "FY2027 county budget", body: "BFED", date: "2026-06-05", status: "passed 2nd reading", art: "X" },
    { id: "Bill 37", t: "$25M water sovereignty fund", body: "WIT", date: "forecast 06-18", status: "flagged", art: "VI" },
    { id: "Bill 32", t: "CDBG-DR Lahaina recovery", body: "DRR", date: "forecast 06-27", status: "flagged", art: "VIII" },
    { id: "Reso 25-80", t: "Recovery resolution", body: "DRR", date: "active", status: "cross-referenced", art: "VIII" },
    { id: "Bill 9", t: "(realtor-PAC linkage)", body: "HLU", date: "2026-06-11", status: "dead", art: "XVI" },
  ];

  window.COUNTYCODE = {
    meta: { snapshot: "2026-06-12", feed: "../_feed/agendas.json",
      note: "Coverage index — title names reflect the published code; chapter detail & amendments hydrate from the live feed. The section-level citation engine is the Charter ⇄ Law Crosswalk." },
    titles: TITLES, committees: COMMITTEES, rules: RULES, ords: ORDS,
  };
})();
