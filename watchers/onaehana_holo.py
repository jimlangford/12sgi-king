# -*- coding: utf-8 -*-
"""
onaehana_holo.py — the ONAEHANA HOLO food-security / traceability engine (P1 pillar, kilo-aupuni civic).

RECOVERED 2026-07-08 (self-map found the original deleted from disk, alive only in the running king_serve's
memory — a reboot would have 500'd the food-security page). This is a faithful, config-aware rebuild from the
captured live API output + the sourced data now on disk under onaehana_data/. Serves the same four surfaces
king_serve calls: traceability_report / wfcf_programs_catalog / farmbox_story / grant_catalog.

Data source: USDA NOP seed (config/onaehana_holo.json). Sourced, never fabricated. ASCII-safe, stdlib only.
"""
import json, os

_HERE = os.path.dirname(os.path.abspath(__file__))
_DATA = os.path.join(_HERE, "onaehana_data")
_ROOT = os.path.dirname(os.path.dirname(_HERE))
_CFG = os.path.join(_ROOT, "config", "onaehana_holo.json")

# HI city -> island (for island_filter + breakdown). Extend as the seed grows; unmapped ops still show in "all".
_CITY_ISLAND = {
    "holualoa": "Hawaii Island", "kailua-kona": "Hawaii Island", "kailua kona": "Hawaii Island",
    "hilo": "Hawaii Island", "kona": "Hawaii Island", "captain cook": "Hawaii Island", "honokaa": "Hawaii Island",
    "pahoa": "Hawaii Island", "keaau": "Hawaii Island", "kealakekua": "Hawaii Island", "naalehu": "Hawaii Island",
    "honolulu": "Oahu", "kailua": "Oahu", "kaneohe": "Oahu", "waimanalo": "Oahu", "wahiawa": "Oahu",
    "waianae": "Oahu", "haleiwa": "Oahu", "ewa beach": "Oahu", "kapolei": "Oahu", "aiea": "Oahu", "pearl city": "Oahu",
    "kula": "Maui", "makawao": "Maui", "haiku": "Maui", "hana": "Maui", "lahaina": "Maui", "kihei": "Maui",
    "wailuku": "Maui", "pukalani": "Maui", "kahului": "Maui", "paia": "Maui",
    "kilauea": "Kauai", "kapaa": "Kauai", "lihue": "Kauai", "koloa": "Kauai", "hanalei": "Kauai", "kalaheo": "Kauai",
    "kaunakakai": "Molokai", "hoolehua": "Molokai", "lanai city": "Lanai",
}


def _load(name, default):
    try:
        return json.load(open(os.path.join(_DATA, name + ".json"), encoding="utf-8"))
    except Exception:
        return default


def _island_of(op_result):
    try:
        city = (op_result.get("operation", {}).get("city") or "").strip().lower()
    except Exception:
        city = ""
    return _CITY_ISLAND.get(city)


class OnaehanaHolo:
    """Food-security traceability engine. Reads the sourced snapshot + catalogs from disk (onaehana_data/)."""

    def __init__(self):
        self._ops = _load("operations", [])
        self._island_breakdown = _load("island_breakdown", {})
        self._programs = _load("programs", {"ok": True, "total": 0, "programs": []})
        self._farmbox = _load("farmbox", {"ok": True})
        self._grants = _load("grants", {"ok": True, "grants": [], "total": 0})
        try:
            self._cfg = json.load(open(_CFG, encoding="utf-8"))
        except Exception:
            self._cfg = {}

    # --- owner-only grant enrichment: match an operation's programs to the grant catalog ---
    def _grants_for(self, op_result):
        progs = set((op_result.get("operation", {}).get("programs_enrolled") or []))
        certs = set(c.lower() for c in (op_result.get("operation", {}).get("certifications") or []))
        hits, amounts = [], []
        for g in self._grants.get("grants", []):
            unlocked = g.get("unlocked_by") or []
            if isinstance(unlocked, str):
                unlocked = [unlocked]
            if any(u in progs for u in unlocked) or any((u or "").lower() in certs for u in unlocked):
                hits.append(g.get("program_name") or g.get("grant_id"))
                try:
                    amounts.append(int(g.get("max_amount") or 0))
                except Exception:
                    pass
        rng = None
        if amounts:
            rng = {"min": min(amounts), "max": sum(amounts)}
        return hits, rng

    def traceability_report(self, state="HI", island_filter=None):
        results = list(self._ops)
        if island_filter:
            results = [r for r in results if (_island_of(r) or "").lower() == island_filter.strip().lower()]
        # owner grant enrichment (king_serve strips these for the public view)
        for r in results:
            hits, rng = self._grants_for(r)
            r["grants_unlocked"] = hits
            r["grant_total_range"] = rng
        # island breakdown: the full snapshot's, or recomputed for a filter
        if island_filter:
            bd = {}
            for r in results:
                isl = _island_of(r) or "Unknown"
                bd[isl] = bd.get(isl, 0) + 1
        else:
            bd = self._island_breakdown
        return {
            "ok": True, "owner_view": True, "module": "onaehana_holo",
            "mode": "PUBLIC", "tenant": self._cfg.get("tenant", "maui"),
            "operation_count": len(results), "island_breakdown": bd, "results": results,
            "data_source": self._cfg.get("data_source", "USDA_NOP_SEED"),
            "snapshot_date": self._cfg.get("snapshot_date", ""),
        }

    def wfcf_programs_catalog(self):
        return self._programs

    def farmbox_story(self):
        return self._farmbox

    def grant_catalog(self):
        return self._grants
