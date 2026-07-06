# govOS app

Purpose

Main govOS v2 frontend integration scaffold.

Current implementation

- `public/index.html`: integration UI for auth, case creation, document generation, and AI guidance
- `public/app.js`: frontend service client wiring using env-provided base URLs

Configuration

Set these globals before loading `public/app.js` (or rely on localhost defaults):

- `AUTH_SERVICE_URL`
- `TENANT_SERVICE_URL`
- `DOCUMENTS_SERVICE_URL`
- `AI_SERVICE_URL`
