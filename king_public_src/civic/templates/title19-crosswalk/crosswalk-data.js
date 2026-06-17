/* ============================================================
   12 Stones Sovereign Charter ⇄ Maui County + State of Hawaiʻi law
   ------------------------------------------------------------
   Section-level legal crosswalk. The charter spine uses the v5 /
   MauiOS_CountyAudit 28-article map (canon for govOS surfaces).
   Each article's `v2` field gives the DIFFERENT label that numeral
   carries in the V2-04082025 master charter (the version gap).

   Citations are real top-level + section statute references across
   six bodies of law. Where the live council-watch / RAIS feed is
   reachable, ordinances + conflicts hydrate from it; otherwise this
   dated snapshot stands.

   Sources of record:
     Charter  — Maui County Charter (1983, as amended)
     MCC      — Maui County Code (Municode)
     HRS      — Hawaiʻi Revised Statutes (capitol.hawaii.gov)
     Const    — Constitution of the State of Hawaiʻi
     Ord      — Maui County Council bills & resolutions (CivicClerk)
     Fed      — U.S. Code / treaties / international instruments
   Snapshot: 2026-06-12
   ============================================================ */
(function () {
  // Law bodies — filter chips, pivot rows, citation colors.
  const BODIES = [
    { id: "charter", label: "Maui County Charter",        short: "Charter", color: "#d9b24c", src: "Maui County Charter (1983, amended)" },
    { id: "mcc",     label: "Maui County Code",           short: "MCC",     color: "#c9943f", src: "Maui County Code · Municode" },
    { id: "hrs",     label: "Hawaiʻi Revised Statutes",   short: "HRS",     color: "#3a8fb7", src: "capitol.hawaii.gov" },
    { id: "const",   label: "Hawaiʻi State Constitution", short: "Const",   color: "#3f9b6d", src: "Constitution of the State of Hawaiʻi" },
    { id: "ord",     label: "Ordinances & Bills",         short: "Ord",     color: "#d9622b", src: "Maui County Council · CivicClerk", live: true },
    // --- the sovereign hierarchy above the State: federal -> international -> the courts of nations -> the Holy See ---
    { id: "fed",     label: "U.S. Federal",               short: "Fed",     color: "#9b7bb8", src: "U.S. Code & federal statutes" },
    { id: "intl",    label: "International Law",           short: "Int'l",   color: "#5fa8a0", src: "UN treaties & instruments" },
    { id: "icc",     label: "Int'l Criminal Court",       short: "ICC",     color: "#b0566e", src: "Rome Statute · ICC" },
    { id: "icj",     label: "Int'l Court of Justice",     short: "ICJ",     color: "#7b86c4", src: "Statute of the ICJ" },
    { id: "holysee", label: "Holy See · Canon Law",       short: "Holy See",color: "#c9b38a", src: "Holy See · Canon Law" },
  ];

  // Citation tuples: [citation, plain-language title].
  // Charter spine = v5 / CountyAudit map. v2 = the label this numeral
  // carries in the V2 master charter (annotates the version gap).
  const ARTICLES = [
    { n: "I", t: "Foundation & Supremacy", h: "Ke Kahua o ka Pono", v2: "Foundation", s: "active", scrolls: ["AUDIT-001", "DASHBOARD-001"],
      desc: "Charter declared supreme over county operations; all 54 HFE nodes operate under this framework. Anchored to the county's own incorporation powers and the State's recognition of Hawaiian usage as law.",
      cites: {
        charter: [["Art.1", "Incorporation & general powers"], ["§1-2", "Powers of the county"]],
        mcc: [["Title 1", "General Provisions"], ["§1.04", "Code adoption & construction"]],
        hrs: [["Ch.50", "County charters"], ["§46-1.5", "General powers of counties"], ["§1-1", "Common law; Hawaiian usage"]],
        const: [["Art.VIII §1-2", "Local government / home rule"], ["Art.I §1", "Political power in the people"]],
        ord: [],
        fed: [["PL 103-150", "Apology Resolution (1993)"], ["UNDRIP", "UN Decl. Rights of Indigenous Peoples"]],
      } },
    { n: "II", t: "Peacekeeper Network", h: "Nā Kiai Maluhia", v2: "Peacekeeper Protocol", s: "active", scrolls: ["MPD-07", "ENFORCEMENT-001"],
      desc: "Community-based restorative enforcement; governs security at all node deployment sites. Sits alongside the county police department and the State county-police statute.",
      cites: {
        charter: [["Art.8", "Department of Police; Police Commission"]],
        mcc: [["Title 9", "Public Peace, Morals & Welfare"]],
        hrs: [["Ch.52D", "County police departments"], ["Ch.353", "Corrections / reentry"]],
        const: [["Art.I §5", "Due process & equal protection"]],
        ord: [],
        fed: [],
      } },
    { n: "III", t: "Resource Custodian Circles", h: "Pōʻaiapuni Mālama Waiwai", v2: "Custodianship of Resources", s: "active", scrolls: ["FOOD-001", "ZONING-001"],
      desc: "Moku-level councils govern land and resource stewardship with veto power over extractive contracts. Oversees the Mauka zone (nodes 1–10). Bound to the public-land trust and the conservation mandate.",
      cites: {
        charter: [["§8-8.5", "Department of Planning"], ["Art.8", "Department of Water Supply"]],
        mcc: [["Title 19", "Comprehensive zoning"], ["Title 20", "Environmental protection"]],
        hrs: [["Ch.171", "Management of public lands"], ["Ch.205", "State land use districts"], ["Ch.183", "Forest reserves & forestry"]],
        const: [["Art.XI §1", "Conservation for present & future generations"]],
        ord: [],
        fed: [],
      } },
    { n: "IV", t: "Lineage & Genealogy Rights", h: "Nā Kuleana Moʻokūʻauhau", v2: "Cultural & Lineage Integrity", s: "active", scrolls: ["CULTURE-001", "PETITION-001"],
      desc: "Lineage-based land access rights; traditional fishing and heirloom seed nodes governed here. Rests on the strongest customary-rights protections in Hawaiʻi law.",
      cites: {
        charter: [["§8-8.4", "Cultural Resources Commission"]],
        mcc: [["§2.80B", "Cultural Resources Commission"]],
        hrs: [["§1-1", "Hawaiian usage as common law"], ["§7-1", "Kuleana — gathering & access rights"], ["§188-22.6", "Community-based subsistence fishing"], ["Ch.10", "Office of Hawaiian Affairs"]],
        const: [["Art.XII §7", "Traditional & customary native rights"], ["Art.XII §1-3", "Hawaiian Homes Commission Act"], ["Art.XII §5", "Office of Hawaiian Affairs"]],
        ord: [],
        fed: [["25 USC §3001", "NAGPRA — graves protection"]],
      } },
    { n: "V", t: "Moku Council Governance", h: "Ka Mokuʻāina Kūkākūkā", v2: "Cultural & Lineage Integrity", s: "pending", scrolls: ["TESTIMONY-001"],
      desc: "Nine moku councils; supermajority required for ʻāina ordinances. All node deployment proposals require moku approval. Mapped to the council, the open-meetings law, and home rule.",
      cites: {
        charter: [["Art.3", "The Council"], ["Art.13", "Initiative, referendum & recall"]],
        mcc: [["Title 2", "Administration"], ["§2.04", "Council organization"]],
        hrs: [["Ch.46", "County organization & general powers"], ["Ch.92", "Public agency meetings (Sunshine Law)"]],
        const: [["Art.VIII §1-2", "Local government"]],
        ord: [],
        fed: [],
      } },
    { n: "VI", t: "Wai Kapu — Water Sovereignty", h: "Wai Kapu o Nā Kānaka", v2: "Fiduciary Trust & Transparency", s: "alert", scrolls: ["AUDIT-001", "GHOST-001"],
      desc: "No privatization of aquifer, stream, or rainfall. Water is held in public trust under the State Water Code and the Constitution. ACTIVE CONFLICT: Bill 37 ($25M water fund) flagged against the public-trust mandate.",
      cites: {
        charter: [["Art.8", "Department of Water Supply"], ["§8-11", "Board of Water Supply"]],
        mcc: [["Title 14", "Public works — Dept. of Water Supply rules"], ["§14.01", "Water rates & service"]],
        hrs: [["Ch.174C", "State Water Code"], ["§174C-101", "Native Hawaiian water rights"], ["§7-1", "Water & access rights"]],
        const: [["Art.XI §1 & §7", "Public trust in water (Waiāhole)"], ["Art.XII §7", "Customary water rights"]],
        ord: [["Bill 37", "$25M water fund — flagged"]],
        fed: [],
      } },
    { n: "VII", t: "Sacred Sites & Burial", h: "Nā Wāhi Kapu", v2: "Public Health & Wellness", s: "alert", scrolls: ["CULTURE-001"],
      desc: "Heiau, burial grounds and sacred sites protected; ceremonial clearance precedes any deployment at sacred zones. Backed by the State historic-preservation and island burial council statutes plus federal graves law.",
      cites: {
        charter: [["§8-8.4", "Cultural Resources Commission"]],
        mcc: [["§2.80B", "Cultural Resources Commission review"]],
        hrs: [["Ch.6E", "Historic preservation"], ["§6E-43", "Prehistoric & historic burial sites"], ["§6E-43.5", "Island burial councils"], ["§6E-42", "Review of proposed projects"]],
        const: [["Art.XII §7", "Customary rights"], ["Art.IX §7", "Preservation of culture"]],
        ord: [],
        fed: [["25 USC §3001", "NAGPRA"], ["54 USC §306108", "NHPA §106 review"]],
      } },
    { n: "VIII", t: "Housing & Rebuilding", h: "Ka Hale Hoʻihoʻi", v2: "Education & Cultural Learning", s: "alert", scrolls: ["HOUSING-001", "AUDIT-001"],
      desc: "Post-Lahaina rebuild under sovereign protocols. ACTIVE CONFLICT: CDBG-DR $1.639B (Bill 32) and Reso 25-80 flagged. Anchored to county workforce-housing code, State affordable-housing law, and the federal disaster-recovery block grant.",
      cites: {
        charter: [["Art.8", "Dept. of Housing & Human Concerns"]],
        mcc: [["Ch.2.96", "Residential workforce housing policy"], ["Title 16", "Building & construction"], ["Title 19", "Residential districts"]],
        hrs: [["Ch.201H", "Hawaiʻi affordable housing"], ["Ch.521", "Residential Landlord-Tenant Code"], ["Ch.514B", "Condominium property"]],
        const: [["Art.IX §1", "Public health & welfare"]],
        ord: [["Bill 32", "CDBG-DR $1.639B — flagged"], ["Reso 25-80", "Recovery resolution — flagged"]],
        fed: [["42 USC §5301", "HCDA / CDBG-DR §105(a)"], ["42 USC §5121", "Stafford Act — disaster relief"]],
      } },
    { n: "IX", t: "Judicial Sovereignty", h: "Ka Hoʻokolokolo Kūpono", v2: "Protection of Youth", s: "pending", scrolls: ["TRIBUNAL-001", "COURT-001"],
      desc: "Sovereign tribunal for charter matters; the 13th Protocol governs enforcement. Read against the State judiciary and arbitration framework and international adjudication.",
      cites: {
        charter: [],
        mcc: [],
        hrs: [["Ch.601", "The judiciary"], ["Ch.603", "Circuit courts"], ["Ch.604", "District courts"], ["Ch.658A", "Uniform Arbitration Act"]],
        const: [["Art.VI", "The judiciary"]],
        ord: [],
        fed: [["ICJ Statute", "International Court of Justice"], ["UNDRIP Art.27,40", "Indigenous adjudication & redress"]],
      } },
    { n: "X", t: "Budget Transparency", h: "Ka ʻOiaʻiʻo Kālā", v2: "Scroll Amendment System", s: "active", scrolls: ["AUDIT-001", "COMPLIANCE-001"],
      desc: "Full expenditure traceability at resident level. Mapped to the county auditor & financial procedures, the real-property-tax code, the procurement code and the State public-records act. FY2027 budget (Bills 55–56) passed 2nd reading 2026-06-05.",
      cites: {
        charter: [["Art.9", "Financial procedures & budget"], ["Art.10", "Office of the County Auditor"]],
        mcc: [["Title 3", "Revenue & taxation"], ["§3.48", "Real property tax"]],
        hrs: [["Ch.92F", "UIPA — public records"], ["Ch.103D", "Procurement Code"], ["Ch.46", "County budget powers"]],
        const: [["Art.VII", "Taxation & finance"]],
        ord: [["Bills 55–56", "FY2027 budget — passed 2nd reading 06-05"]],
        fed: [],
      } },
    { n: "XI", t: "Land Use & Zoning", h: "Ka Hoʻohana ʻĀina", v2: "Spirit Contract & Creator's Oath", s: "active", zoning: true, scrolls: ["ZONING-001", "GHOST-001"],
      desc: "THE TITLE 19 ANCHOR. Land use decisions require moku approval and charter review. Title 19 rewrite carries 97 ordinance scrolls. Crosswalked to the full State land-use, coastal-zone, planning and environmental-review chain. Mauka nodes 1–10, 31, 34, 41, 46 require zoning clearance before deployment.",
      cites: {
        charter: [["§8-8.5", "Department of Planning"], ["§8-8.4", "Planning commissions"]],
        mcc: [["Title 19", "Comprehensive zoning"], ["Title 18", "Subdivision"], ["§19.04", "Zoning definitions"], ["§19.510", "Special Management Area (SMA)"]],
        hrs: [["Ch.205", "State Land Use Commission & districts"], ["Ch.205A", "Coastal Zone Management / SMA"], ["Ch.226", "Hawaiʻi State Planning Act"], ["Ch.343", "Environmental impact statements"]],
        const: [["Art.XI §1", "Conservation & public trust"], ["Art.XII §7", "Customary rights on land"]],
        ord: [["Title 19 rewrite", "97 ordinance scrolls — ZONING-001"]],
        fed: [],
      } },
    { n: "XII", t: "RAIS Digital Sovereignty", h: "Ka ʻIkepili Sovereign", v2: "Public Trust Infrastructure", s: "active", scrolls: ["DASHBOARD-001", "TWINS-001"],
      desc: "Every council agenda item becomes a sovereign scroll; IoT and digital-twin nodes governed here. Built on the State open-records, open-meetings and data-protection statutes and the constitutional privacy right.",
      cites: {
        charter: [],
        mcc: [["Title 2", "Administration — records"]],
        hrs: [["Ch.92F", "Uniform Information Practices Act"], ["Ch.92", "Public meetings (Sunshine Law)"], ["Ch.487N", "Security breach of personal info"], ["Ch.487J", "SSN protection"]],
        const: [["Art.I §6", "Right to privacy"], ["Art.I §7", "Searches & seizures"]],
        ord: [],
        fed: [],
      } },
    { n: "XIII", t: "Restorative Justice", h: "Ka Hoʻoponopono Kānāwai", v2: "Enforcement & 13th Protocol", s: "active", scrolls: ["ENFORCEMENT-001", "TRIBUNAL-001"],
      desc: "Hoʻoponopono-based justice circles replace punitive enforcement. Maps to the State sentencing-alternatives, deferred-plea and family-court frameworks.",
      cites: {
        charter: [],
        mcc: [],
        hrs: [["Ch.706", "Disposition of convicted defendants"], ["Ch.853", "Deferred acceptance of plea"], ["Ch.571", "Family Court"]],
        const: [["Art.I", "Bill of rights"]],
        ord: [],
        fed: [],
      } },
    { n: "XIV", t: "14th Stone Algorithm", h: "Ka Pohaku ʻUmikūmāhā", v2: "Backend Protocols & RAIS Ledger", s: "active", scrolls: ["CULTURE-001", "TESTIMONY-001"],
      desc: "AI-driven glyph audit guardian — every node output, bill, contract and resolution passes through it for compliance tagging. Governed by the public-records and procurement-audit statutes; no direct MCC equivalent — a new sovereign provision.",
      cites: {
        charter: [],
        mcc: [],
        hrs: [["Ch.92F", "UIPA — record access"], ["Ch.103D", "Procurement audit"]],
        const: [],
        ord: [],
        fed: [],
      } },
    { n: "XV", t: "Cultural Preservation", h: "Ka Mālama Moʻomeheu", v2: "Sacred Sites & Burial", s: "active", scrolls: ["CULTURE-001"],
      desc: "Kapa, hula, navigation, ʻōlelo Hawaiʻi as core infrastructure. Anchored to the Aloha Spirit law, the historic-preservation chapter and the constitutional Hawaiian-language and culture provisions.",
      cites: {
        charter: [["§8-8.4", "Cultural Resources Commission"]],
        mcc: [["§2.80B", "Cultural Resources Commission"]],
        hrs: [["§5-7.5", "ʻAloha Spirit law"], ["Ch.6E", "Historic preservation"], ["§5-7", "Hawaiian language"]],
        const: [["Art.XV §4", "Hawaiian & English official languages"], ["Art.X §4", "Hawaiian education program"], ["Art.IX §9", "Hawaiian culture"]],
        ord: [],
        fed: [],
      } },
    { n: "XVI", t: "Food Sovereignty", h: "Ka Mana ʻAi o Nā Kānaka", v2: "Ocean & Marine Stewardship", s: "active", zoning: true, scrolls: ["FOOD-001", "ZONING-001"],
      desc: "Sovereign agriculture governs the entire Kula (Upcountry) zone — crop, hydroponic, FarmBox and seed nodes. Crosswalked to agricultural zoning, Important Agricultural Lands and the State agriculture chapter.",
      cites: {
        charter: [],
        mcc: [["Title 19", "Agricultural districts"], ["Title 5", "Animals"]],
        hrs: [["§205-41", "Important Agricultural Lands"], ["Ch.141", "Department of Agriculture"], ["Ch.149A", "Pesticides"]],
        const: [["Art.XI §3", "Conservation of agricultural lands"]],
        ord: [],
        fed: [],
      } },
    { n: "XVII", t: "Environmental Justice", h: "Ka Pono Kaiapuni", v2: "Indigenous Diplomacy", s: "pending", scrolls: ["AUDIT-001", "DISASTER-001"],
      desc: "Prohibits ecological exploitation without sovereign review; soil, carbon, biodiversity and waste nodes. Mapped to the environmental-impact, environmental-quality and hazardous-response statutes and the right to a clean environment.",
      cites: {
        charter: [],
        mcc: [["Title 20", "Environmental protection"]],
        hrs: [["Ch.343", "Environmental impact statements"], ["Ch.342B/D/G", "Air, water-pollution & solid waste"], ["Ch.128D", "Environmental response (HEER)"], ["Ch.195D", "Conservation of aquatic life & wildlife"]],
        const: [["Art.XI §9", "Right to a clean & healthful environment"]],
        ord: [],
        fed: [["33 USC §1251", "Clean Water Act"]],
      } },
    { n: "XVIII", t: "Generational Wealth Trust", h: "Ka Waiwai Hanauna Hou", v2: "Treasury & Financial Sovereignty", s: "active", scrolls: ["AUDIT-001"],
      desc: "12.5% of all county contracts flow to the trust; deployment contracts must embed community benefit. Implemented through the procurement code's preference mechanisms and the county financial procedures.",
      cites: {
        charter: [["Art.9", "Financial procedures"]],
        mcc: [["Title 3", "Revenue & taxation"], ["§3.48", "Real property tax"]],
        hrs: [["Ch.103D", "Procurement Code — preferences & set-asides"], ["Ch.554", "Trusts"]],
        const: [["Art.VII", "Taxation & finance"]],
        ord: [],
        fed: [],
      } },
    { n: "XIX", t: "Workforce Development", h: "Ka Hānai ʻOhana Hana", v2: "Restitution & Economic Justice", s: "pending", scrolls: ["TESTIMONY-001"],
      desc: "Sovereign workforce pipelines from the Kula nodes; FarmBox shelters eligible under CDBG §105(a). Read against the State labor and community-college workforce statutes.",
      cites: {
        charter: [],
        mcc: [],
        hrs: [["Ch.371", "Department of Labor & Industrial Relations"], ["Ch.304A", "University of Hawaiʻi / community colleges"]],
        const: [],
        ord: [],
        fed: [["42 USC §5305", "CDBG §105(a) eligible activities"]],
      } },
    { n: "XX", t: "Ocean & Reef Restoration", h: "Ka Mālama Moana", v2: "Global Sovereign Banking", s: "active", scrolls: ["AUDIT-001"],
      desc: "Water Keepers sovereign council governs all Makai zone nodes — coral, reef, fishing, seaweed, marine energy. Crosswalked to the marine-life, aquatic-resources, fishing and coastal-zone statutes.",
      cites: {
        charter: [],
        mcc: [],
        hrs: [["Ch.190", "Marine life conservation"], ["Ch.187A", "Aquatic resources"], ["Ch.188", "Fishing"], ["§188-22.6", "Community-based subsistence fishing"], ["Ch.205A", "Coastal Zone Management"]],
        const: [["Art.XI §6", "Marine resources"]],
        ord: [],
        fed: [["33 USC §1251", "Clean Water Act"]],
      } },
    { n: "XXI", t: "Digital Infrastructure", h: "Ka Paepae Huna Kikohoʻe", v2: "Sovereign Personnel & Public Office", s: "active", scrolls: ["TWINS-001", "DASHBOARD-001"],
      desc: "Sovereign digital twin integrating all node IoT feeds. Governed by the public-utilities (telecom) chapter, county rights-of-way code and the open-records act.",
      cites: {
        charter: [],
        mcc: [["Title 12", "Streets, sidewalks & public places (ROW)"]],
        hrs: [["Ch.269", "Public Utilities Commission — telecom"], ["Ch.92F", "UIPA"]],
        const: [],
        ord: [],
        fed: [],
      } },
    { n: "XXII", t: "Renewable Energy Sovereignty", h: "Ka Mana Pūʻaneane", v2: "People's Selection Protocol", s: "active", scrolls: ["AUDIT-001"],
      desc: "Community-owned energy; no privatization without moku consent. Anchored to the renewable-portfolio standard (100% by 2045), net-metering and the State energy objectives.",
      cites: {
        charter: [],
        mcc: [],
        hrs: [["Ch.269", "Public Utilities Commission"], ["§269-91 to -95", "Renewable Portfolio Standard"], ["Ch.196", "Energy / net energy metering"], ["§226-18", "State energy objectives"]],
        const: [["Art.XI §1", "Conservation of natural resources"]],
        ord: [],
        fed: [],
      } },
    { n: "XXIII", t: "Emergency & Disaster", h: "Ka Pio i ka Pōʻino", v2: "Elemental Utility Protocols", s: "pending", scrolls: ["DISASTER-001", "SAFETY-001"],
      desc: "Sovereign emergency management — firebreak, fire-detection, flood and erosion nodes. Mapped to the county fire code & emergency agency, the State emergency-management act and the federal disaster framework.",
      cites: {
        charter: [["Art.8", "Dept. of Fire & Public Safety; MEMA"]],
        mcc: [["Title 16", "Fire code"], ["§16.04", "Fire prevention"]],
        hrs: [["Ch.127A", "Emergency management"]],
        const: [],
        ord: [],
        fed: [["42 USC §5121", "Stafford Act / FEMA"]],
      } },
    { n: "XXIV", t: "ICJ & International Law", h: "Ka Kānāwai Honua", v2: "HR & Community Agreements", s: "active", scrolls: ["ICJ-JL-001", "ICJPROTECT-001"],
      desc: "International standing; sovereign projects carry ICJ-backed protective designation. Grounded in international instruments and the federal apology for the overthrow of the Hawaiian Kingdom.",
      cites: {
        charter: [],
        mcc: [],
        hrs: [],
        const: [["Art.XV §1", "Boundaries of the State"]],
        ord: [],
        fed: [["UN Charter", "Self-determination"], ["UNDRIP", "Indigenous peoples' rights"], ["PL 103-150", "Apology Resolution"], ["ICJ Statute", "International adjudication"]],
      } },
    { n: "XXV", t: "Healthcare Sovereignty", h: "Ka Olakino Kānaka", v2: "Diaspora & Exile Return", s: "pending", scrolls: ["ADA-001"],
      desc: "Community health centers integrating lāʻau lapaʻau with western medicine. Crosswalked to the Department of Health, the traditional Hawaiian healing exemption and federal disability law.",
      cites: {
        charter: [],
        mcc: [],
        hrs: [["Ch.321", "Department of Health"], ["§453-2(b)(4)", "Traditional Hawaiian healing (lāʻau lapaʻau)"], ["Ch.323D", "Health resource planning"]],
        const: [],
        ord: [],
        fed: [["42 USC §12101", "Americans with Disabilities Act"]],
      } },
    { n: "XXVI", t: "Youth & Elder Governance", h: "Ka Nohona Hanauna", v2: "Sacred Technology & AI Governance", s: "pending", scrolls: ["CULTURE-001", "TESTIMONY-001"],
      desc: "Bi-generational governance; inter-generational knowledge transmission nodes. Mapped to the executive office on aging, family court and child-welfare statutes.",
      cites: {
        charter: [],
        mcc: [],
        hrs: [["Ch.349", "Executive Office on Aging"], ["Ch.571", "Family Court"], ["Ch.350", "Child abuse & neglect"]],
        const: [],
        ord: [],
        fed: [],
      } },
    { n: "XXVII", t: "Petition & Direct Democracy", h: "Ka Noi Kānāwai", v2: "Crisis Recovery & Disaster Resilience", s: "active", scrolls: ["PETITION-001", "PRESS-001"],
      desc: "Sovereign petition: 60% of registered voters; full deployment requires community ratification. Anchored to the county charter's initiative/referendum/recall article and the State elections code.",
      cites: {
        charter: [["Art.13", "Initiative, referendum & recall"]],
        mcc: [],
        hrs: [["Ch.11", "Elections, generally"], ["Ch.12", "Election of officials"]],
        const: [["Art.I §1", "Political power in the people"]],
        ord: [],
        fed: [],
      } },
    { n: "XXVIII", t: "Living Scroll Amendment", h: "Ka Puke Ola Kānāwai", v2: "The 14th Stone: Guardian Algorithm", s: "pending", scrolls: ["PETITION-001"],
      desc: "The charter is a living document; nodes going live can trigger charter annotation updates. Mapped to the county charter-amendment article, the State charter statute and constitutional revision.",
      cites: {
        charter: [["Art.14", "Charter amendment & charter commission"]],
        mcc: [],
        hrs: [["Ch.50", "County charters — amendment"]],
        const: [["Art.XVII", "Revision & amendment"]],
        ord: [],
        fed: [],
      } },
  ];

  /* ---- The sovereign hierarchy above the State. Each charter principle is set
     beside the REAL instrument in each body that articulates the same principle —
     a correspondence map (the charter's claim ⇄ the existing law), not a claim of
     binding jurisdiction. Every citation is a real instrument; bodies with no
     defensible correspondence stay empty. This merge REPLACES the legacy combined
     "fed" bucket with cleanly-separated U.S. / International / ICC / ICJ / Holy See
     columns so the crosswalk spans county → state → federal → the courts of nations. */
  const SUPRA = {
    "I":     { fed: [["PL 103-150", "Apology Resolution (1993)"]], intl: [["UNDRIP Art.3", "Right of self-determination"], ["ICCPR Art.1", "Self-determination of peoples"], ["UN Charter Art.1(2)", "Self-determination"]], icj: [["Western Sahara (1975)", "Self-determination — advisory opinion"], ["Chagos (2019)", "Decolonization & self-determination"]], holysee: [["Pacem in Terris (1963)", "Sovereignty & rights among peoples"]] },
    "III":   { intl: [["UNDRIP Art.26", "Lands, territories & resources"]] },
    "IV":    { fed: [["25 USC §3001", "NAGPRA — graves protection"]], intl: [["UNDRIP Art.11–13", "Culture, lineage & tradition"], ["ICERD", "Racial-discrimination convention"]] },
    "V":     { intl: [["UNDRIP Art.18", "Right to participate in decision-making"]] },
    "VI":    { intl: [["UN Res 64/292", "Human right to water & sanitation"], ["UNDRIP Art.25", "Spiritual relationship to waters"]] },
    "VII":   { fed: [["25 USC §3001", "NAGPRA"], ["54 USC §306108", "NHPA §106 review"]], intl: [["UNDRIP Art.12", "Sacred sites & ceremonial objects"], ["Hague Conv. 1954", "Cultural property protection"]], icc: [["Rome Statute Art.8(2)(b)(ix)", "Attacks on religious / cultural sites"]], holysee: [["Code of Canon Law c.1205–1213", "Sacred places"]] },
    "VIII":  { fed: [["42 USC §5301", "HCDA / CDBG-DR §105(a)"], ["42 USC §5121", "Stafford Act — disaster relief"]], intl: [["UDHR Art.25", "Right to adequate housing"], ["ICESCR Art.11", "Adequate standard of living"]] },
    "IX":    { icj: [["ICJ Statute Art.36", "Jurisdiction of the Court"], ["ICJ Statute Art.38", "Sources of international law"]], icc: [["Rome Statute Art.1", "The Court — complementary jurisdiction"]], intl: [["UNDRIP Art.27 & 40", "Adjudication & redress"]], holysee: [["Lateran Treaty (1929)", "Sovereign juridical personality of the Holy See"]] },
    "XI":    { intl: [["UNDRIP Art.26", "Lands, territories & resources"]] },
    "XII":   { intl: [["UDHR Art.12", "Privacy"], ["ICCPR Art.17", "Protection from interference"]] },
    "XIII":  { intl: [["UN Res 40/34 (1985)", "Justice for victims — restorative principles"]] },
    "XV":    { intl: [["UNESCO 2003 Convention", "Intangible cultural heritage"], ["UNDRIP Art.13", "Languages & oral traditions"]] },
    "XVI":   { intl: [["UNDROP (2018)", "Rights of peasants & rural workers"], ["ICESCR Art.11", "Right to food"]] },
    "XVII":  { fed: [["33 USC §1251", "Clean Water Act"]], intl: [["UN Res 76/300", "Right to a healthy environment"], ["Rio Declaration", "Principle 10 — access & participation"]] },
    "XIX":   { fed: [["42 USC §5305", "CDBG §105(a) eligible activities"]], intl: [["ICESCR Art.6", "Right to work"]] },
    "XX":    { fed: [["33 USC §1251", "Clean Water Act"]], intl: [["UNCLOS (1982)", "Marine resources & stewardship"]] },
    "XXII":  { intl: [["Paris Agreement (2015)", "Climate & energy transition"]] },
    "XXIII": { fed: [["42 USC §5121", "Stafford Act / FEMA"]], intl: [["Sendai Framework (2015)", "Disaster risk reduction"]] },
    "XXIV":  { fed: [["PL 103-150", "Apology Resolution"]], intl: [["UN Charter Art.1(2)", "Self-determination"], ["UNDRIP", "Indigenous peoples' rights"]], icj: [["ICJ Statute Art.36 & 38", "International adjudication"], ["Western Sahara (1975)", "Self-determination opinion"], ["Chagos (2019)", "Decolonization opinion"]], icc: [["Rome Statute Art.5", "Core international crimes"]], holysee: [["Holy See — UN Permanent Observer", "Sovereign subject of international law"]] },
    "XXV":   { fed: [["42 USC §12101", "Americans with Disabilities Act"]], intl: [["ICESCR Art.12", "Right to health"], ["CRPD", "Rights of persons with disabilities"]] },
    "XXVI":  { intl: [["CRC", "Convention on the Rights of the Child"], ["UN Res 46/91", "Principles for Older Persons"]] },
    "XXVII": { intl: [["ICCPR Art.25", "Right to political participation"]] },
  };
  ARTICLES.forEach(function (a) {
    var s = SUPRA[a.n] || {};
    a.cites.fed     = s.fed     || [];   // legacy combined bucket -> clean U.S.-only
    a.cites.intl    = s.intl    || [];
    a.cites.icc     = s.icc     || [];
    a.cites.icj     = s.icj     || [];
    a.cites.holysee = s.holysee || [];
  });

  // Nodes requiring Title 19 / Art.XI zoning clearance (the deep-dive anchor).
  const CLEAR = [
    { id: 1,  z: "mauka", nm: "Firebreak Design",          why: "Art.XI clearance" },
    { id: 2,  z: "mauka", nm: "Soil Health",               why: "Art.XI clearance" },
    { id: 3,  z: "mauka", nm: "Rainwater Harvesting",      why: "Art.XI clearance" },
    { id: 4,  z: "mauka", nm: "Carbon Sequestration",      why: "Art.XI · ZONING-001" },
    { id: 5,  z: "mauka", nm: "Biodiversity Restoration",  why: "Art.XI clearance" },
    { id: 6,  z: "mauka", nm: "IoT Fire Detection",        why: "Art.XI clearance" },
    { id: 7,  z: "mauka", nm: "Renewable Energy",          why: "Art.XI clearance" },
    { id: 8,  z: "mauka", nm: "Cultural Site Preservation", why: "Art.XI clearance" },
    { id: 9,  z: "mauka", nm: "Microclimate Monitoring",   why: "Art.XI clearance" },
    { id: 10, z: "mauka", nm: "Ecosystem Connectivity",    why: "Art.XI · ZONING-001" },
    { id: 31, z: "mauka", nm: "Native Tree Planting",      why: "Art.XI · ZONING-001" },
    { id: 34, z: "mauka", nm: "Fog Harvesting",            why: "Art.XI clearance" },
    { id: 41, z: "mauka", nm: "Waterfall Restoration",     why: "Art.XI clearance" },
    { id: 46, z: "mauka", nm: "Sacred Forests",            why: "Art.XI clearance" },
    { id: 14, z: "kula",  nm: "Waste-to-Resource",         why: "ZONING-001 scroll" },
    { id: 39, z: "kula",  nm: "Nutrient Recovery",         why: "ZONING-001 scroll" },
    { id: 47, z: "kula",  nm: "Rotational Grazing",        why: "ZONING-001 scroll" },
  ];

  // Live conflicts — charter article vs the law it is flagged against.
  // Hydrated from council-watch when reachable; else this snapshot.
  const CONFLICTS = [
    { id: "C-37",   sev: "alert",    art: "VI",   title: "Bill 37 — $25M water fund", against: "HRS Ch.174C public trust · Haw. Const. Art.XI §7",
      desc: "Fund structure flagged as a step toward de-facto privatization of a public-trust resource. Question raised, not an accusation — needs the ordinance text to resolve.", source: "council-watch", date: "2026-06-12" },
    { id: "C-32",   sev: "alert",    art: "VIII", title: "Bill 32 + Reso 25-80 — CDBG-DR $1.639B", against: "42 USC §5301 §105(a) eligible activities · MCC Ch.2.96",
      desc: "Lahaina recovery block-grant allocation crossed against workforce-housing eligibility and the federal eligible-activities list. FarmBox shelter eligibility under §105(a) pending HUD read.", source: "council-watch", date: "2026-06-12" },
    { id: "C-budget", sev: "watch",  art: "X",    title: "FY2027 budget — Bills 55–56", against: "Charter Art.9 · MCC Title 3",
      desc: "Passed 2nd & final reading 2026-06-05 ($1.6B total). Penny-level dept ledger re-parse ACTIONABLE — CivicClerk file 5893 ordinance text detected; re-checksum on post.", source: "council-watch", date: "2026-06-12" },
    { id: "C-9",    sev: "resolved", art: "XVI",  title: "Bill 9 — realtor-PAC linkage", against: "HRS Ch.205 · Ch.84 (ethics)",
      desc: "Documented donor↔Bill 9 correlation surfaced as a question. Entry now DEAD on the council feed — closed.", source: "donor-watch", date: "2026-06-11" },
  ];

  // ============================================================
  // Title 19 ingest (AG-first) — rules-vs-code mapping. [r1]
  // Added 2026-06-17. Reflects the ingested Title 19 corpus
  // (Ch. 19.30A Agricultural + Ch. 19.530 Enforcement) and which
  // provisions are CODE vs. delegated to administrative RULES.
  // codeStatus/ruleStatus: "ingested" = verbatim section text
  // captured + cited; "expanding" = identified, not yet ingested.
  // codifyCandidate -> analysis/rules_to_code_candidates.md in the
  // title19-service template (labeled analysis, not law).
  // ============================================================
  const RULES_TO_CODE = [
    { topic: "AG district standards & uses", code: "MCC 19.30A.010–.120", codeStatus: "ingested",
      rule: "Planning Dept admin rules MC-12, Subtitle 01 (Ch. 19.30A amendments)", ruleStatus: "expanding",
      codifyCandidate: "A2, B4–B6", src: "https://library.municode.com/hi/county_of_maui/codes/code_of_ordinances?nodeId=TIT19ZO_ARTIICOZOPR_CH19.30AAGDI" },
    { topic: "Commercial agricultural structures", code: "MCC 19.30A.072", codeStatus: "ingested",
      rule: "delegated by 19.30A.072(J)", ruleStatus: "expanding",
      codifyCandidate: "A1", src: "https://library.municode.com/hi/county_of_maui/codes/code_of_ordinances?nodeId=TIT19ZO_ARTIICOZOPR_CH19.30AAGDI" },
    { topic: "Civil fines / enforcement procedure", code: "MCC 19.530.030", codeStatus: "ingested",
      rule: "Rules for Administrative Procedures and Civil Fines for Violations of Ch. 16.13 and Title 19", ruleStatus: "expanding",
      codifyCandidate: "A3, C7", src: "https://library.municode.com/hi/county_of_maui/codes/code_of_ordinances?nodeId=TIT19ZO_ARTVADEN_CH19.530EN" },
    { topic: "Farm plan contents", code: "referenced in MCC 19.30A.050/.072", codeStatus: "ingested",
      rule: "department practice / AG Declaration form", ruleStatus: "expanding",
      codifyCandidate: "B4", src: "https://www.mauicounty.gov/2017/Planning-Regulations" },
    { topic: "Rural district standards & uses", code: "MCC 19.29.010–.060", codeStatus: "ingested",
      rule: "director may adopt rules to implement (19.29.060)", ruleStatus: "expanding",
      codifyCandidate: "—", src: "https://library.municode.com/hi/county_of_maui/codes/code_of_ordinances?nodeId=TIT19ZO_ARTIICOZOPR_CH19.29RUDI" },
    { topic: "SMA / shoreline enforcement (independent of county-ordinance warnings)", code: "HRS 205A-32 (civil fine ≤$100,000; ≤$10,000/day)", codeStatus: "ingested",
      rule: "SMA Rules §12-202-23(d)(1), §12-202-25 (≤$10,000/violation + ≤$1,000/day); Shoreline Rules §12-5-15 → 205A-32; contrast HRS 46-1.5(24)(A) county-ordinance warnings", ruleStatus: "ingested",
      note: "Per 2003 Corp. Counsel opinion: NO warning required before NOV+fine under HRS 205A/SMA/Shoreline (cf. county ordinance/rule, which expects reasonable notice). DATED OPINION — may be superseded.",
      codifyCandidate: "enforcement-corpus (opinion, not codification)", src: "https://www.mauicounty.gov/ArchiveCenter/ViewFile/Item/288" },
  ];

  window.CROSSWALK = {
    meta: {
      snapshot: "2026-06-12",
      title19Ingest: { date: "2026-06-17", scope: "AG-first + expanding: Ch. 19.30A (Agricultural) + Ch. 19.29 (Rural) + Ch. 19.530 (Enforcement) ingested/cited; SMA/shoreline enforcement (HRS 205A) + 2003 CC warnings opinion ingested; other districts + admin-rule text expanding", refreshPolicy: "Re-pull each Municode node; compare ordinance trailer; mark stale; re-ingest. Cross-ref County Title 19 Rewrite draft TOC." },
      charterPrimary: "v5 / MauiOS_CountyAudit map (28 articles)",
      versionGap: "The V2-04082025 master charter orders these 28 numerals differently — e.g. Art.XI is \u201cLand Use & Zoning\u201d here but \u201cSpirit Contract & Creator's Oath\u201d in V2. Each row shows its V2 label. v5 is canon for govOS surfaces; V2 is historical.",
      feed: "../_feed/agendas.json",
    },
    bodies: BODIES,
    articles: ARTICLES,
    clearances: CLEAR,
    conflicts: CONFLICTS,
    rulesToCode: RULES_TO_CODE,
  };
})();
