/* slate-data.js
 * Reusable slate source for Element Lotus public pages (films.html, music.html).
 *
 * DATA SOURCE: production_status.json (repo root).
 * This file embeds a static snapshot for public-page rendering.
 * Regenerate values here whenever production_status.json changes.
 *
 * PUBLIC: safe to serve from the public site/ shell.
 * PRIVATE: no internal production controls, queue IDs, render paths, or
 * owner-only metadata are included here. Private production remains protected.
 */
(function () {
  window.SLATE = {
    /* source field: films_produced */
    films_produced: 36,

    /* source field: latest_films
     * These titles appear in latest_films only. No release dates, credits, or
     * synopsis data are present in production_status.json. They are rendered as
     * "listed" with status unknown until additional public metadata is available. */
    latest_films: [
      "Keys Of Starforge Partial 2Of9",
      "Luna Chronicles Partial 2Of8",
      "12 Stones Feature V Auto",
      "Children Of Nature S Source",
      "Bye Sin",
      "Bless Er",
      "Aina Lani Fa",
      "Maui Courts"
    ],

    /* source field: quadcast_songs */
    quadcast_songs: 1,

    /* source field: youtube_uploaded — null in current data */
    youtube_uploaded: null,

    /* source field: updated */
    updated: "2026-07-09 13:34 HST"
  };
}());
