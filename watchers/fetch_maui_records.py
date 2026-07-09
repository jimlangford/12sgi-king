#!/usr/bin/env python3
"""fetch_maui_records.py — VP LISTENER: fetch the Maui public record to VERBATIM txt + store it (Jimmy
2026-06-20: "Go fetch all records from tenant (Maui) to txt and store on king server").

Walks ALL Maui County Legistar meeting Events (every body, newest first), pulls each meeting's MINUTES
(and, best-effort, AGENDA) PDF -> text, and persists each VERBATIM into the truth-store via record_store
(provenance + sha256, idempotent), then mirrors the store onto the King server (king-local, Tailscale,
owner-only). Re-runnable: unchanged records are skipped; new/changed are added/refreshed.

Sources here are PUBLIC + open (Legistar API + the public View.ashx PDFs) — no terms screen, no CAPTCHA.
Court records (eCourt Kokua) are a SEPARATE, terms-gated pull (not in this run). Stdlib + pypdf.
Usage: python fetch_maui_records.py [max_meetings]   (default 1000; idempotent so safe to re-run)
"""
import os, sys, io, time, shutil

HOME = os.path.expanduser("~")
PROJ = os.path.join(HOME, "Documents", "Claude", "Projects", "Video System elementLOTUS")
KILO = os.path.join(PROJ, "tools", "kilo-aupuni")
RECORD = os.path.join(PROJ, "reports", "_status", "record")
KING = [os.path.join(HOME, "AppData", "Local", "king-extract", "deploy", "king-local"),
        os.path.join(PROJ, "king-local")]
sys.path.insert(0, KILO)
import committee_minutes as cm   # reuse the Legistar fetch (cm.gt, cm.jj, cm.minutes_url_for, cm.BASE)
import record_store


def pdf_text(raw):
    import pypdf
    return "\n".join((p.extract_text() or "") for p in pypdf.PdfReader(io.BytesIO(raw)).pages)


def all_events(total_cap=6000, page=1000):
    """Paginate Maui Legistar Events (newest-first) via $skip past the 1000-row cap, to the full history."""
    import urllib.parse
    out, skip = [], 0
    while len(out) < total_cap:
        qs = urllib.parse.urlencode({"$orderby": "EventDate desc", "$top": str(page), "$skip": str(skip)})
        try:
            batch = cm.jj("%s/Events?%s" % (cm.BASE, qs))
        except Exception as e:
            print("fetch: page at skip=%d failed (%s)" % (skip, str(e)[:100])); break
        if not batch:
            break
        out.extend(batch)
        if len(batch) < page:
            break
        skip += page
    return out[:total_cap]


def _have(source, doc_id):
    return os.path.exists(os.path.join(RECORD, source, "hi-maui", record_store._slug(doc_id) + ".txt"))


def agenda_url_for(ev):
    """Best-effort agenda link (View.ashx?M=A) from the InSite meeting page."""
    import re
    insite = ev.get("EventInSiteURL")
    if not insite:
        return None
    try:
        html = cm.gt(insite)
    except Exception:
        return None
    m = re.search(r'View\.ashx\?M=A[^"\']*', html)
    return ("https://mauicounty.legistar.com/" + m.group(0).replace("&amp;", "&")) if m else None


def mirror_to_king():
    src = RECORD
    if not os.path.isdir(src):
        return None
    for kd in KING:
        if os.path.isdir(kd):
            dst = os.path.join(kd, "record")
            n = 0
            for dp, _, files in os.walk(src):
                rel = os.path.relpath(dp, src)
                outd = os.path.join(dst, rel)
                os.makedirs(outd, exist_ok=True)
                for fn in files:
                    s, d = os.path.join(dp, fn), os.path.join(outd, fn)
                    try:
                        if (not os.path.exists(d)) or os.path.getmtime(s) > os.path.getmtime(d):
                            shutil.copyfile(s, d); n += 1
                    except Exception:
                        pass
            return (dst, n)
    return None


def main():
    mx = int(sys.argv[1]) if len(sys.argv) > 1 else 6000
    evs = all_events(mx)
    print("fetch_maui_records: %d Maui Legistar events listed (cap %d, paginated)" % (len(evs), mx))
    w = u = nomin = err = ag = have = 0
    for i, ev in enumerate(evs[:mx]):
        eid = ev.get("EventId")
        date = (ev.get("EventDate") or "")[:10]
        body = ev.get("EventBodyName") or ""
        # MINUTES (primary substantive text) — skip the network fetch if already in the store
        try:
            if _have("legistar_minutes", "maui_min_%s" % eid):
                have += 1
            else:
                murl = cm.minutes_url_for(ev)
                if murl:
                    txt = pdf_text(cm.gt(murl, b=True))
                    st = record_store.put(source="legistar_minutes", tenant="hi-maui",
                                          doc_id="maui_min_%s" % eid, text=txt, url=murl, tier="primary",
                                          doc_type="minutes", title="%s %s" % (date, body), fetch_tool="fetch_maui_records")
                    w += 1 if st == "written" else 0; u += 1 if st == "unchanged" else 0
                    time.sleep(0.4)  # politeness only on a real fetch
                else:
                    nomin += 1
        except Exception:
            err += 1
        # AGENDA (best-effort) — skip if already stored
        try:
            if not _have("legistar_agenda", "maui_ag_%s" % eid):
                aurl = agenda_url_for(ev)
                if aurl:
                    atxt = pdf_text(cm.gt(aurl, b=True))
                    record_store.put(source="legistar_agenda", tenant="hi-maui",
                                     doc_id="maui_ag_%s" % eid, text=atxt, url=aurl, tier="primary",
                                     doc_type="agenda", title="%s %s (agenda)" % (date, body), fetch_tool="fetch_maui_records")
                    ag += 1
                    time.sleep(0.4)
        except Exception:
            pass
        if (i + 1) % 50 == 0:
            print("  ...%d/%d (new-min=%d already-have=%d no-minutes=%d new-agendas=%d err=%d)"
                  % (i + 1, len(evs), w, have, nomin, ag, err))
    mir = mirror_to_king()
    print("fetch_maui_records: DONE. new-minutes=%d already-have=%d | no-minutes=%d | new-agendas=%d | errors=%d"
          % (w, have, nomin, ag, err))
    if mir:
        print("  mirrored to King: %s (%d files copied)" % (mir[0], mir[1]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
