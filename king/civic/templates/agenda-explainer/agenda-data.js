/* ============================================================
   govOS · Agenda Explainer — data layer
   ------------------------------------------------------------
   Today's CURRENT Maui County Council committee agenda,
   turned into plain-language fact-cards (what it is, the law it
   touches, the dollars, the deadline, and how to testify).

   Every item is sourced from the official meeting notice posted
   on Legistar (mauicounty.legistar.com) and linked to its
   committee page on mauicounty.us. Facts only — the "what to
   ask" line is a neutral question for testimony, never an
   accusation. Where a detail isn't in the agenda, we link to the
   source instead of inventing it.

   Snapshot: 2026-07-06 · TODAY — Housing and Land Use Committee
   reconvened from 7/1/2026 · 10:30 a.m. · Council Chamber, 8th Flr.
   Source: Maui County Legistar calendar (mauicounty.legistar.com).
   ============================================================ */
(function () {
  // Today's queue — current committee items, sorted by the Sunshine clock.
  // `meeting` is the decision/hearing date; `days` is days out from snapshot.
  // `cite` is the official agenda item reference; `url` is the committee page.
  var ITEMS = [
    { id: "HLU-reconvene-20260706",
      cite: "HLU · Reconvened from 7/1/2026", file: "Legistar · HLU",
      url: "https://mauicounty.legistar.com/Calendar.aspx",
      title: "Housing & Land Use Committee — reconvened meeting",
      body: "Housing & Land Use Cmte (2025-2027) · Chair Uʻu-Hodgins · reconvened from 7/1/2026",
      type: "zoning", meeting: "2026-07-06", days: 0, stake: 4, status: "today",
      hook: "Maui's Housing & Land Use Committee meets again today",
      decision: "The Housing and Land Use Committee reconvenes this morning at 10:30 a.m. from its July 1, 2026 meeting. The committee is continuing work on housing and land use matters from the July 1 agenda — which includes the ongoing briefing series on the Title 19 zoning code rewrite (first briefed June 17) and any additional housing bills referred to the committee. Reconvened meetings take up items left unfinished or recessed from the original session; the full item list is on the official Legistar meeting page. No new items may be added to a reconvened meeting.",
      law: [["MCC Title 19", "comprehensive zoning code — rewrite project ongoing"], ["HRS §92-7", "Sunshine Law — 6-day notice requirement for committee meetings"], ["Council Rule 7(B)", "informational presentations and briefings"]],
      money: "—", moneyNote: "no appropriation known from the reconvene notice; check Legistar for any bill texts",
      ask: "What items from the July 1 agenda remain unresolved, and will the committee vote or continue to present? For the Title 19 rewrite: when will the public get to comment on specific zone changes before any text is adopted?",
      testify: "Oral testimony in person at the Council Chamber, Kalana O Maui Building, 8th Floor, 200 S. High Street, Wailuku — or via Microsoft Teams (link posted on Legistar meeting page). Written testimony: HLU.committee@mauicounty.us. Reconvened meetings accept testimony on the reconvened items. Deadline: contact the Council Services staff at councilservices@mauicounty.us to confirm testimony window.",
      clips: ["Housing & Land Use", "Title 19 / zoning", "Wailuku / council chambers"] },

    { id: "HLU-title19-context",
      cite: "HLU-3(5) → HLU-3(6) · Title 19 rewrite series", file: "Legistar · HLU",
      url: "https://www.mauicounty.us/HLU",
      title: "Context: Title 19 zoning code rewrite — the ongoing series",
      body: "Housing & Land Use Cmte · background item for today's reconvened session",
      type: "zoning", meeting: "2026-07-06", days: 0, stake: 5, status: "context",
      hook: "Why does Title 19 matter?",
      decision: "Title 19 of the Maui County Code is the comprehensive zoning ordinance — it governs what can be built, where, and at what density across the entire island. The Planning Department's rewrite project is the most significant land-use overhaul in a generation. The June 17 briefing (HLU-3(5)) was the committee's first formal presentation on the project scope and timeline. Today's reconvened session continues that work. Any new zoning map or text will ultimately require multiple public hearings before adoption.",
      law: [["MCC Title 19", "comprehensive zoning code — full text at mauicounty.us/planning"], ["HRS §205A", "coastal zone management (relevant to shoreline zoning)"], ["HRS §46-4", "county zoning authority"]],
      money: "—", moneyNote: "planning dept. staff time; no known appropriation in the briefing phase",
      ask: "Which neighborhoods and zoning districts are changing first? Is the rewrite adding housing capacity in areas near transit and jobs, or locking in existing exclusions? How will affected landowners and renters be notified?",
      testify: "The rewrite is in the briefing phase — no vote on specific language today. Written comment to the Planning Department: planning.dept@mauicounty.us. Oral testimony at HLU committee hearings on specific bills once introduced. Watch Legistar for hearing notices.",
      clips: ["zoning map overlay", "Maui towns", "planning dept. / Wailuku"] },
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
    meta: {
      snapshot: "2026-07-06",
      week: "Jul 6, 2026 · Housing & Land Use Committee reconvene",
      feed: "../_feed/agendas.json",
      sunshine: "HRS §92-7 · ≥6 days notice",
      today: true,
      meeting_time: "10:30 a.m.",
      meeting_body: "Housing and Land Use Committee",
      meeting_location: "Council Chamber, Kalana O Maui Bldg., 8th Flr. · 200 S. High St., Wailuku",
      legistar_calendar: "https://mauicounty.legistar.com/Calendar.aspx",
    },
    items: ITEMS, recipe: RECIPE, platforms: PLATFORMS, pipeline: PIPELINE,
  };
})();
