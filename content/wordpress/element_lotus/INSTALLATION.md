# ElementLOTUS WordPress rebuild package

1. Back up the current WordPress menu and page content.
2. Replace the primary navigation with `primary-navigation.html`; keep the listed legacy routes live.
3. Apply `additional-css.css` in the theme's Additional CSS.
4. Replace only the page content whose slug appears in `manifest.json`.
5. Keep the WordPress theme responsible for its single global header/footer.
6. Open every navigation destination from a signed-out browser and verify the return path. Do not expose owner/system routes in public menus.

This package is prepared for review. Building it does not update the live site.
