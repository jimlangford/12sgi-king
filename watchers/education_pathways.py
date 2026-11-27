"""Offline educational pathways using the existing civic education map.
No publishing, network requests, student records or inferred film approvals.
Run from repo root: python -m watchers.education_pathways --grade g68
"""
import argparse
import json
from watchers.education_to_graph import GRADE_BANDS, CIVIC_TOOLS, USES

GAMES = {
    "k2": ("konane", "games/konane.html", "With an adult, practice taking turns."),
    "g35": ("konane", "games/konane.html", "Explain a move and listen to another player's reasoning."),
    "g68": ("sage", "sage/index.html", "Compare a simulated resource decision with a public record."),
    "g912": ("sage", "sage/index.html", "Discuss tradeoffs in a simulated community decision."),
    "college": ("weiqi", "games/weiqi.html", "Compare strategic choices with a documented policy decision."),
    "grad": ("sage", "sage/index.html", "Evaluate simulation assumptions against documented evidence."),
}

def pathway(grade):
    if grade not in GAMES:
        raise ValueError("Unknown grade band")
    band = next(g for g in GRADE_BANDS if g["id"] == grade)
    tools = {t["id"]: t for t in CIVIC_TOOLS}
    game, url, activity = GAMES[grade]
    return {
        "grade": band["id"],
        "label": band["label"],
        "civic": [
            {"tool": t, "url": tools[t]["url"], "activity": a}
            for g, t, a in USES if g == grade
        ],
        "game": {"id": game, "url": url, "activity": activity,
                 "classification": "simulation_not_evidence"},
        "film": {"status": "awaiting_approved_asset", "assets": [],
                 "activity": "Distinguish storytelling from documented public records."},
        "publishing": {"status": "not_staged", "account_scope": "education"},
    }

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--grade", choices=list(GAMES))
    args = parser.parse_args()
    print(json.dumps(pathway(args.grade) if args.grade else
                     [pathway(g["id"]) for g in GRADE_BANDS], ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
