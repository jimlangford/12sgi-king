#!/usr/bin/env python3
"""agenda_intel.py — THE automation (Jimmy 2026-06-18 "look at agenda items and attached files; this is the
automation we need on Maui and tenants"): for each UPCOMING meeting, read every agenda ITEM and its ATTACHED
packet FILES (the PDFs where the real detail lives — developer, TMK, dollars, parties), extract the facts,
run the money lens, and surface a sourced aloha get-ahead question BEFORE the vote. Daily, per tenant.

WHY attachments: a press release names "Hoʻonani Village" but not the developer; the agenda packet does.
This reads the packet so the public learns who benefits while there is still time to testify.

BOUNDED + cached so it is daily-safe: caps meetings/items/attachments/pages; caches read PDFs by URL so it
never re-downloads. CPU + network only (no GPU). Sourced-only; every flag is a QUESTION, never an accusation;
private detail (the dollars) stays owner-side, the public board carries the question + the source link.

TENANT-PARAMETERIZED: TENANTS maps each tenant to its agenda system. Maui = Legistar (proven). Other tenants
plug in as their system/host is configured — the same skill runs everywhere.
Output: reports/_status/agenda_intel_<tenant>.json + reports/mauios/agenda_intel_<tenant>.html
"""
import os, sys, json, re, ssl, html, hashlib, io, urllib.request, urllib.parse
from datetime import datetime, date, timezone, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(os.path.dirname(HERE))
M = os.path.join(PROJ, "reports", "mauios")
ST = os.path.join(PROJ, "reports", "_status")
CACHE = os.path.join(ST, "agenda_intel_cache");
HST = timezone(timedelta(hours=-10))
UA = {"User-Agent": "12sgi-kilo-aupuni/1.0 (civic transparency; public record)"}
esc = lambda s: html.escape(str(s if s is not None else ""))

TENANTS = {
    "maui":     {"sys": "legistar", "client": "mauicounty"},   # mauicounty.legistar.com (verified)
    "honolulu": {"sys": "legistar", "client": "honolulu"},      # honolulu.legistar.com
    "hawaii":   {"sys": "legistar", "client": "hawaiicounty"},  # hawaiicounty.legistar.com
    "kauai":    {"sys": "legistar", "client": "kauai"},         # kauai.legistar.com
    # "ny":    {"sys": "legistar", "client": "nyc"},            # NYC Council Legistar — client ID pending verification
    # "state": -- State of Hawaiʻi uses capitol.hawaii.gov (not Legistar); sys type needs separate handler
}
# the matters worth getting ahead of (land-use / money / entitlement)
PRIORITY = re.compile(r"housing|affordable|zoning|rezone|district boundary|community plan|island plan|"
                      r"entitlement|development|subdivision|201h|permit|contract|award|lease|bond|"
                      r"general plan|land use|mixed.use|appropriat|grant", re.I)
MONEY = re.compile(r"\$[\s]?[\d][\d,]{3,}(?:\.\d\d)?")
TMK = re.compile(r"\(?\d\)?\s?\d-\d-\d{3}\s?:\s?\d{2,3}")
TINY = {"THE", "AND", "OF", "INC", "LLC", "LP", "DBA", "A", "FOR"}


def _get(url, raw=False, timeout=60):
    r = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout,
                               context=ssl.create_default_context())
    return r.read() if raw else r.read().decode("utf-8", "replace")


def jj(url):
    return json.loads(_get(url))


def load(p, d):
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:
        return d


def watch_names():
    """Worked entity names (watchlist + donor profiles) -> distinctive token sets, for the money lens."""
    out = []
    w = load(os.path.join(ST, "hewa_watchlist_maui.json"), {})
    for e in w.get("entities", []):
        toks = {t for t in re.sub(r"[^A-Z0-9 ]", " ", (e.get("entity") or "").upper()).split() if len(t) >= 4 and t not in TINY}
        if toks:
            out.append((toks, e.get("entity"), e.get("officials", [])))
    dp = load(os.path.join(M, "donor_profiles.json"), [])
    for prof in (dp if isinstance(dp, list) else []):
        for don in ((prof.get("realestate") or {}).get("donors") or [])[:60]:
            toks = {t for t in re.sub(r"[^A-Z0-9 ]", " ", (don.get("name") or "").upper()).split() if len(t) >= 4 and t not in TINY}
            if toks:
                out.append((toks, don.get("name"), [prof.get("label") or prof.get("key")]))
    return out


def lens(text, names):
    tn = {t for t in re.sub(r"[^A-Z0-9 ]", " ", text.upper()).split() if len(t) >= 4}
    hits = []
    for toks, name, offs in names:
        if toks and toks <= tn:
            hits.append({"entity": name, "officials": offs})
    # dedupe by entity
    seen, out = set(), []
    for h in hits:
        if h["entity"] not in seen:
            seen.add(h["entity"]); out.append(h)
    return out[:4]


def read_pdf(url, max_pages=18):
    os.makedirs(CACHE, exist_ok=True)
    key = os.path.join(CACHE, hashlib.md5(url.encode()).hexdigest() + ".txt")
    if os.path.exists(key):
        return open(key, encoding="utf-8").read()
    try:
        import pypdf
        data = _get(url, raw=True, timeout=120)
        rd = pypdf.PdfReader(io.BytesIO(data))
        txt = []
        for pg in rd.pages[:max_pages]:
            try: txt.append(pg.extract_text() or "")
            except Exception: pass
        out = re.sub(r"\s+", " ", " ".join(txt))[:60000]
        open(key, "w", encoding="utf-8").write(out)
        return out
    except Exception:
        return ""


def legistar_items(client, eid):
    out = []
    try:
        for it in jj("https://webapi.legistar.com/v1/%s/Events/%s/EventItems?$top=200" % (client, eid)):
            t = (it.get("EventItemTitle") or it.get("EventItemMatterName") or "").strip()
            if t and t.replace(" ", "") != "AGENDA":
                out.append({"title": t, "file": it.get("EventItemMatterFile"), "mid": it.get("EventItemMatterId")})
    except Exception:
        pass
    return out


def legistar_attachments(client, mid):
    if not mid:
        return []
    try:
        a = jj("https://webapi.legistar.com/v1/%s/Matters/%s/Attachments" % (client, mid))
        return [{"name": x.get("MatterAttachmentName"), "url": x.get("MatterAttachmentHyperlink")}
                for x in a if x.get("MatterAttachmentHyperlink")]
    except Exception:
        return []


def upcoming(client, days=10):
    today = date.today().isoformat()
    horizon = (date.today() + timedelta(days=days)).isoformat()
    rows = jj("https://webapi.legistar.com/v1/%s/Events?%s" % (
        client, urllib.parse.urlencode({"$orderby": "EventDate desc", "$top": "60"})))
    up = [r for r in rows if today <= str(r.get("EventDate"))[:10] <= horizon]
    return sorted(up, key=lambda r: str(r.get("EventDate"))[:10])


def build(tenant, days=10, max_meetings=4, max_items=14, max_att=2):
    cfg = TENANTS.get(tenant)
    if not cfg or cfg["sys"] != "legistar":
        return {"ok": False, "error": "tenant %s not wired for agenda_intel yet" % tenant}
    client = cfg["client"]
    names = watch_names()
    meetings_out = []
    try:
        meetings = upcoming(client, days)[:max_meetings]
    except Exception as e:
        return {"ok": False, "error": "feed: %s" % str(e)[:100]}
    for ev in meetings:
        items = legistar_items(client, ev["EventId"])
        analyzed = []
        for it in items[:max_items]:
            pri = bool(PRIORITY.search(it["title"]))
            atts = legistar_attachments(client, it["mid"])[:max_att] if pri else []
            packet = " ".join(read_pdf(a["url"]) for a in atts) if atts else ""
            blob = it["title"] + " " + packet
            money = sorted(set(MONEY.findall(blob)))[:6]
            tmk = sorted(set(TMK.findall(blob)))[:6]
            hits = lens(blob, names)
            analyzed.append({"file": it["file"], "title": it["title"][:200], "priority": pri,
                             "attachments": [a["name"] for a in atts], "attach_read": bool(packet),
                             "money_found": money, "tmk": tmk, "money_lens": hits})
        meetings_out.append({"date": str(ev.get("EventDate"))[:10], "body": ev.get("EventBodyName"),
                             "source": ev.get("EventInSiteURL"), "items": analyzed})
    flagged = [(mt, it) for mt in meetings_out for it in mt["items"] if it["money_lens"]]
    out = {"tenant": tenant, "generated": datetime.now(HST).strftime("%Y-%m-%d %H:%M:%S HST"),
           "meetings": meetings_out, "flagged_count": len(flagged),
           "integrity": ("Read from the public agenda + packet files. Every flag is a QUESTION for pono before "
                         "the vote, never an accusation; the dollars stay in the private record, the source is linked.")}
    json.dump(out, open(os.path.join(ST, "agenda_intel_%s.json" % tenant), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    _html(out)
    for mt, it in flagged:
        _dispatch("FINDING (get ahead, %s %s): agenda item \"%s\" — the packet names %s, who appear in the "
                  "donor/contract record. A question for pono before the vote: should the funded member disclose "
                  "or recuse? Source: %s" % (
                      it["file"] or "", mt["date"], it["title"][:90],
                      ", ".join(h["entity"] for h in it["money_lens"]), mt.get("source") or "Maui County Legistar"))
    return out


def _dispatch(msg):
    try:
        import subprocess
        subprocess.run([sys.executable, os.path.join(PROJ, "app", "server", "dispatch.py"), PROJ,
                        "--log-event", msg, "--source", "kilo-aupuni"],
                       capture_output=True, timeout=30, creationflags=(0x08000000 if os.name == "nt" else 0))
    except Exception:
        pass


def _html(out):
    secs = []
    for mt in out["meetings"]:
        rows = []
        for it in mt["items"]:
            if not it["priority"]:
                continue
            lens_h = ("<div class=lens>The packet names <b>%s</b> (in the donor/contract record) — a question "
                      "to verify at the source, never a claim.</div>" % esc(", ".join(h["entity"] for h in it["money_lens"]))) if it["money_lens"] else ""
            att = ("<div class=att>read packet: %s</div>" % esc("; ".join(it["attachments"][:2]))) if it["attach_read"] else ""
            rows.append("<div class=item><div class=t>%s</div>%s%s</div>" % (esc(it["title"]), att, lens_h))
        if rows:
            secs.append("<div class=mtg><div class=mh><b>%s</b> &mdash; %s</div>%s</div>"
                        % (esc(mt["body"]), esc(mt["date"]), "".join(rows)))
    body = "".join(secs) or "<div class=fine>No priority agenda items in the window yet — the watch refreshes daily.</div>"
    doc = ("<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>"
           "<title>Agenda intel — get ahead | govOS</title>"
           "<style>body{font-family:system-ui,Segoe UI,sans-serif;max-width:900px;margin:1.4rem auto;padding:0 1rem;color:#1f2d3a}"
           "h1{color:#7fb2ff;font-size:1.3rem}.lead{color:#33414f}.mtg{border:1px solid #26456a;border-radius:10px;padding:.6rem .9rem;margin:.7rem 0}"
           ".mh{color:#7fb2ff;margin-bottom:.3rem}.item{border-top:1px solid #eef3f9;padding:.45rem 0}.t{font-weight:600}"
           ".att{font-size:.78rem;color:#8b99a6}.lens{font-size:.86rem;color:#1f6f54;margin-top:.2rem}.fine{color:#9fb2c8}</style>"
           "<h1>Agenda intel — reading the packets to get ahead</h1>"
           "<p class=lead>Upcoming agenda items and their attached files, read early. Where the packet names a "
           "party who funds the deciders, we raise a question for pono &mdash; before the vote, sourced, never an "
           "accusation. %s</p>%s<p class=fine>Generated %s.</p>" % (esc(out["integrity"]), body, esc(out["generated"])))
    open(os.path.join(ST, "agenda_intel_%s.html" % out["tenant"]), "w", encoding="utf-8", newline="\n").write(doc)  # PRIVATE (money lens)


def main():
    import argparse
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--tenant", default="maui")
    ap.add_argument("--all", action="store_true", help="run every wired tenant")
    a, _ = ap.parse_known_args()
    tenants = list(TENANTS) if a.all else [a.tenant]
    for t in tenants:
        out = build(t)
        if not out.get("ok", True):
            print("agenda_intel[%s]: %s" % (t, out.get("error"))); continue
        npri = sum(1 for mt in out["meetings"] for it in mt["items"] if it["priority"])
        print("agenda_intel[%s]: %d meetings, %d priority items, %d money-lens flags -> agenda_intel_%s.{json,html}"
              % (t, len(out["meetings"]), npri, out["flagged_count"], t))
        for mt in out["meetings"]:
            for it in mt["items"]:
                if it["money_lens"]:
                    print("  FLAG %s %s -> %s" % (mt["date"], (it["file"] or it["title"][:40]),
                                                  ", ".join(h["entity"] for h in it["money_lens"])))
    return 0


if __name__ == "__main__":
    if sys.platform == "win32":
        import io as _io; sys.stdout = _io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(main())
