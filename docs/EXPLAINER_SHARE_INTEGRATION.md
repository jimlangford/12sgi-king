# Public-safe manual sharing component

Reusable browser-side sharing controls for public civic explainers and later educational content. This component only creates user-initiated browser share intents or clipboard copies. It **never** auto-publishes, collects credentials, or calls the Postiz/YouTube APIs.

The live King route `/status/explainers.html` is generated or served locally and was not found in the GitHub default branch when this component was authored. Do **not** manufacture that route in public GitHub Pages output. The local site owner must integrate this module into the canonical page generator after verifying its true repository path.

## Embed

```html
<div id="public-share" aria-label="Civic explainer sharing"></div>
<script src="/assets/sgi-share.js"></script>
<script>
  SGIShare.addShareTools(document.getElementById("public-share"), {
    url: "https://12sgi.com/agenda_explainer.html",
    title: "Civic agenda explainer",
    summary: "Learn what the public record says"
  });
</script>
```

Use a **per-explainer public canonical URL** after confirming it actually resolves, not a private Tailscale or localhost URL. Input text is placed through `textContent`, never `innerHTML`. If the URL is not on the public allowlist, the control fails closed with an explanation.

## Verification

`node --test tests/test_sgi_share.cjs`

The implementation has no build-time external dependencies, but release still requires live page integration, mobile review, accessible focus styling via the host CSS and a valid public URL for each item.

## Publishing boundary

For automatic distribution use the existing, separate approval workflow in `docs/SOCIAL_CONNECTORS.md` and the existing social workers. Staged is not approved; build/reboot is not publish. The owner-disabled Claude bridge/startup shortcuts must not be re-enabled by this feature.
