/* ============================================================
   govOS · Agenda Explainer — data layer
   ------------------------------------------------------------
   This week's CURRENT Maui County Council committee agendas,
   turned into plain-language fact-cards (what it is, the law it
   touches, the dollars, the deadline, and how to testify).

   Every item is sourced from the official meeting agenda posted
   on Legistar (mauicounty.legistar.com) and linked to its
   committee page on mauicounty.us. Facts only — the "what to
   ask" line is a neutral question for testimony, never an
   accusation. Where a detail isn't in the agenda, we link to the
   source instead of inventing it.

   Snapshot: 2026-06-15 · week of Mon Jun 15 – Wed Jun 17, 2026.
   Source: Maui County Council committee meeting notices (Legistar).
   ============================================================ */
(function () {
  // This week's queue — current committee items, sorted by the Sunshine clock.
  // `meeting` is the decision/hearing date; `days` is days out from the snapshot.
  // `cite` is the official agenda item number; `url` is the committee page.
  var ITEMS = [
    { id: "WASSP-11", cite: "WASSP-11 · Bill 77 (2026)", file: "Legistar · WASSP", url: "https://www.mauicounty.us/WASSP",
      title: "Bill 77 — Affordable Housing Fund for the unhoused", body: "Water Authority, Social Services & Parks Cmte · Chair Sinenci",
      type: "housing", meeting: "2026-06-15", days: 0, stake: 5, status: "current",
      hook: "Should the Housing Fund pay for the unhoused?",
      decision: "Bill 77 would require a portion of the county's Affordable Housing Fund to be used to systemically address housing needs and provide “suitable living environments” for County residents who are houseless. The committee may recommend it for first reading (with or without revisions), or file it.",
      law: [["MCC · Affordable Housing Fund", "county housing trust fund"], ["Bill 77 (2026)", "proposed ordinance — see agenda for full text"]],
      money: "—", moneyNote: "redirects a share of an existing fund — the amount is set in the bill text",
      ask: "How large a share of the fund would be redirected, and what counts as a “suitable living environment”? Would this add capacity or move money away from other affordable-housing projects?",
      testify: "Written testimony via eComment at mauicounty.us/agendas (search June 15) or WASSP.committee@mauicounty.us. Oral testimony in person (Council Chamber, 8th Flr.) or online via Teams — 3 min/item.",
      clips: ["kūpuna / housing", "Wailuku", "council chambers"] },

    { id: "WAI-24", cite: "WAI-24 · Bill 68 (2026)", file: "Legistar · WAI", url: "https://www.mauicounty.us/WAI",
      title: "Bill 68 — Special parking regulations (West & South Maui)", body: "Water & Infrastructure Cmte · Chair Cook",
      type: "permit", meeting: "2026-06-15", days: 0, stake: 3, status: "current",
      hook: "Paid parking coming to West Maui?",
      decision: "Bill 68 would amend Title 10, Article II of the Maui County Code to: (1) authorize paid-parking and permit-parking zones in West Maui; (2) create “Resident Town Benefit” locations in paid-parking zones in Wailuku and West Maui; (3) change Resident Recreation Hours locations at South Maui beach-park paid-parking zones; and (4) remove outdated references to parking lots, piers, and loading zones in West Maui. First reading.",
      law: [["MCC Title 10, Art. II", "special parking regulations"]],
      money: "—", moneyNote: "parking-policy change — no appropriation in the bill",
      ask: "Who qualifies for the resident exemptions, and how would paid zones affect everyday resident access to beaches and town parking?",
      testify: "Written testimony via eComment at mauicounty.us/agendas (search June 15) or WAI.committee@mauicounty.us. Oral testimony in person or via Teams — 3 min/item.",
      clips: ["West Maui parking", "beach access", "Wailuku town"] },

    { id: "BFED-61", cite: "BFED-61 · Reso 26-100", file: "Legistar · BFED", url: "https://www.mauicounty.us/BFED",
      title: "Reso 26-100 — $9.0M energy-performance lease (Johnson Controls)", body: "Budget, Finance & Economic Development Cmte · Chair Sugimura",
      type: "budget", meeting: "2026-06-16", days: 1, stake: 4, status: "current",
      hook: "$9M to cut the county's energy bills?",
      decision: "Resolution 26-100 would authorize a tax-exempt lease-purchase agreement, through TD Equipment Finance, Inc., for Phase 3 of the county's energy-performance contract with Johnson Controls, Inc., under HRS §36-41 — $9,021,259 for the work, plus interest at 4.49%. The committee may recommend adoption (with or without revisions), or file it.",
      law: [["HRS §36-41", "tax-exempt lease-purchase financing"]],
      money: "$9,021,259", moneyNote: "Phase 3 work · + 4.49% interest · via TD Equipment Finance",
      ask: "What energy savings does Phase 3 promise, and over how many years? Would the projected utility-bill reduction cover the financing cost and interest?",
      testify: "Written testimony via eComment at mauicounty.us/agendas (search June 16) or BFED.committee@mauicounty.us. Oral testimony in person or via Teams — 3 min/item.",
      clips: ["county buildings", "HVAC / solar retrofit", "ledger"] },

    { id: "BFED-58", cite: "BFED-58 · Bill 73 (2026)", file: "Legistar · BFED", url: "https://www.mauicounty.us/BFED",
      title: "Bill 73 — Uniform rules for the county Grants Program", body: "Budget, Finance & Economic Development Cmte · Chair Sugimura",
      type: "budget", meeting: "2026-06-16", days: 1, stake: 3, status: "current",
      hook: "Standard rules for county grants?",
      decision: "Bill 73 would amend MCC §3.36.020 to require the county to adopt uniform, countywide administrative rules (under HRS Chapter 91) for the Maui County Grants Program, while still letting grant-accepting agencies keep supplemental internal policies that don't conflict with those rules. First reading.",
      law: [["MCC §3.36.020", "Maui County Grants Program"], ["HRS Ch. 91", "administrative rulemaking"]],
      money: "—", moneyNote: "process / governance change — no appropriation",
      ask: "Would uniform Chapter 91 rules make grant awards more transparent and consistent, or add steps that slow funding to community nonprofits?",
      testify: "Written testimony via eComment at mauicounty.us/agendas (search June 16) or BFED.committee@mauicounty.us. Oral testimony in person or via Teams — 3 min/item.",
      clips: ["grant paperwork", "nonprofit", "Kalana O Maui"] },

    { id: "GREAT-10", cite: "GREAT-10 · 14 charter amendments", file: "Legistar · GREAT", url: "https://www.mauicounty.us/GREAT",
      title: "14 proposed Charter amendments for the ballot", body: "Government Relations, Ethics & Transparency Cmte · Chair Batangan · reconvened from 6/2",
      type: "gov", meeting: "2026-06-16", days: 1, stake: 5, status: "current",
      hook: "14 changes to the County Charter — onto your ballot?",
      decision: "The committee is weighing 14 resolutions that would each place a proposed Maui County Charter amendment on the next General Election ballot for voters to decide. They include: modernizing public-meeting notice to the Sunshine Law and dropping the newspaper-notice requirement (25-215); standardizing deadlines for voter initiative, recall and charter amendments (25-216); computation of time (25-217); filing injury/property claims directly with Corporation Counsel (26-61); special elections to fill council vacancies (26-11); removing the English translation of the state motto from the preamble (26-85); publishing bill digests online instead of in a newspaper (26-94); staggering Cost of Government Commission terms (26-86); one successive reappointment for Board of Ethics members (26-95); a Climate Action & Resiliency Revolving Fund of at least 20% of hotel-tax (TAT) revenue (26-87); using the Open Space / Natural / Cultural Resources / Scenic Views Preservation Fund for wildfire fuel-hazard removal (24-100); dissolving the Independent Nomination Board (26-93); and emergency-appropriation and appropriation-transfer changes (26-88, 26-89).",
      law: [["Maui County Charter (1983)", "14 amendments — placed on the ballot for voter ratification"], ["HRS §92", "Sunshine Law (Reso 25-215)"]],
      money: "—", moneyNote: "ballot questions — Reso 26-87 would dedicate ≥20% of TAT revenue to a climate fund if passed",
      ask: "Which of these 14 belong on your ballot? The highest-stakes are 26-87 (≥20% of hotel-tax revenue to a climate fund) and 26-93 (dissolving the Independent Nomination Board) — do they widen or narrow public oversight?",
      testify: "Written testimony via eComment at mauicounty.us/agendas (search June 16) or GREAT.committee@mauicounty.us. Oral testimony in person or via Teams — 3 min/item.",
      clips: ["ballot box", "county charter", "council chambers"] },

    { id: "HLU-3(5)", cite: "HLU-3(5) · Title 19 rewrite", file: "Legistar · HLU", url: "https://www.mauicounty.us/HLU",
      title: "Title 19 zoning rewrite — Planning Dept. briefing", body: "Housing & Land Use Cmte · Chair Uʻu-Hodgins",
      type: "zoning", meeting: "2026-06-17", days: 2, stake: 4, status: "current",
      hook: "Rewriting Maui's zoning code",
      decision: "Under Council Rule 7(B), the Department of Planning will brief the committee on its project to modernize and rewrite Maui County Code Title 19 (zoning). This meeting is a presentation and discussion only — no legislative action will be taken.",
      law: [["MCC Title 19", "comprehensive zoning code"], ["Council Rule 7(B)", "informational presentation"]],
      money: "—", moneyNote: "informational briefing — no appropriation",
      ask: "What is actually changing in the zoning rewrite, and when will the public get to weigh in on specific districts before any new code is adopted?",
      testify: "Written testimony via eComment at mauicounty.us/agendas (search June 17) or HLU.committee@mauicounty.us. Oral testimony in person or via Teams — 3 min/item.",
      clips: ["zoning map", "Maui towns", "planning dept."] },

    { id: "DRIP-9(4)", cite: "DRIP-9(4) · long-term recovery", file: "Legistar · DRIP", url: "https://www.mauicounty.us/DRIP",
      title: "Long-term recovery & the 2026 Kona Low storms", body: "Disaster Recovery, International Affairs & Planning Cmte · Chair Paltin",
      type: "housing", meeting: "2026-06-17", days: 2, stake: 4, status: "current",
      hook: "Where does Kona Low storm recovery stand?",
      decision: "Under Council Rule 7(B), the Office of Recovery and the U.S. Small Business Administration will brief the committee on Maui's long-term recovery operations, with emphasis on recovery from the 2026 Kona Low storms — including disaster assistance for homeowners, renters, businesses, and nonprofits. Presentation and discussion only — no legislative action.",
      law: [["Council Rule 7(B)", "informational presentation"], ["U.S. Small Business Administration", "federal disaster-assistance programs"]],
      money: "—", moneyNote: "briefing — federal disaster assistance discussed, not appropriated here",
      ask: "Where does long-term recovery stand for Kona Low storm survivors, and what SBA or county help is still open to homeowners, renters, and small businesses?",
      testify: "Written testimony via eComment at mauicounty.us/agendas (search June 17) or DRIP.committee@mauicounty.us. Oral testimony in person or via Teams — 3 min/item.",
      clips: ["storm damage", "recovery / SBA", "East Maui"] },
  ];

  // Storyboard card recipe — the order of shots in every explainer.
  var RECIPE = ["hook", "what", "law", "money", "stakes", "deadline", "cta"];

  // Platform render targets. YouTube + TikTok are the active push channels;
  // Canvas is passive reach.
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
    meta: { snapshot: "2026-06-15", week: "Jun 15–17, 2026", feed: "../_feed/agendas.json", sunshine: "HRS §92-7 · ≥6 days notice" },
    items: ITEMS, recipe: RECIPE, platforms: PLATFORMS, pipeline: PIPELINE,
  };
})();
