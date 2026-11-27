/* 12SGI public-safe manual sharing. No credentials, auto-posts, or private URLs. */
(function (root) {
  "use strict";
  const SAFE_HOSTS = new Set(["12sgi.com", "www.12sgi.com", "elementlotus.com", "www.elementlotus.com"]);
  function safePublicUrl(value) {
    try {
      const url = new URL(String(value || ""));
      if (url.protocol !== "https:" || !SAFE_HOSTS.has(url.hostname.toLowerCase()) ||
          url.username || url.password || url.port) return null;
      url.hash = "";
      return url.href;
    } catch (_) { return null; }
  }
  function shareTargets(url, title, summary) {
    const publicUrl = safePublicUrl(url);
    if (!publicUrl) return [];
    const text = [String(title || "").trim(), String(summary || "").trim()].filter(Boolean).join(" — ");
    const enc = encodeURIComponent;
    return [
      { id: "facebook", label: "Facebook", href: "https://www.facebook.com/sharer/sharer.php?u=" + enc(publicUrl) },
      { id: "linkedin", label: "LinkedIn", href: "https://www.linkedin.com/sharing/share-offsite/?url=" + enc(publicUrl) },
      { id: "bluesky", label: "Bluesky", href: "https://bsky.app/intent/compose?text=" + enc((text ? text + " " : "") + publicUrl) },
      { id: "x", label: "X", href: "https://twitter.com/intent/tweet?text=" + enc(text) + "&url=" + enc(publicUrl) },
      { id: "whatsapp", label: "WhatsApp", href: "https://api.whatsapp.com/send?text=" + enc((text ? text + " " : "") + publicUrl) },
      { id: "telegram", label: "Telegram", href: "https://t.me/share/url?url=" + enc(publicUrl) + "&text=" + enc(text) },
      { id: "email", label: "Email", href: "mailto:?subject=" + enc(title || "12 Stones civic explainer") +
        "&body=" + enc((summary ? summary + "\n\n" : "") + publicUrl) }
    ];
  }
  function addShareTools(container, data) {
    if (!container || !root.document) return false;
    const url = safePublicUrl(data && data.url);
    if (!url) {
      container.textContent = "Public sharing unavailable: an approved public URL is required.";
      return false;
    }
    const title = (data && data.title) || "12 Stones civic explainer";
    const summary = (data && data.summary) || "";
    const targets = shareTargets(url, title, summary);
    container.textContent = "";
    const bar = root.document.createElement("div");
    bar.className = "sgi-share-bar";
    bar.setAttribute("role", "group");
    bar.setAttribute("aria-label", "Share this civic explainer");
    const status = root.document.createElement("span");
    status.className = "sgi-share-status";
    status.setAttribute("role", "status");
    status.setAttribute("aria-live", "polite");
    function button(label, handler) {
      const btn = root.document.createElement("button");
      btn.type = "button"; btn.textContent = label; btn.addEventListener("click", handler);
      bar.appendChild(btn);
    }
    if (root.navigator && typeof root.navigator.share === "function") {
      button("Share", function () {
        root.navigator.share({ title: title, text: summary, url: url }).catch(function () {
          status.textContent = "Sharing was cancelled or unavailable.";
        });
      });
    }
    button("Copy link", function () {
      if (!root.navigator || !root.navigator.clipboard || !root.navigator.clipboard.writeText) {
        status.textContent = "Copy is unavailable here; use a platform link."; return;
      }
      root.navigator.clipboard.writeText(url).then(function () {
        status.textContent = "Public link copied.";
      }).catch(function () { status.textContent = "Copy failed."; });
    });
    button("Copy caption", function () {
      const caption = [title, summary, url].filter(Boolean).join("\n");
      if (!root.navigator || !root.navigator.clipboard || !root.navigator.clipboard.writeText) {
        status.textContent = "Copy is unavailable here."; return;
      }
      root.navigator.clipboard.writeText(caption).then(function () {
        status.textContent = "Caption copied.";
      }).catch(function () { status.textContent = "Copy failed."; });
    });
    targets.forEach(function (item) {
      const a = root.document.createElement("a");
      a.href = item.href;
      a.textContent = item.label;
      a.rel = "noopener noreferrer";
      if (item.id !== "email") a.target = "_blank";
      bar.appendChild(a);
    });
    container.appendChild(bar);
    container.appendChild(status);
    return true;
  }
  const api = { safePublicUrl: safePublicUrl, shareTargets: shareTargets, addShareTools: addShareTools };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  root.SGIShare = api;
})(typeof window !== "undefined" ? window : globalThis);
