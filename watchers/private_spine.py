# -*- coding: utf-8 -*-
"""private_spine.py — additive PRIVATE Neo4j relationship spine across skills + lanes.

Builds a private-only graph layer that formalizes:
  - self-heal skills and their lane/quadrant roles
  - dispatch events touching those skills
  - workboard jobs, approvals, and creative/output artifacts
  - publish-ready lineage for approved jobs with traceable provenance

This layer is additive and isolated under ``layer='private_spine'`` so it never
disturbs the existing civic graph/vector layers. It is resilient by design:
missing logs, absent selfheal registry files, or an unreachable Neo4j instance
result in a soft skip rather than a crash.
"""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
HOME = Path.home()
NEO = os.environ.get("NEO4J_HTTP", "http://127.0.0.1:7474/db/neo4j/tx/commit")
LAYER = "private_spine"
EDGE_CONTEXT_ID = "context:known-universe-edge"
APEX_CONTEXT_ID = "context:shared-apex-spine"
RHYTHM_CONTEXT_ID = "context:ao-po-rhythm"
COORDINATION_FALLBACK = HOME / "Documents" / "Claude" / "Projects" / "Video System elementLOTUS" / ".dispatch_log.jsonl"
WORKBOARD_DEFAULT = REPO / ".dispatch_log.jsonl"
STATUS_SKILLS = REPO / "reports" / "_status" / "selfheal_skills.json"
LOCAL_SKILLS = HERE / "selfheal_skills.json"

try:  # graph_refresh imports this as a loose module from HERE on sys.path
    from selfheal_learn import KW as SKILL_PATTERNS  # type: ignore
except Exception:  # pragma: no cover - import style varies by caller
    from watchers.selfheal_learn import KW as SKILL_PATTERNS  # type: ignore


SKILL_SPECS = {
    "gpu_orchestration": {
        "area": "compute",
        "lane": "engineering",
        "quadrant": "cross",
        "uses": ["service:gpu-router", "engine:ollama", "engine:comfyui", "resource:vram"],
    },
    "lora_training": {
        "area": "models",
        "lane": "engineering",
        "quadrant": "music_video",
        "uses": ["engine:kohya", "artifact:lora-model", "dataset:character-reference"],
    },
    "mesh_pipeline": {
        "area": "assets",
        "lane": "engineering",
        "quadrant": "film",
        "uses": ["artifact:mesh", "artifact:rig", "tool:accurig", "dataset:terrain"],
    },
    "deck_render": {
        "area": "creative",
        "lane": "creative",
        "quadrant": "game",
        "uses": ["artifact:sage-card", "artifact:card-render", "source:sage-node"],
    },
    "character_model": {
        "area": "creative",
        "lane": "creative",
        "quadrant": "game",
        "uses": ["artifact:character-model", "dataset:reference", "policy:likeness-boundary"],
    },
    "grants": {
        "area": "civic",
        "lane": "engineering",
        "quadrant": "govos",
        "uses": ["source:grant-program", "artifact:submission", "artifact:evidence"],
    },
    "civic_audit": {
        "area": "civic",
        "lane": "engineering",
        "quadrant": "govos",
        "uses": ["source:money-chain", "source:vendor-donor-join", "source:rep-audit", "graph:neo4j"],
    },
    "publish": {
        "area": "release",
        "lane": "output",
        "quadrant": "cross",
        "uses": ["artifact:public-output", "policy:leak-gate", "surface:site"],
    },
    "self_heal": {
        "area": "ops",
        "lane": "engineering",
        "quadrant": "cross",
        "uses": ["source:dispatch-log", "artifact:learned-rule", "surface:self-heal"],
    },
    "ops_discipline": {
        "area": "ops",
        "lane": "engineering",
        "quadrant": "cross",
        "uses": ["surface:scheduled-task", "policy:windowless", "policy:ascii-safe"],
    },
    "civic_ingest": {
        "area": "civic",
        "lane": "engineering",
        "quadrant": "govos",
        "uses": ["source:civicclerk", "source:minutes", "artifact:normalized-record"],
    },
    "cross_thread_ingest": {
        "area": "civic",
        "lane": "engineering",
        "quadrant": "cross",
        "uses": ["source:dispatch-log", "surface:thread-bus", "artifact:handoff"],
    },
    "tenant_discover": {
        "area": "tenants",
        "lane": "engineering",
        "quadrant": "govos",
        "uses": ["artifact:tenant-candidate", "source:jurisdiction-feed"],
    },
    "tenant_onboarding": {
        "area": "tenants",
        "lane": "engineering",
        "quadrant": "govos",
        "uses": ["artifact:tenant", "artifact:onboarding-checklist", "source:minutes"],
    },
    "agenda_getahead": {
        "area": "civic",
        "lane": "engineering",
        "quadrant": "govos",
        "uses": ["artifact:agenda-item", "artifact:packet", "source:meeting-calendar"],
    },
    "testimony_crosscheck": {
        "area": "civic",
        "lane": "engineering",
        "quadrant": "govos",
        "uses": ["artifact:testimony", "source:donor-network", "source:parcel"],
    },
    "civic_commerce": {
        "area": "commerce",
        "lane": "output",
        "quadrant": "govos",
        "uses": ["artifact:subscription", "artifact:entitlement", "policy:private-billing"],
    },
}

LANE_LABELS = {
    "engineering": "engineering",
    "creative": "creative",
    "output": "output",
}


def _say(message: str) -> None:
    try:
        if sys.stdout:
            print(message, flush=True)
    except Exception:
        pass


def _slug(text: object) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", str(text or "").lower()).strip("-")
    return base or "unknown"


def _read_jsonl(path: Path | None) -> list[dict]:
    if not path or not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def _load_registry_skills() -> dict[str, dict]:
    for candidate in (Path(os.environ.get("PRIVATE_SPINE_SKILLS_JSON", "")), LOCAL_SKILLS, STATUS_SKILLS):
        if candidate and str(candidate) and candidate.exists():
            try:
                data = json.loads(candidate.read_text(encoding="utf-8"))
            except Exception:
                continue
            skills = {}
            for skill in data.get("skills", []):
                sid = skill.get("id")
                if sid:
                    skills[sid] = skill
            if skills:
                return skills
    return {}


def load_skill_catalog() -> list[dict]:
    registry = _load_registry_skills()
    rows = []
    for skill_id, pattern in SKILL_PATTERNS.items():
        spec = dict(SKILL_SPECS.get(skill_id, {}))
        reg = registry.get(skill_id, {})
        rows.append(
            {
                "id": skill_id,
                "area": reg.get("area", spec.get("area", "general")),
                "lane": reg.get("lane", spec.get("lane", "engineering")),
                "quadrant": reg.get("quadrant", spec.get("quadrant", "cross")),
                "uses": list(spec.get("uses", [])),
                "pattern": pattern,
                "touches": reg.get("touches", 0),
                "learning_count": reg.get("learning_count", len(reg.get("learnings", []))),
            }
        )
    return rows


def classify_skills(text: str) -> list[str]:
    hits = []
    low = (text or "").lower()
    for skill_id, pattern in SKILL_PATTERNS.items():
        if re.search(pattern, low):
            hits.append(skill_id)
    return sorted(set(hits))


def default_dispatch_log() -> Path | None:
    override = os.environ.get("PRIVATE_SPINE_DISPATCH_LOG", "").strip()
    if override:
        return Path(override)
    if WORKBOARD_DEFAULT.exists():
        return WORKBOARD_DEFAULT
    if COORDINATION_FALLBACK.exists():
        return COORDINATION_FALLBACK
    return WORKBOARD_DEFAULT


def default_workboard_log() -> Path | None:
    override = os.environ.get("WORKBOARD_DISPATCH_LOG", "").strip()
    if override:
        return Path(override)
    return WORKBOARD_DEFAULT


def _artifact_rows_for_job(job_entry: dict) -> tuple[list[dict], list[dict]]:
    payload = ((job_entry.get("job") or {}).get("payload")) or {}
    job_id = ((job_entry.get("job") or {}).get("id")) or ""
    lane = job_entry.get("lane") or "engineering"
    if lane not in {"creative", "output"} or not job_id:
        return [], []

    artifacts = []
    edges = []

    def add_artifact(kind: str, ref: str, props: dict | None = None) -> None:
        aid = f"artifact:{kind}:{ref}"
        artifacts.append(
            {
                "id": aid,
                "kind": kind,
                "ref": ref,
                "lane": lane,
                "job_id": job_id,
                "layer": LAYER,
                **(props or {}),
            }
        )
        edges.append({"src": f"job:{job_id}", "dst": aid, "key": f"has-artifact:{aid}", "props": {"layer": LAYER}})

    if payload.get("document_id"):
        add_artifact("document", str(payload["document_id"]), {"case_id": payload.get("case_id", "")})
    if payload.get("object_id"):
        add_artifact("storage-object", str(payload["object_id"]), {"name": payload.get("name", "")})
    if payload.get("assist_id"):
        add_artifact("assist-event", str(payload["assist_id"]), {"case_id": payload.get("case_id", "")})
    if payload.get("case_id"):
        add_artifact("case", str(payload["case_id"]))
    for output_type in payload.get("output_types") or []:
        add_artifact(str(output_type), job_id, {"offering_date": payload.get("offering_date", "")})
    if not artifacts and lane == "output":
        add_artifact("publishable", job_id)
    return artifacts, edges


def job_has_publish_lineage(job_entry: dict) -> bool:
    payload = ((job_entry.get("job") or {}).get("payload")) or {}
    lane = job_entry.get("lane") or "engineering"
    if lane == "creative":
        if payload.get("civic_source") and payload.get("hina_node_id") and payload.get("offering_date"):
            return True
        if payload.get("document_id") and payload.get("case_id"):
            return True
    if lane == "output":
        return bool(payload.get("artifact_id") or payload.get("publish_target") or payload.get("document_id") or payload.get("output_types"))
    return False


def publish_ready_jobs(workboard_entries: list[dict]) -> list[dict]:
    jobs = {}
    decisions: dict[str, list[dict]] = {}
    for entry in workboard_entries:
        job = entry.get("job") or {}
        if entry.get("kind") == "job":
            jid = job.get("id")
            if jid:
                jobs[jid] = entry
        elif entry.get("kind") == "tombstone":
            corr = job.get("correlation_id")
            if corr:
                decisions.setdefault(corr, []).append(entry)
    ready = []
    for job_id, entry in jobs.items():
        lane = entry.get("lane") or "engineering"
        if lane not in {"creative", "output"}:
            continue
        if not job_has_publish_lineage(entry):
            continue
        statuses = [d.get("status") for d in decisions.get(job_id, [])]
        if "approved" in statuses:
            ready.append(entry)
    return ready


def build_private_spine(dispatch_entries: list[dict], workboard_entries: list[dict]) -> dict:
    skill_rows = load_skill_catalog()
    lane_rows = [{"id": f"lane:{lane}", "name": lane, "layer": LAYER} for lane in LANE_LABELS]
    nodes_by_id = {}
    edges_by_type: dict[str, dict[str, dict]] = {}

    def add_node(label: str, row: dict) -> None:
        rid = row["id"]
        if rid in nodes_by_id:
            nodes_by_id[rid].update(row)
            return
        nodes_by_id[rid] = {"label": label, **row, "layer": LAYER}

    def add_edge(rel: str, src: str, dst: str, key: str, props: dict | None = None) -> None:
        edges_by_type.setdefault(rel, {})[key] = {"src": src, "dst": dst, "key": key, "props": {"layer": LAYER, **(props or {})}}

    for context in (
        {
            "id": EDGE_CONTEXT_ID,
            "name": "Known universe boundary",
            "context_kind": "edge",
            "scope": "outermost",
            "note": "Outer containment boundary; not the day-to-day source of truth.",
        },
        {
            "id": APEX_CONTEXT_ID,
            "name": "Shared apex spine",
            "context_kind": "apex",
            "scope": "governing",
            "note": "Governing hierarchy for civic and accountability alignment.",
        },
        {
            "id": RHYTHM_CONTEXT_ID,
            "name": "Ao/Pō rhythm",
            "context_kind": "rhythm",
            "scope": "balancing",
            "note": "Rhythm layer for Ao action, Pō balancing, and Hina cadence.",
        },
    ):
        add_node("Context", context)
    add_edge("CONTAINS", EDGE_CONTEXT_ID, APEX_CONTEXT_ID, "context-edge-apex")
    add_edge("CONTAINS", EDGE_CONTEXT_ID, RHYTHM_CONTEXT_ID, "context-edge-rhythm")

    for lane in lane_rows:
        add_node("Lane", lane)
        add_edge("MODULATES", RHYTHM_CONTEXT_ID, lane["id"], f"rhythm-lane:{lane['name']}")

    for skill in skill_rows:
        quadrant_id = f"quadrant:{_slug(skill['quadrant'])}"
        add_node("Quadrant", {"id": quadrant_id, "name": skill["quadrant"]})
        add_edge("GOVERNS", APEX_CONTEXT_ID, quadrant_id, f"apex-quadrant:{skill['quadrant']}")
        add_node(
            "Skill",
            {
                "id": f"skill:{skill['id']}",
                "skill_id": skill["id"],
                "area": skill["area"],
                "quadrant": skill["quadrant"],
                "touches": skill["touches"],
                "learning_count": skill["learning_count"],
            },
        )
        add_edge("OPERATES_IN", f"skill:{skill['id']}", f"lane:{skill['lane']}", f"skill-lane:{skill['id']}:{skill['lane']}")
        add_edge("OPERATES_IN_QUADRANT", f"skill:{skill['id']}", quadrant_id, f"skill-quadrant:{skill['id']}:{skill['quadrant']}")
        for uses in skill.get("uses", []):
            cid = f"capability:{uses}"
            add_node("Capability", {"id": cid, "name": uses})
            add_edge("USES", f"skill:{skill['id']}", cid, f"skill-uses:{skill['id']}:{uses}")

    for idx, entry in enumerate(dispatch_entries):
        text = " ".join(
            [
                str(entry.get("event", "")),
                str(entry.get("instruction", "")),
                str(entry.get("source", "")),
            ]
        )
        event_id = entry.get("id") or f"dispatch:{idx}"
        add_node(
            "DispatchEvent",
            {
                "id": event_id,
                "event": entry.get("event", ""),
                "source": entry.get("source", ""),
                "iso": entry.get("iso", ""),
                "target_thread": entry.get("target_thread", ""),
            },
        )
        for skill_id in classify_skills(text):
            add_edge("TOUCHES_SKILL", event_id, f"skill:{skill_id}", f"dispatch-skill:{event_id}:{skill_id}")
        thread_name = entry.get("target_thread", "")
        if thread_name:
            thread_id = f"thread:{_slug(thread_name)}"
            add_node("Thread", {"id": thread_id, "thread": thread_name, "name": thread_name})
            add_edge("CONTAINS", EDGE_CONTEXT_ID, thread_id, f"edge-thread:{thread_name}")
            add_edge("GOVERNS", APEX_CONTEXT_ID, thread_id, f"apex-thread:{thread_name}")
            add_edge("FRAMES", RHYTHM_CONTEXT_ID, thread_id, f"rhythm-thread:{thread_name}")
            add_edge("ROUTES_TO_THREAD", event_id, thread_id, f"dispatch-thread:{event_id}:{thread_name}")

    jobs = []
    approvals = []
    publish_ready = publish_ready_jobs(workboard_entries)
    publish_ready_ids = {((entry.get("job") or {}).get("id")) for entry in publish_ready}

    for entry in workboard_entries:
        job = entry.get("job") or {}
        if entry.get("kind") == "job":
            jid = job.get("id")
            if not jid:
                continue
            jobs.append(
                {
                    "id": f"job:{jid}",
                    "job_id": jid,
                    "action": job.get("action", ""),
                    "status": entry.get("status", ""),
                    "lane": entry.get("lane", "engineering"),
                    "source": entry.get("source", ""),
                    "event": entry.get("event", ""),
                    "iso": entry.get("iso", ""),
                    "target_thread": entry.get("target_thread", ""),
                    "priority": entry.get("priority", ""),
                }
            )
        elif entry.get("kind") == "tombstone":
            corr = job.get("correlation_id")
            aid = job.get("id")
            if not corr or not aid:
                continue
            approvals.append(
                {
                    "id": f"approval:{aid}",
                    "approval_id": aid,
                    "job_id": corr,
                    "status": entry.get("status", ""),
                    "source": entry.get("source", ""),
                    "iso": entry.get("iso", ""),
                }
            )

    for job_row in jobs:
        add_node("WorkboardJob", job_row)
        add_edge("EMITTED_IN", job_row["id"], f"lane:{job_row['lane']}", f"job-lane:{job_row['job_id']}:{job_row['lane']}")
        thread_name = job_row.get("target_thread") or ""
        if thread_name:
            thread_id = f"thread:{_slug(thread_name)}"
            add_node("Thread", {"id": thread_id, "thread": thread_name, "name": thread_name})
            add_edge("CONTAINS", EDGE_CONTEXT_ID, thread_id, f"edge-thread:{thread_name}")
            add_edge("GOVERNS", APEX_CONTEXT_ID, thread_id, f"apex-thread:{thread_name}")
            add_edge("FRAMES", RHYTHM_CONTEXT_ID, thread_id, f"rhythm-thread:{thread_name}")
            add_edge("ROUTES_TO_THREAD", job_row["id"], thread_id, f"job-thread:{job_row['job_id']}:{thread_name}")
        matches = classify_skills(" ".join([job_row["action"], job_row["event"], job_row["source"]]))
        for skill_id in matches:
            add_edge("TOUCHES_SKILL", job_row["id"], f"skill:{skill_id}", f"job-skill:{job_row['job_id']}:{skill_id}")

    approvals_by_job = {ap["job_id"]: ap for ap in approvals if ap.get("status") in {"approved", "rejected", "done"}}
    for ap in approvals:
        add_node("Approval", ap)
        add_edge("CLEARS", ap["id"], f"job:{ap['job_id']}", f"approval-job:{ap['approval_id']}:{ap['job_id']}", {"status": ap["status"]})

    for entry in workboard_entries:
        if entry.get("kind") != "job":
            continue
        job = entry.get("job") or {}
        jid = job.get("id")
        if not jid:
            continue
        artifacts, artifact_edges = _artifact_rows_for_job(entry)
        for artifact in artifacts:
            add_node("Artifact", artifact)
        for edge in artifact_edges:
            add_edge("HAS_ARTIFACT", edge["src"], edge["dst"], edge["key"], edge["props"])

        payload = job.get("payload") or {}
        if payload.get("civic_source"):
            sid = f"source:{_slug(payload['civic_source'])}"
            add_node("SourceRef", {"id": sid, "name": payload["civic_source"], "source_kind": "civic_source"})
            add_edge("DERIVED_FROM", f"job:{jid}", sid, f"job-source:{jid}:{sid}")
        if payload.get("hina_node_id") is not None:
            nid = f"sage-node:{payload['hina_node_id']}"
            add_node(
                "SageNode",
                {
                    "id": nid,
                    "node_id": str(payload["hina_node_id"]),
                    "akua": payload.get("akua", ""),
                    "wa_phase": payload.get("wa_phase", ""),
                    "particles": payload.get("particles", ""),
                },
            )
            add_edge("ANSWERS_NODE", f"job:{jid}", nid, f"job-node:{jid}:{nid}")
            add_edge("CONTAINS", EDGE_CONTEXT_ID, nid, f"edge-node:{nid}")
            add_edge("BALANCES_THROUGH", RHYTHM_CONTEXT_ID, nid, f"rhythm-node:{nid}", {"wa_phase": payload.get("wa_phase", "")})
        if jid in approvals_by_job and jid in publish_ready_ids:
            add_edge("PUBLISH_READY", f"job:{jid}", approvals_by_job[jid]["id"], f"publish-ready:{jid}", {"status": approvals_by_job[jid]["status"]})

    return {
        "nodes": list(nodes_by_id.values()),
        "edges": {rel: list(rows.values()) for rel, rows in edges_by_type.items()},
        "publish_ready_ids": sorted(x for x in publish_ready_ids if x),
    }


def _post(statements: list[dict], timeout: float = 120):
    body = json.dumps({"statements": statements}).encode("utf-8")
    req = urllib.request.Request(NEO, data=body, headers={"Content-Type": "application/json", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            out = json.loads(resp.read().decode("utf-8", "replace"))
    except urllib.error.URLError as exc:
        _say(f"private_spine: Neo4j not reachable at {NEO} ({str(exc)[:140]})")
        return None
    if out.get("errors"):
        _say("private_spine Cypher errors: %s" % json.dumps(out.get("errors"))[:300])
    return out


def refresh(dispatch_path: Path | None = None, workboard_path: Path | None = None) -> bool:
    dispatch_entries = _read_jsonl(dispatch_path or default_dispatch_log())
    workboard_entries = _read_jsonl(workboard_path or default_workboard_log())
    payload = build_private_spine(dispatch_entries, workboard_entries)

    if _post([{"statement": "MATCH (n {layer:$layer}) DETACH DELETE n", "parameters": {"layer": LAYER}}]) is None:
        return False

    _post([{"statement": "CREATE CONSTRAINT spine_id IF NOT EXISTS FOR (x:Spine) REQUIRE x.id IS UNIQUE"}])

    nodes_by_label: dict[str, list[dict]] = {}
    for node in payload["nodes"]:
        nodes_by_label.setdefault(node["label"], []).append({k: v for k, v in node.items() if k != "label"})

    for label, rows in nodes_by_label.items():
        _post(
            [
                {
                    "statement": f"UNWIND $rows AS r MERGE (n:Spine:{label} {{id:r.id}}) SET n += r",
                    "parameters": {"rows": rows},
                }
            ]
        )

    for rel, rows in payload["edges"].items():
        if not rows:
            continue
        _post(
            [
                {
                    "statement": (
                        f"UNWIND $rows AS r MATCH (a:Spine {{id:r.src}}) MATCH (b:Spine {{id:r.dst}}) "
                        f"MERGE (a)-[e:{rel} {{key:r.key}}]->(b) SET e += r.props"
                    ),
                    "parameters": {"rows": rows},
                }
            ]
        )

    _say(
        "private_spine: loaded %d nodes, %d edges, %d publish-ready jobs."
        % (
            len(payload["nodes"]),
            sum(len(v) for v in payload["edges"].values()),
            len(payload["publish_ready_ids"]),
        )
    )
    return True
