/* slate-data.js — Element Lotus public media data
 *
 * SOURCES (both are authoritative; this file embeds their PUBLIC-safe content):
 *   production_status.json  — summary counts (films_produced, quadcast_songs, updated)
 *   data/media_catalog.json — per-entry structured catalog (title, type, status, youtube_url…)
 *
 * PUBLIC: safe to serve from the public site/ shell.
 * PRIVATE: no internal production controls, render queue IDs, owner-only paths, or
 *   Tailscale hosts are included here.
 *
 * DRIFT PROTECTION: tests/test_slate_data_drift.py asserts that every PUBLIC-safe
 *   field in this file matches production_status.json. Update both files together.
 *   build_site.py regenerates site/slate-data.js from live JSON sources at build time,
 *   overwriting this checked-in copy in the site/ output.
 *
 * CONSUMERS: films.html, music.html, future Element Lotus pages, WordPress public pages.
 *
 * ARCHITECTURE:
 *   data/media_catalog.json  (per-entry)  ──┐
 *   production_status.json   (counts)     ──┼→ slate-data.js → films.html
 *                                            │                → music.html
 *                                            └──────────────→ future pages
 */
(function () {
  /* ── summary counts from production_status.json ── */
  var prodStatus = {
    films_produced: 36,
    quadcast_songs: 1,
    youtube_uploaded: null,
    updated: "2026-07-09 13:34 HST",
    latest_films: [
      "Keys Of Starforge Partial 2Of9",
      "Luna Chronicles Partial 2Of8",
      "12 Stones Feature V Auto",
      "Children Of Nature S Source",
      "Bye Sin",
      "Bless Er",
      "Aina Lani Fa",
      "Maui Courts"
    ]
  };

  /* ── per-entry catalog from data/media_catalog.json ──
   * Only PUBLIC-safe fields. No release dates, credits, or YouTube URLs are
   * fabricated — null means the field has not yet been confirmed for public release. */
  var catalog = {
    films: [
      { id: "keys-of-starforge-partial-2of9", title: "Keys Of Starforge Partial 2Of9", type: "film", status: "listed", public_visibility: true, youtube_url: null, youtube_video_id: null, thumbnail: null, release_date: null, duration: null, description: null, related_project: null, album: null, credits: null, copyright_status: "pending", tags: ["film"] },
      { id: "luna-chronicles-partial-2of8",   title: "Luna Chronicles Partial 2Of8",   type: "film", status: "listed", public_visibility: true, youtube_url: null, youtube_video_id: null, thumbnail: null, release_date: null, duration: null, description: null, related_project: null, album: null, credits: null, copyright_status: "pending", tags: ["film"] },
      { id: "12-stones-feature-v-auto",       title: "12 Stones Feature V Auto",       type: "film", status: "listed", public_visibility: true, youtube_url: null, youtube_video_id: null, thumbnail: null, release_date: null, duration: null, description: null, related_project: null, album: null, credits: null, copyright_status: "pending", tags: ["film"] },
      { id: "children-of-nature-s-source",    title: "Children Of Nature S Source",    type: "film", status: "listed", public_visibility: true, youtube_url: null, youtube_video_id: null, thumbnail: null, release_date: null, duration: null, description: null, related_project: null, album: null, credits: null, copyright_status: "pending", tags: ["film"] },
      { id: "bye-sin",                        title: "Bye Sin",                        type: "film", status: "listed", public_visibility: true, youtube_url: null, youtube_video_id: null, thumbnail: null, release_date: null, duration: null, description: null, related_project: null, album: null, credits: null, copyright_status: "pending", tags: ["film"] },
      { id: "bless-er",                       title: "Bless Er",                       type: "film", status: "listed", public_visibility: true, youtube_url: null, youtube_video_id: null, thumbnail: null, release_date: null, duration: null, description: null, related_project: null, album: null, credits: null, copyright_status: "pending", tags: ["film"] },
      { id: "aina-lani-fa",                   title: "Aina Lani Fa",                   type: "film", status: "listed", public_visibility: true, youtube_url: null, youtube_video_id: null, thumbnail: null, release_date: null, duration: null, description: null, related_project: null, album: null, credits: null, copyright_status: "pending", tags: ["film"] },
      { id: "maui-courts",                    title: "Maui Courts",                    type: "film", status: "listed", public_visibility: true, youtube_url: null, youtube_video_id: null, thumbnail: null, release_date: null, duration: null, description: null, related_project: null, album: null, credits: null, copyright_status: "pending", tags: ["film"] }
    ],
    /* music entries: catalog is in early growth — no confirmed song titles yet.
     * Count is in prodStatus.quadcast_songs. Add entries here as titles are confirmed. */
    music: []
  };

  window.SLATE = {
    films_produced:  prodStatus.films_produced,
    quadcast_songs:  prodStatus.quadcast_songs,
    youtube_uploaded: prodStatus.youtube_uploaded,
    updated:         prodStatus.updated,
    latest_films:    prodStatus.latest_films,  /* kept for backward compat */
    catalog:         catalog
  };
}());

