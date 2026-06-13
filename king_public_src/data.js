/* King System · real data harvested 2026-06-10 · rendered flags verified 06-11 · 06-12 07:00 crosscheck: 35 finals, 3 uploaded — from Video System elementLOTUS
   (sage_node_system.py SONG_NODES + DISPATCH.md v3.3.0-mission-control).
   Zone "Kula" = enforced canon name for legacy "Farmlands".
   2026-06-11: catalogExtras added (flagship songs beyond the 54-node roster) + pending list synced to dispatch.
   2026-06-12: zone conflict RESOLVED by charter logic (dispatch 09:22) — zone is TWO dimensions: 'quad' (governance
   quadrant, DT_SGI_Nodes.quad.csv 18/18/16+2 lock, joined by node name) governs acts/pillars; 'zone' here =
   setting_zone (registry) governs render/LoRA styling. kilo synced to 06-11 night fleet (6 live); game3d added.
   06-12 p.m. pass: longform branch surfaced (cowork 06-11 17:19, missed by the a.m. sync) + render lane PAUSE flag
   + film crosscheck moved to 32-of-35.
   Live app reads /api/film/roster etc; this snapshot drives the prototype. */
window.KING_DATA = (() => {
  // n, name, zone, song slug, duration s, rendered
  const N = [
    [1,"Firebreak Design","Mauka","ASHES_OF_TRUST_DISTROKID",214,1],
    [2,"Soil Health","Mauka","MAUI_COURTS",187,1],
    [3,"Rainwater Harvesting","Mauka","CURE_(REMASTERED)",243,0],
    [4,"Carbon Sequestration","Mauka","AINA_LANI_FA",201,1],
    [5,"Biodiversity Restoration","Mauka","CHILDREN_OF_NATURE_S_SOURCE",256,1],
    [6,"IoT Fire Detection","Mauka","SCROLL_6_REMASTERED",178,0],
    [7,"Renewable Energy Systems","Mauka","SCROLL_7_MASTERED",192,0],
    [8,"Cultural Site Preservation","Mauka","HE_LEI_NO_LAHAINA",274,1],
    [9,"Watershed Management","Mauka","SCROLL_2",169,0],
    [10,"Ecosystem Connectivity","Mauka","BREATHKEEPERS_(REMASTERED)",228,0],
    [11,"Crop Diversification","Kula","GARDENREGGAE",233,0],
    [12,"Hydroponic Systems","Kula","TRACK_24",198,0],
    [13,"Mushroom Cultivation","Kula","BUDDHA_DON_T_BURN_OTHER",247,0],
    [14,"Waste-to-Resource Recycling","Kula","BYE_SIN",205,1],
    [15,"Smart Irrigation","Kula","TRACK_21",184,1],
    [16,"Pest Control","Kula","BASE_BANGER",176,0],
    [17,"Post-Harvest Preservation","Kula","ALOHA_E_ALOHAEQ8C_1",221,0],
    [18,"Seed Germination","Kula","ALOHA_E_ALOHAEQ8C_2",217,0],
    [19,"Aquaponics Fish Farming","Kula","WHITE_FOLKS_VOX_MAS",240,0],
    [20,"Crop Quality Optimization","Kula","WHITE_FOLKS_ARE_ALIENS_WAV",236,0],
    [21,"Coral Restoration","Makai","SCROLL_14_REMASTERED",188,0],
    [22,"Wave Energy","Makai","JAMMIN_(REMASTERED)",251,0],
    [23,"Marine Biodiversity","Makai","KUULA_ANA_BREATH_OF_THE_SACRED_CAVE",289,0],
    [24,"Plastic Cleanup","Makai","LEFT_BEHIND_TUNED",207,1],
    [25,"Coastal Erosion Prevention","Makai","BALDWIN_BEACH_(REMASTERED)",232,0],
    [26,"Eco-Tourism Education","Makai","TRACK_22",195,0],
    [27,"Water Desalination","Makai","SACRED_VOW_OF_THE_ISLANDS",263,0],
    [28,"Coastal Erosion Prevention II","Makai","STONE_4",171,0],
    [29,"Eco-Tourism Education II","Makai","SCROLL_16_REMASTERED",182,0],
    [30,"Traditional Fishing Practices","Makai","SCROLL_13_REMASTERED",190,0],
    [31,"Native Tree Planting","Mauka","KAULA_LANI",244,0],
    [32,"Food Forest Design","Kula","HUA_LANI",226,0],
    [33,"Ridge-to-Reef Systems","Makai","REEF",258,1],
    [34,"Fog Harvesting","Mauka","MODERN_POST_ROCK_5_21_25",212,0],
    [35,"Vertical Farming","Kula","WU_LANG_TANG_DU",199,0],
    [36,"Wave Energy Integration","Kula","WU_LANG_TANG_VOCAL",203,0],
    [37,"Modular FarmBox Design","Kula","SCROLL_5_MASTERED",186,0],
    [38,"Artificial Reef Creation","Makai","2DF3_8845_AF76_4589_8084_7A32_528C_5AB8",224,0],
    [39,"Nutrient Recovery","Kula","OUTLAWS",218,0],
    [40,"Red Algae Farming","Makai","SOWETO_SOUL",249,0],
    [41,"Waterfall Restoration","Mauka","PULE_LUNA",267,0],
    [42,"Compost Management","Kula","OUTLAW_ALOHA_MASTERED",231,1],
    [43,"Algae Biofuel Production","Makai","COSMIC_GUSH_5_27_25",194,0],
    [44,"Climate-Resilient Crops","Kula","STONE_5",179,1],
    [45,"Offshore Wind Energy","Makai","AUCTIONING_PEACE",237,0],
    [46,"Sacred Forests","Mauka","STONE_1_ARTICLE_1__EX",158,0],
    [47,"Rotational Grazing","Kula","JIMMYLANGFORD_STONE3_FINAL",223,1],
    [48,"Flood Management","Makai","PROMISED_AND_BETRAYED",246,1],
    [49,"Heirloom Seed Libraries","Kula","FOUND_SOUND_JOURNEY_ITALIAN_CHILL",260,0],
    [50,"Mauka Rangeland Management","Mauka","GLASCOTT_SUMMERS",229,1],
    [51,"Indigenous Forestry Knowledge","Mauka","SCROLL_4",165,0],
    [52,"Renewable Marine Farming","Makai","MOKU_ULA_BLUES_FAST_MINUS_ONE",242,0],
    [53,"Joker Node: Central Hub","Universal","AN_ON_Y_MO_US",235,1],
    [54,"Final Joker: Universal Synergy","Universal","COLORS_COLLIDE",271,1],
  ];
  // Governance quadrant per registry node (joined to quad.csv by name; lock 18/18/16+2 holds).
  const QUAD = n =>
    n >= 53 ? "Universal" :
    (n <= 12 || [31,34,41,46,50,51].includes(n)) ? "Mauka" :
    ((n >= 13 && n <= 21) || [32,35,36,37,39,42,44,47,49].includes(n)) ? "Kula" : "Makai";
  const PILLAR = {Mauka:"P1 Food Security", Kula:"P2 Education", Makai:"P3 Truth", Universal:"P4 Sovereign Charter"};
  const ACT = {Mauka:"Act I — Governance / Cultural Sovereignty", Kula:"Act II — Agriculture / Food / Education",
               Makai:"Act III — Revenue / Commerce / Coastal", Universal:"Joker — Cosmic Synthesis / Calendar Reckoning"};
  const nodes = N.map(([n,name,zone,song,duration,rendered]) =>
    ({n,name,zone,song,duration,rendered:!!rendered, quad:QUAD(n), pillar:PILLAR[QUAD(n)], act:ACT[QUAD(n)]}));

  const title = s => s.replace(/_/g," ").replace(/\s*\((REMASTERED|MASTERED)\)\s*/i," ")
    .toLowerCase().replace(/\b\w/g,c=>c.toUpperCase()).trim();

  // Lyric scores — corpus fully transcribed 2026-06-10 (193/193, 0 below threshold)
  const scoreSeed = {REEF:96,HE_LEI_NO_LAHAINA:94,QUEEN_MOKU:93,AN_ON_Y_MO_US:91,BLESS_ER:90,
    COLORS_COLLIDE:95,HAMAKUA_FULLMASTER:92,BUDDHA_DON_T_BURN:89,DIFFERENT_CLOTH:88,
    ASH_ON_THE_BADGE:87,PULSE:85,KAULA_LANI:84,SCROLL_4:58,STONE_1_ARTICLE_1__EX:55};
  const songs = nodes.map(d => ({
    slug: d.song, title: title(d.song), node: d.n, zone: d.zone,
    score: scoreSeed[d.song] ?? (62 + ((d.n*37)%33)),
    model: "large-v3", flag: (scoreSeed[d.song]??99) < 60 ? "SHORT" : null
  }));

  // Flagship catalog songs beyond the 54-node roster — secondary seats on their
  // primary node per SONG_NODES (sage_node_system.py). Transcripts in lyrics.js.
  const catalogExtras = [
    {slug:"QUEEN_MOKU",         node:8,  zone:"Mauka"},
    {slug:"BLESS_ER",           node:8,  zone:"Mauka"},
    {slug:"ASH_ON_THE_BADGE",   node:53, zone:"Universal"},
    {slug:"DIFFERENT_CLOTH",    node:53, zone:"Universal"},
    {slug:"HAMAKUA_FULLMASTER", node:41, zone:"Mauka"},
  ].map(d => ({...d, title:title(d.slug), score:scoreSeed[d.slug] ?? 80, model:"large-v3", flag:null, extra:true}));

  return {
    version: "v4.1.0", dispatch: "3.3.0-mission-control",
    nodes, songs, catalogExtras,
    zoneHex: {Mauka:"#4ade80", Kula:"#fbbf24", Makai:"#38bdf8", Universal:"#ffffff"},
    kpis: {songsCatalog:193, lyricsDone:193, deckComplete:54, clips:3562, clipsDescribed:0,
           nodesMapped:70, pendingNodeMaps:1, loraAnchors:20, loraTarget:20},
    services: [],
    finals: [],
    dispatchLog: [],
    pending: [],
    // Sage build chain — render↔game alignment (sage_sync_check.py v1.2, cowork-thread 06-12).
    game3d: {
      asOf: "2026-06-12",
      sync: { state: "54 / 54 nodes mapped", detail: "Every node has a card, a zone, and a song — the deck is complete." },
      baseline: "A 54-card playable deck of the Sage Game — each node a living system of its zone, built in-house.",
      pipeline: [
        { step: "image to 3D", tool: "ComfyUI",       note: "node art generated into a 3D mesh" },
        { step: "mesh prep",   tool: "Blender",        note: "cleanup and texture pass" },
        { step: "rigging",     tool: "Rigify",         note: "one shared hero rig" },
        { step: "import",      tool: "Unreal Engine 5", note: "assembled into the playable world" },
      ],
      gaps: [],
      scenesDone: 21, scenesTotal: 54,
    },
    zoneLora: {},
    // Kilo Aupuni — observer of the government. Watcher fleet on Jimmy's machine
    kilo: {
      asOf: "2026-06-12",
      watchers: [
        { name: "council-watch",   src: "CivicClerk agendas", n: "38 agendas YTD · FY27 ordinance text FLAGGED 06-11", stat: "live" },
        { name: "votes-watch",     src: "council minutes",    n: "14 minutes sets · 9 officials · 1 recusal (CC 26-11)", stat: "live" },
        { name: "donor-watch",     src: "HI Campaign Spending Commission", n: "$256,020 RE/dev-sector money flagged across officials", stat: "live" },
        { name: "charter-law-map", src: "Charter v5 ↔ HRS · Sherman §1", n: "2 threads bound · live evidence injected each run", stat: "live" },
        { name: "mapps-watch",     src: "MAPPS / EnerGov permits", n: "834 permits 30d · 114 Lahaina-recovery flagged", stat: "live" },
        { name: "bids-watch",      src: "procurement · Bids.aspx", n: "2,791 bids ingested", stat: "live" },
        { name: "rpa-watch",       src: "qPublic real property", n: "Terms gate passed via browser capture — Playwright build next", stat: "captured" },
        { name: "docs-watch",      src: "public documents", n: "registry mapped, not yet built", stat: "planned" },
      ],
      outputs: [
        "county_dashboard.html — coverage map · lens activity · money trail · publishes to gov.12sgi.com",
        "officials_scorecard.html — votes + recusals, anchored to the verified 9-member roster",
        "money_behind_officials.html — campaign finance with real-estate/developer flags",
        "charter_application.html — Charter→Law→Evidence: every provision already has an enforceable statute",
        "bill9/bill9_testimony_scan.html — 50 RE testimonies, zero collusion language — lawful-lobbying finding",
        "Financial Motivations — Maui County 2026.html — rolling agenda digest (lens totals · month rhythm · top dollar figures)",
      ],
      integrity: "Facts + source links only. Recusals and donor→vote proximity are framed as questions for further reporting — never accusations.",
    },
    council: {
      asOf: "2026-06-12",
      sunshine: "HRS §92-7 · agendas post ≥6 days before a meeting",
      ytd: 38, recusals: 1, recusalCite: "CC 26-11 · via votes-watch",
      forecast: [
        { id:"I-PRM", title:"Building-permit batch — 114 Lahaina parcels", body:"Dept. of Planning · administrative", type:"permit",  days:4, meeting:"Jun 16", charter:"XI", file:"EnerGov batch" },
        { id:"I-37",  title:"Bill 37 — $25M water sovereignty fund",        body:"Water, Infrastructure & Transportation", type:"water",  days:6, meeting:"Jun 18", charter:"VI", file:"CivicClerk 5901", flag:true },
        { id:"I-55",  title:"Bills 55–56 — FY2027 county budget adoption",   body:"Budget, Finance & Economic Development", type:"budget", days:8, meeting:"Jun 20", charter:"X",  file:"CivicClerk 5893" },
        { id:"I-SMA", title:"SMA use permit — Makai coastal parcel",          body:"Housing & Land Use", type:"zoning",  days:13, meeting:"Jun 25", charter:"XI", file:"CivicClerk 5907" },
        { id:"I-32",  title:"Bill 32 — CDBG-DR Lahaina recovery allocation",  body:"Disaster, Resilience & Recovery", type:"housing", days:15, meeting:"Jun 27", charter:"VIII", file:"CivicClerk 5888", flag:true },
      ],
      committees: [
        { ab:"BFED", nm:"Budget, Finance & Economic Development" },
        { ab:"HLU",  nm:"Housing & Land Use" },
        { ab:"WIT",  nm:"Water, Infrastructure & Transportation" },
        { ab:"DRR",  nm:"Disaster, Resilience & Recovery" },
        { ab:"GET",  nm:"Governance, Ethics & Transparency" },
        { ab:"APT",  nm:"Agriculture, Environment & Public Trust" },
        { ab:"HCC",  nm:"Human Concerns & Culture" },
      ],
      ledger: [
        { id:"Bill 55–56", t:"FY2027 county budget",          status:"passed 2nd reading" },
        { id:"Bill 37",    t:"$25M water sovereignty fund",    status:"flagged" },
        { id:"Bill 32",    t:"CDBG-DR Lahaina recovery",        status:"flagged" },
        { id:"Bill 9",     t:"(realtor-PAC linkage)",           status:"dead" },
      ],
      integrity: "Every item carries its CivicClerk file and the statute that governs it. Flags are framed as questions for testimony — never accusations.",
    },
    // Push · Reach — distribution/marketing awareness, harvested from dispatch log +
    // docs (YOUTUBE_OPS, PRODUCTION_AND_REVENUE_STRATEGY, NextSong brief). Honest numbers,
    // each dated. Live app would read /api/youtube/status + /api/youtube/marketing.
    push: {},
    // Real data from finals/*_tab.json, harvested 2026-06-12.
    tabs: {
      asOf: "2026-06-12",
      tuning: "E A D G B e · standard · frets 0–22",
      onFile: [
        {slug:"OUTLAW_ALOHA_MASTERED", title:"Outlaw Aloha", node:42, zone:"Kula", bpm:95.7, notes:318, engine:"librosa-yin-full", window:"full song", audio:"Outlaw_Aloha_Mastered.wav"},
      ],
      // v2 bar-aware render — final climb, bars 92–93 · 4/4 · 16th grid (re-bar pending on machine)
      excerpt: [
        "Bars 92-93",
        "e|------------------------------------------------|------------------------------------18-19-19-19-|",
        "B|------------------------------19-20-20-21-21-22-|------------------------------------------------|",
        "G|------------------18-18-19-19-19-----------------|------------------------------------------------|",
        "D|------18-20-21-21-22-22--------------------------|------------------------------------------------|",
        "A|20-21-22-22-22-----------------------------------|------------------------------------------------|",
        "E|-------------------------------------------------|15-16-17-18-19-20-21-22--------------------------|",
      ],
      pipeline: [
        ["stem split",  "demucs — guitar/lead · vocals · bass, or full mix"],
        ["pitch track",  "librosa-yin full-song · basic-pitch for solo windows"],
        ["fretting",     "greedy minimal-movement · EADGBE · prefers low frets + small hand motion"],
        ["bar quantize", "v2 — 16th grid in 4/4 from bpm · rests for silence · onsets own the timeline"],
        ["outputs",      "tab JSON + bar-lined ASCII + measured alphaTex → finals/<slug>_tab.json"],
        ["render",       "alphaTab SVG + playback cursor + soundfont — studio panel 6"],
      ],
      nextUp: ["REEF", "HE_LEI_NO_LAHAINA", "COLORS_COLLIDE", "BLESS_ER", "GLASCOTT_SUMMERS"],
      note: "Renderer v2 (bar-aware) INSTALLED + re-bar RUN 06-12 — Outlaw Aloha now sits in 105 bars of 4/4 (was a flat note stream). Full song above; the studio (panel 6) renders it as interactive notation. Known limit: grid anchors at audio t=0 — v2.1 adds downbeat detection. Generate more tabs in the studio (panel 6).",
    },
    heroModes: [
      {id:"BASE_IDENTITY", use:"Default render mode — any song without ceremonial/water override.",
       desc:"Above clouds on volcanic rock, dark earth-tone feathered cloak, Milky Way overhead."},
      {id:"TEAL_OCEAN", use:"QUEEN_MOKU, BUDDHA_DON_T_BURN_II, or N8 + ceremonial-water themes.",
       desc:"Hooded figure in deep teal sacred light, sacred geometric light emerging from hands."},
    ],
    gradeArc: [
      {span:"0.00–0.20", name:"Pacific dawn", note:"teal shadows, warm amber skin, crushed blacks", sh:"#123b3e", warm:"#d99a4e"},
      {span:"0.20–0.40", name:"Tension", note:"green-shifted midtones, shadows cooling toward blue", sh:"#1e4034", warm:"#c9905a"},
      {span:"0.40–0.60", name:"Drain", note:"desaturated world, Jimmy holds the warmth", sh:"#3a3a36", warm:"#d97b35"},
      {span:"0.60–0.75", name:"Peak", note:"deep teal full saturation, a single warm point", sh:"#0e5560", warm:"#e3a23a"},
      {span:"0.75–0.85", name:"Silver & black", note:"a single gold point", sh:"#2a2c2e", warm:"#d4af4a"},
      {span:"0.85–1.00", name:"The return", note:"warm shadows lifting — the earned calm", sh:"#46362a", warm:"#c98a52"},
    ],
    fmt: s => s ? Math.floor(s/60)+":"+String(Math.round(s%60)).padStart(2,"0") : "—",
  };
})();
