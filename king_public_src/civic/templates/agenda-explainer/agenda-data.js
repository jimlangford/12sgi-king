/* ============================================================
   govOS · Agenda Explainer — data layer
   ------------------------------------------------------------
   Turns a forecast agenda item into a ready-to-render fact-card
   storyboard. Facts assemble from the Charter ⇄ Law Crosswalk
   (governing statute), the council-watch money trail (dollars),
   and the Sunshine Law clock (HRS §92-7 — agendas post ≥6 days
   before a meeting; publish the explainer inside that window so
   the public can still testify).

   Integrity: every card carries its source. Correlations are
   questions, never accusations. Hydrates from council-watch when
   the feed is reachable; else this dated snapshot stands.
   Snapshot: 2026-06-12.
   ============================================================ */
(function () {
  // Forecast queue — upcoming items, ranked by public stakes.
  // `meeting` is the decision date; `days` is days out (Sunshine clock).
  var ITEMS = [
    { id: "I-37", file: "CivicClerk 5901", title: "Bill 37 — $25M water sovereignty fund", body: "Water, Infrastructure & Transportation Cmte", type: "water",
      meeting: "2026-06-18", days: 6, stake: 5, charter: "VI", status: "forecast",
      decision: "Establishes a $25M county fund for water-system acquisition and management. The fund's governance structure decides whether a public-trust resource stays in public hands.",
      law: [["HRS Ch.174C", "State Water Code"], ["Haw. Const. Art.XI §7", "Public trust in water (Waiāhole)"], ["MCC Title 14", "Dept. of Water Supply"]],
      money: "$25,000,000", moneyNote: "general fund appropriation",
      conflict: "Flagged: fund structure raises a public-trust question — needs the ordinance text to resolve. Not an accusation.",
      testify: "Written testimony via mauicounty.us eComment, or testify in person / online — by meeting start, 9:00 AM.",
      clips: ["ʻīao stream", "Nā Wai ʻEhā", "council chambers"] },
    { id: "I-55", file: "CivicClerk 5893", title: "Bills 55–56 — FY2027 county budget adoption", body: "Budget, Finance & Economic Development Cmte", type: "budget",
      meeting: "2026-06-20", days: 8, stake: 5, charter: "X", status: "forecast",
      decision: "Final adoption of the $1.6B FY2027 budget — $1.2B operating + $351M CIP. Passed 2nd & final reading 06-05; ordinance text now posting for the penny-level dept re-parse.",
      law: [["Charter Art.9", "Financial procedures & budget"], ["MCC Title 3", "Revenue & taxation"], ["HRS Ch.46", "County budget powers"]],
      money: "$1,600,000,000", moneyNote: "$1.2B operating · $351M CIP · −$8.4M vs Mayor's proposal",
      conflict: null,
      testify: "Budget already adopted at 2nd reading — track the Mayor's signature (effective 07-01). Implementation testimony at dept level.",
      clips: ["budget binder", "Kalana O Maui", "resident b-roll"] },
    { id: "I-SMA", file: "CivicClerk 5907", title: "SMA use permit — Makai coastal parcel", body: "Housing & Land Use Cmte", type: "zoning",
      meeting: "2026-06-25", days: 13, stake: 4, charter: "XI", status: "forecast",
      decision: "Special Management Area use permit for development within the shoreline zone. Triggers charter Art.XI review and moku approval before ground is touched.",
      law: [["MCC §19.510", "Special Management Area (SMA)"], ["HRS Ch.205A", "Coastal Zone Management"], ["HRS Ch.343", "Environmental impact statements"]],
      money: "—", moneyNote: "permit action — no appropriation",
      conflict: null,
      testify: "Written testimony to the HLU committee via eComment, or testify in person / online before the hearing.",
      clips: ["shoreline", "SMA boundary map", "reef"] },
    { id: "I-32", file: "CivicClerk 5888", title: "Bill 32 — CDBG-DR Lahaina recovery allocation", body: "Disaster, Resilience & Recovery Cmte", type: "housing",
      meeting: "2026-06-27", days: 15, stake: 5, charter: "VIII", status: "forecast",
      decision: "Allocation within the $1.639B federal CDBG-DR block grant for Lahaina rebuild. Decides which recovery activities are funded and whether they meet federal eligibility.",
      law: [["42 USC §5301", "HCDA / CDBG-DR §105(a) eligible activities"], ["HRS Ch.201H", "Affordable housing"], ["MCC Ch.2.96", "Residential workforce housing"]],
      money: "$1,639,000,000", moneyNote: "federal block grant · HUD",
      conflict: "Flagged: FarmBox shelter eligibility under §105(a) pending HUD read. Reso 25-80 cross-referenced.",
      testify: "Written testimony to the DRR committee via eComment; recovery-affected residents prioritized for in-person testimony.",
      clips: ["Lahaina rebuild", "FarmBox shelter", "ʻohana"] },
    { id: "I-PRM", file: "EnerGov batch", title: "Building-permit batch — 114 Lahaina parcels", body: "Dept. of Planning · administrative", type: "permit",
      meeting: "2026-06-16", days: 4, stake: 3, charter: "XI", status: "forecast",
      decision: "Administrative release of 114 Lahaina rebuild permits (of 834 county-wide in 30 days). Charter Art.XI clearance precedes deployment-adjacent parcels.",
      law: [["MCC Title 19", "Comprehensive zoning"], ["MCC Title 16", "Building & construction"], ["§205A SMA", "Coastal parcels"]],
      money: "—", moneyNote: "permit fees only",
      conflict: null,
      testify: "Administrative action — comment via the Planning Dept. permit portal; appeals through the Planning Commission.",
      clips: ["permit counter", "rebuild site", "map overlay"] },
  ];

  // Storyboard card recipe — the order of shots in every explainer.
  var RECIPE = ["hook", "what", "law", "money", "stakes", "deadline", "cta"];

  // Platform render targets. YouTube + TikTok are the active push channels
  // (APPROVED 06-12); Canvas is passive reach.
  var PLATFORMS = [
    { id: "youtube", nm: "YouTube Short", spec: "9:16 · ≤60s", handle: "Jimmy Langford · 62 subs", ops: "YouTube ops · daily 6:30a · OAuth self-heal", status: "automated", note: "watch-hours = the Partner lever" },
    { id: "tiktok", nm: "TikTok", spec: "9:16 · ≤60s", handle: "@jimmylangfordofficial", ops: "tiktok-ops · Playwright draft-push · 3 slots/day", status: "staged", note: "~2/3 of discovery starts here" },
    { id: "canvas", nm: "Spotify Canvas", spec: "9:16 · 8s loop", handle: "artist · 19 listeners", ops: "manual upload", status: "passive", note: "passive reach" },
  ];

  // Render → publish pipeline for a single explainer.
  var PIPELINE = [
    { step: "Storyboard", d: "fact cards from this item", tool: "Agenda Explainer", status: "ready" },
    { step: "Render", d: "9:16 MP4 · govOS motion template", tool: "render lane", status: "queued" },
    { step: "Caption", d: "burned-in captions + hook", tool: "clip_forge", status: "queued" },
    { step: "Publish", d: "push to YouTube + TikTok", tool: "YouTube ops · tiktok-ops", status: "queued" },
  ];

  window.AGENDA = {
    meta: { snapshot: "2026-06-12", feed: "../_feed/agendas.json", sunshine: "HRS §92-7 · ≥6 days notice" },
    items: ITEMS, recipe: RECIPE, platforms: PLATFORMS, pipeline: PIPELINE,
  };
})();
