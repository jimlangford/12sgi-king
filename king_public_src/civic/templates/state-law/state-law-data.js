/* ============================================================
   State of Hawaiʻi · Law Index — data layer
   ------------------------------------------------------------
   The PARENT corpus every Hawaiʻi county inherits: the State
   Constitution and the Hawaiʻi Revised Statutes (HRS), organized
   by division. Counties (Maui 001, Honolulu 003, Hawaiʻi 004,
   Kauaʻi 005) operate UNDER this — Const. Art. VIII (home rule)
   + HRS Title 6 (county organization) grant the charter + code
   each county lays on top.

   HONEST FRAMING: a structural index, not a reproduction. HRS is
   28 titles in 5 divisions; the civic-load-bearing titles are
   detailed here with their key chapters. Chapter text + current
   amendments hydrate from the State feed (Capitol / data.hawaii.gov).
   `inherit:true` = a title counties directly operate under.
   Snapshot: 2026-06-12.
   ============================================================ */
(function () {
  // Constitution of the State of Hawaiʻi — 18 articles.
  var CONST = [
    { n: "I", t: "Bill of Rights", note: "Due process, privacy (§6), equal protection" },
    { n: "II", t: "Suffrage & Elections", note: "Voting; political power in the people" },
    { n: "III", t: "The Legislature", note: "Senate (25) + House (51); lawmaking" },
    { n: "IV", t: "Reapportionment", note: "Decennial redistricting" },
    { n: "V", t: "The Executive", note: "Governor & Lieutenant Governor" },
    { n: "VI", t: "The Judiciary", note: "Supreme, intermediate, circuit, district courts" },
    { n: "VII", t: "Taxation & Finance", note: "Budget, debt, public funds" },
    { n: "VIII", t: "Local Government", note: "Home rule — counties' charter power", inherit: true },
    { n: "IX", t: "Public Health & Welfare", note: "Housing, health, public assistance" },
    { n: "X", t: "Education", note: "Statewide DOE; UH; Hawaiian education (§4)" },
    { n: "XI", t: "Conservation & Resources", note: "Public trust; water (§7); clean environment (§9)", inherit: true },
    { n: "XII", t: "Hawaiian Affairs", note: "Hawaiian Homes; OHA; customary rights (§7)", inherit: true },
    { n: "XIII", t: "Organization; Collective Bargaining", note: "Public-employee unions" },
    { n: "XIV", t: "Code of Ethics", note: "Conflict of interest; standards of conduct" },
    { n: "XV", t: "Boundaries; Capital; Flag; Language", note: "Hawaiian & English official (§4)" },
    { n: "XVI", t: "General & Miscellaneous", note: "Civil service; oaths; severability" },
    { n: "XVII", t: "Revision & Amendment", note: "Constitutional convention; amendment" },
    { n: "XVIII", t: "Schedule", note: "Transitional provisions" },
  ];

  // HRS — 5 divisions. Civic-load-bearing titles detailed; key chapters listed.
  var DIVISIONS = [
    { nm: "Division 1 · Government", titles: [
      { n: "1", nm: "General Provisions", ch: "Ch.1 common law / §1-1 Hawaiian usage · Ch.6E historic preservation · §5-7.5 Aloha Spirit", inherit: true },
      { n: "2", nm: "Elections", ch: "Ch.11–19 · elections, campaign finance", inherit: false },
      { n: "3", nm: "Legislature", ch: "Ch.21 organization · Ch.23G", inherit: false },
      { n: "4", nm: "State Organization & Administration", ch: "Ch.26 departments · Ch.28 AG", inherit: false },
      { n: "5", nm: "State Financial Administration", ch: "Ch.36–40 budget, funds, audit", inherit: false },
      { n: "6", nm: "County Organization & Administration", ch: "Ch.46 county powers (§46-1.5) · Ch.50 charters", inherit: true, key: true },
      { n: "7", nm: "Public Officers & Employees", ch: "Ch.76 civil service · Ch.84 ethics", inherit: true },
      { n: "8", nm: "Public Proceedings & Records", ch: "Ch.91 HAPA · Ch.92 Sunshine · Ch.92F UIPA", inherit: true, key: true },
      { n: "9", nm: "Public Property, Purchasing & Contracting", ch: "Ch.103D Procurement Code", inherit: true },
      { n: "10", nm: "Public Safety & Internal Security", ch: "Ch.127A emergency management", inherit: true },
    ] },
    { nm: "Division 2 · Business", titles: [
      { n: "11", nm: "Agriculture & Animals", ch: "Ch.141 Dept of Ag · Ch.149A pesticides", inherit: false },
      { n: "12", nm: "Conservation & Resources", ch: "Ch.171 public lands · Ch.174C Water Code · Ch.183 forests · Ch.195D endangered species", inherit: true, key: true },
      { n: "13", nm: "Planning & Economic Development", ch: "Ch.205 land use · Ch.205A Coastal Zone/SMA · Ch.226 state planning · Ch.343 EIS", inherit: true, key: true },
      { n: "14", nm: "Taxation", ch: "Ch.235 income · Ch.237 general excise (GET) · Ch.246 real property → counties", inherit: true },
      { n: "15", nm: "Transportation & Utilities", ch: "Ch.269 PUC · Ch.261 aeronautics", inherit: false },
      { n: "16", nm: "Intoxicating Liquor", ch: "Ch.281 county liquor commissions", inherit: true },
      { n: "17", nm: "Motor & Other Vehicles", ch: "Ch.286–291 vehicles, traffic", inherit: false },
    ] },
    { nm: "Division 3 · Property; Family", titles: [
      { n: "18", nm: "Property", ch: "Ch.501 land court · Ch.502 recording · Ch.514B condos · Ch.521 landlord-tenant", inherit: false },
      { n: "19", nm: "Health", ch: "Ch.321 Dept of Health · §453-2 lāʻau lapaʻau", inherit: false },
      { n: "20", nm: "Social Services", ch: "Ch.346 Human Services · Ch.349 aging", inherit: false },
      { n: "21", nm: "Labor & Industrial Relations", ch: "Ch.371 labor · Ch.386 workers' comp", inherit: false },
      { n: "—", nm: "Hawaiian affairs (across titles)", ch: "Ch.10 OHA · Hawaiian Homes Commission Act · §7-1 kuleana access", inherit: true, key: true },
    ] },
    { nm: "Division 4 · Courts & Judicial Proceedings", titles: [
      { n: "31", nm: "Courts & Judicial Proceedings", ch: "Ch.601 judiciary · Ch.603 circuit · Ch.604 district · Ch.658A arbitration", inherit: false },
    ] },
    { nm: "Division 5 · Crimes & Criminal Proceedings", titles: [
      { n: "37", nm: "Hawaiʻi Penal Code", ch: "Ch.701–712 penal code · Ch.706 sentencing · Ch.853 deferral", inherit: false },
    ] },
  ];

  // How the counties inherit the parent corpus.
  var INHERIT = [
    { k: "Constitution", d: "Art. VIII (home rule) + Art. XI (public trust) + Art. XII (Hawaiian rights) bind every county" },
    { k: "HRS Title 6", d: "Ch.46 grants county powers; Ch.50 governs charter formation & amendment" },
    { k: "HRS spine", d: "Sunshine (Ch.92), UIPA (Ch.92F), Procurement (Ch.103D), Land Use (Ch.205/205A), Water (Ch.174C) apply statewide" },
    { k: "County charter", d: "each county adopts its own home-rule charter (Maui · Honolulu RCH · Hawaiʻi · Kauaʻi)" },
    { k: "County code", d: "MCC · ROH · Hawaiʻi County Code · Kauaʻi County Code lay local law on top" },
    { k: "Sovereign overlay", d: "the 12 Stones Sovereign Charter v5 layers above as the MauiOS governance frame" },
  ];

  window.STATELAW = {
    meta: {
      snapshot: "2026-06-12", feed: "../_feed/agendas.json", jurisdiction: "HI-000",
      note: "Structural index of the parent corpus. HRS is 28 titles in 5 divisions; civic-load-bearing titles are detailed with key chapters. Chapter text + amendments via the State feed (Capitol · data.hawaii.gov).",
      counties: ["MAU-001", "HON-003", "HAW-004", "KAU-005"],
    },
    constitution: CONST, divisions: DIVISIONS, inherit: INHERIT,
    har: "Hawaiʻi Administrative Rules (HAR) — agency rules implementing HRS: e.g. HAR Title 13 (DLNR), Title 11 (Health), Title 15 (Planning / Land Use Commission).",
  };
})();
