/* ============================================================
   County of Hawaiʻi · Charter ⇄ Code Crosswalk — data layer
   ------------------------------------------------------------
   The Charter of the County of Hawaiʻi mapped against the Hawaiʻi
   County Code (HCC), Hawaiʻi Revised Statutes (HRS), the State
   Constitution, and — as the top overlay — the 12 Stones Sovereign
   Charter article each function answers to.

   Same engine as Maui's Title 19 crosswalk, instanced for HAW-002.
   The County Charter is organized by its functional articles
   (powers · council · executive · departments · planning · water ·
   safety · civil defense · finance · personnel · direct democracy ·
   amendment). Exact article numbers track the published charter;
   chapter detail hydrates from the State feed. Conflicts hydrate
   from the Hawaiʻi County feed (agendas-HAW-002.json).

   Distinctive to Hawaiʻi Island: an active Civil Defense Agency
   (Kīlauea lava + tsunami) and lava-hazard zoning overlays.
   Snapshot: 2026-06-12.
   ============================================================ */
(function () {
  var BODIES = [
    { id: "charter",   label: "County Charter",        short: "Charter",   color: "#d9b24c", src: "Charter of the County of Hawaiʻi" },
    { id: "hcc",       label: "Hawaiʻi County Code",    short: "HCC",       color: "#c9943f", src: "Hawaiʻi County Code · Municode" },
    { id: "hrs",       label: "Hawaiʻi Revised Statutes", short: "HRS",     color: "#3a8fb7", src: "capitol.hawaii.gov" },
    { id: "const",     label: "Hawaiʻi Constitution",   short: "Const",     color: "#3f9b6d", src: "Constitution of the State of Hawaiʻi" },
    { id: "sovereign", label: "Sovereign Charter overlay", short: "Sov",    color: "#9b7bb8", src: "12 Stones Sovereign Charter v5" },
    { id: "ord",       label: "Ordinances & Bills",     short: "Ord",       color: "#d9622b", src: "Hawaiʻi County Council · Granicus", live: true },
    // --- the sovereign hierarchy above the State (inherited from each function's mapped charter article) ---
    { id: "fed",       label: "U.S. Federal",           short: "Fed",       color: "#a07850", src: "U.S. Code & federal statutes" },
    { id: "intl",      label: "International Law",       short: "Int'l",     color: "#5fa8a0", src: "UN treaties & instruments" },
    { id: "icc",       label: "Int'l Criminal Court",   short: "ICC",       color: "#b0566e", src: "Rome Statute · ICC" },
    { id: "icj",       label: "Int'l Court of Justice", short: "ICJ",       color: "#7b86c4", src: "Statute of the ICJ" },
    { id: "holysee",   label: "Holy See · Canon Law",   short: "Holy See",  color: "#c9b38a", src: "Holy See · Canon Law" },
  ];

  // Charter functions → law. `sov` = the Sovereign overlay article.
  var FUNCS = [
    { n: "1", t: "Powers & General Provisions", h: "Ka Mana Kūikawā", s: "active", sov: "I",
      desc: "The county's home-rule powers and the supremacy of the charter over county operations.",
      cites: { charter: [["Art.1", "Powers of the county"]], hcc: [["Title 1", "General provisions"]], hrs: [["§46-1.5", "General powers of counties"], ["Ch.50", "County charters"]], const: [["Art.VIII §1-2", "Local government / home rule"]], sovereign: [["Art.I", "Foundation & Supremacy"]], ord: [] } },
    { n: "2", t: "The Council", h: "Ka ʻAha Kūkā", s: "active", sov: "V",
      desc: "Nine-member County Council (by district); legislative authority; seat at Hilo. Open-meetings law governs every agenda.",
      cites: { charter: [["Art.2", "The Council"]], hcc: [["Council Rules", "Standing committees"]], hrs: [["Ch.46", "County organization"], ["Ch.92", "Sunshine Law"]], const: [["Art.VIII", "Local government"]], sovereign: [["Art.V", "Moku Council Governance"], ["Art.XXVII", "Petition & Direct Democracy"]], ord: [] } },
    { n: "3", t: "Executive — Mayor", h: "Ka Luna Hoʻokō", s: "active", sov: "I",
      desc: "Mayor + Managing Director; executes county law and the budget across all departments.",
      cites: { charter: [["Art.3", "Executive branch"], ["Art.4", "Managing Director"]], hcc: [], hrs: [["Ch.46", "County powers"]], const: [["Art.VIII", "Local government"]], sovereign: [["Art.I", "Foundation"]], ord: [] } },
    { n: "5", t: "Planning & Land Use", h: "Ka Hoʻolālā ʻĀina", s: "active", sov: "XI", anchor: true,
      desc: "THE LAND-USE ANCHOR. Planning Dept + Windward/Leeward Planning Commissions; the island General Plan; zoning under HCC Chapter 25. Lava-hazard zones overlay every entitlement.",
      cites: { charter: [["Art.5", "Department of Planning"], ["", "Planning Commissions"]], hcc: [["Ch.25", "Zoning"], ["", "General Plan · CDPs"]], hrs: [["Ch.205", "State land use districts"], ["Ch.205A", "Coastal Zone / SMA"], ["Ch.343", "Environmental impact statements"]], const: [["Art.XI §1", "Conservation & public trust"]], sovereign: [["Art.XI", "Land Use & Zoning"], ["Art.XVI", "Food Sovereignty"]], ord: [["STVR rules", "vacation-rental zoning — forecast"]] } },
    { n: "6", t: "Water Supply", h: "Wai Kapu", s: "alert", sov: "VI",
      desc: "Semi-autonomous Department of Water Supply + Board; water held in public trust under the State Water Code.",
      cites: { charter: [["Art.6", "Dept. of Water Supply"]], hcc: [["Water rules", "Rates & service"]], hrs: [["Ch.174C", "State Water Code"], ["§174C-101", "Native Hawaiian water rights"]], const: [["Art.XI §7", "Public trust in water"]], sovereign: [["Art.VI", "Wai Kapu — Water Sovereignty"]], ord: [["Water CIP", "system capital plan — forecast"]] } },
    { n: "7", t: "Public Works & Infrastructure", h: "Ka Hana Lehulehu", s: "active", sov: "XXI",
      desc: "Roads, facilities, solid waste, and rights-of-way across the largest land area of any county.",
      cites: { charter: [["Art.7", "Public Works"]], hcc: [["Title 14", "Public works"]], hrs: [["Ch.264", "Highways"]], const: [], sovereign: [["Art.XXI", "Digital Infrastructure"]], ord: [] } },
    { n: "8", t: "Finance & Budget", h: "Ka ʻOiaʻiʻo Kālā", s: "active", sov: "X",
      desc: "Department of Finance; real-property tax; procurement; the annual budget and CIP.",
      cites: { charter: [["Art.8", "Financial procedures"]], hcc: [["Title 2", "Real property tax & finance"]], hrs: [["Ch.103D", "Procurement Code"], ["Ch.46", "County budget"]], const: [["Art.VII", "Taxation & finance"]], sovereign: [["Art.X", "Budget Transparency"], ["Art.XVIII", "Generational Wealth Trust"]], ord: [["GET surcharge", "transportation CIP — forecast"]] } },
    { n: "9", t: "Police & Fire", h: "Nā Kiai Maluhia", s: "active", sov: "II",
      desc: "Police Dept (under Police Commission) and Fire Dept; community safety across rural districts.",
      cites: { charter: [["Art.9", "Police & Fire departments"]], hcc: [], hrs: [["Ch.52D", "County police departments"]], const: [["Art.I §5", "Due process"]], sovereign: [["Art.II", "Peacekeeper Network"]], ord: [] } },
    { n: "10", t: "Civil Defense & Emergency", h: "Ka Pio i ka Pōʻino", s: "alert", sov: "XXIII", anchor: true,
      desc: "DISTINCTIVE TO HAWAIʻI ISLAND. Active Civil Defense Agency — Kīlauea lava flows (2018 LERZ), tsunami, and hurricane. Emergency powers under the State emergency-management act.",
      cites: { charter: [["Art.10", "Civil Defense Agency"]], hcc: [["Emergency", "Hazard mitigation"]], hrs: [["Ch.127A", "Emergency management"]], const: [], sovereign: [["Art.XXIII", "Emergency & Disaster"]], fed: [], ord: [["Lava recovery", "Zone 1/2 rebuild policy — forecast"]] } },
    { n: "11", t: "Environmental Management", h: "Ka Pono Kaiapuni", s: "pending", sov: "XVII",
      desc: "Solid waste, recycling, geothermal oversight (Puna), and environmental review.",
      cites: { charter: [["Art.11", "Environmental Management"]], hcc: [["Ch.20", "Environmental"]], hrs: [["Ch.343", "EIS"], ["Ch.342", "Environmental quality"]], const: [["Art.XI §9", "Clean & healthful environment"]], sovereign: [["Art.XVII", "Environmental Justice"], ["Art.XXII", "Renewable Energy"]], ord: [["Geothermal", "Puna relicensing — forecast"]] } },
    { n: "12", t: "Personnel & Civil Service", h: "Nā Limahana", s: "active", sov: "XXI",
      desc: "Merit-based civil service; collective bargaining under State law.",
      cites: { charter: [["Art.12", "Personnel"]], hcc: [], hrs: [["Ch.76", "Civil service"], ["Ch.89", "Collective bargaining"]], const: [["Art.XIII", "Collective bargaining"]], sovereign: [["Art.XXI", "Digital Infrastructure"]], ord: [] } },
    { n: "13", t: "Initiative, Referendum & Recall", h: "Ka Noi Kānāwai", s: "active", sov: "XXVII",
      desc: "Direct-democracy instruments reserved to the people of the county.",
      cites: { charter: [["Art.13", "Initiative, referendum & recall"]], hcc: [], hrs: [["Ch.11", "Elections"]], const: [["Art.I §1", "Political power in the people"]], sovereign: [["Art.XXVII", "Petition & Direct Democracy"]], ord: [] } },
    { n: "14", t: "Charter Amendment", h: "Ka Hoʻololi Kumukānāwai", s: "pending", sov: "XXVIII",
      desc: "Charter Commission and amendment process; the charter as a living instrument.",
      cites: { charter: [["Art.14", "Charter amendment & commission"]], hcc: [], hrs: [["Ch.50", "County charters — amendment"]], const: [["Art.XVII", "Revision & amendment"]], sovereign: [["Art.XXVIII", "Living Scroll Amendment"]], ord: [] } },
  ];

  /* ---- Supranational tier (real instruments). Each Hawaiʻi County function INHERITS the
     correspondences of the 12 Stones Sovereign Charter article(s) it maps to (cites.sovereign),
     so the county crosswalk spans the same county → state → federal → int'l → ICC → ICJ →
     Holy See hierarchy. Correspondence map, not a claim of binding jurisdiction. ---- */
  const SUPRA = {
    "I":     { fed: [["PL 103-150", "Apology Resolution (1993)"]], intl: [["UNDRIP Art.3", "Right of self-determination"], ["ICCPR Art.1", "Self-determination of peoples"], ["UN Charter Art.1(2)", "Self-determination"]], icj: [["Western Sahara (1975)", "Self-determination — advisory opinion"], ["Chagos (2019)", "Decolonization & self-determination"]], holysee: [["Pacem in Terris (1963)", "Sovereignty & rights among peoples"]] },
    "II":    { intl: [["UNDRIP Art.18", "Right to participate in decision-making"]] },
    "V":     { intl: [["UNDRIP Art.18", "Participation in decision-making"]] },
    "VI":    { intl: [["UN Res 64/292", "Human right to water & sanitation"], ["UNDRIP Art.25", "Spiritual relationship to waters"]] },
    "X":     { fed: [["33 USC §1251", "Clean Water Act"]], intl: [["UN Res 76/300", "Right to a healthy environment"]] },
    "XI":    { intl: [["UNDRIP Art.26", "Lands, territories & resources"]] },
    "XVI":   { intl: [["UNDROP (2018)", "Rights of peasants & rural workers"], ["ICESCR Art.11", "Right to food"]] },
    "XVII":  { fed: [["33 USC §1251", "Clean Water Act"]], intl: [["UN Res 76/300", "Right to a healthy environment"], ["Rio Declaration", "Principle 10 — participation"]] },
    "XXI":   { intl: [["UDHR Art.12", "Privacy"], ["ICCPR Art.17", "Protection from interference"]] },
    "XXII":  { intl: [["Paris Agreement (2015)", "Climate & energy transition"]] },
    "XXIII": { fed: [["42 USC §5121", "Stafford Act / FEMA"]], intl: [["Sendai Framework (2015)", "Disaster risk reduction"]] },
    "XXVII": { intl: [["ICCPR Art.25", "Right to political participation"]] },
    "XXVIII":{ intl: [["UNDRIP Art.3", "Self-determination — living instrument"]] },
  };
  FUNCS.forEach(function (f) {
    var acc = { fed: [], intl: [], icc: [], icj: [], holysee: [] }, seen = { fed: {}, intl: {}, icc: {}, icj: {}, holysee: {} };
    (f.cites.sovereign || []).forEach(function (sv) {
      var m = /Art\.([IVXLC]+)/.exec(sv[0] || "");
      if (m && SUPRA[m[1]]) {
        Object.keys(acc).forEach(function (k) {
          (SUPRA[m[1]][k] || []).forEach(function (c) {
            if (!seen[k][c[0]]) { seen[k][c[0]] = 1; acc[k].push(c); }
          });
        });
      }
    });
    Object.keys(acc).forEach(function (k) { f.cites[k] = acc[k]; });
  });

  window.HAWCROSS = {
    meta: {
      snapshot: "2026-06-12", jurisdiction: "HAW-002", feed: "../_feed/agendas-HAW-002.json",
      county: "County of Hawaiʻi", seat: "Hilo", councilSize: 9,
      note: "County Charter functions crosswalked to HCC + HRS + Constitution, with the 12 Stones Sovereign Charter as the top overlay. Conflicts hydrate from the Hawaiʻi County feed.",
    },
    bodies: BODIES, funcs: FUNCS,
  };
})();
