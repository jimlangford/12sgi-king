// elementLOTUS — self-contained loader for the hosted King System.
// No _ds_bundle.js: the King System surfaces use CSS tokens only, not compiled
// components, so we load just the token stylesheets (same dir).
(() => {
  const base = '.';
  for (const p of ["tokens/fonts.css","tokens/colors.css","tokens/typography.css","tokens/spacing.css","tokens/motion.css","tokens/cosmology.css","tokens/film.css","tokens/codex.css","tokens/ops.css","tokens/mauios.css","styles.css"]) {
    const l = document.createElement('link'); l.rel = 'stylesheet'; l.href = base + '/' + p;
    document.head.appendChild(l);
  }
})();
