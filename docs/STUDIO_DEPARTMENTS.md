# Studio Departments — Open WebUI Model Configuration

`PRIVATE · owner-only · king-server operational reference`

This document describes the naming convention and system prompt scaffolding for
department-specific AI models in Open WebUI. Each department uses the same
backend model but receives a scoped system prompt and optionally a scoped
knowledge collection.

---

## Department Roster

| Dept ID      | Panel          | AI Role           | Records Scope           |
|:-------------|:---------------|:------------------|:------------------------|
| `writing`    | Studio Depts   | Writing AI        | Scripts, dialogue, characters, story architecture |
| `storyboard` | Studio Depts   | Director AI       | Shot plans, storyboards, continuity, blocking |
| `fcp`        | Studio Depts   | Editor AI         | Edit decisions, FCP timelines, cuts, transitions |
| `logic`      | Studio Depts   | Audio AI          | Logic sessions, ADR, Foley, music cues, stems |
| `game`       | Studio Depts   | Game AI           | Levels, NPCs, dialogue trees, quests, Unreal blueprints |
| `civic`      | Records        | Civic Records AI  | Public records, audit reports, tenants |
| `media`      | Records        | Media Assets AI   | Production files, renders, audio assets |
| `graph`      | Records        | Graph AI          | Neo4j civic + spine provenance nodes |
| `board`      | Records        | Workboard AI      | Engineering/creative/output job queue |

---

## Open WebUI Setup — Per-Department Model Preset

### 1. Model naming convention

In Open WebUI, create one **Model Preset** per department:

```
12sgi-writing-ai
12sgi-director-ai
12sgi-editor-ai
12sgi-audio-ai
12sgi-game-ai
12sgi-civic-ai
12sgi-media-ai
12sgi-graph-ai
12sgi-board-ai
```

All presets can point to the same base model (e.g. `mistral:latest` or
`llama3.1:8b`). The differentiation comes from the **system prompt** and
optional **knowledge collection**.

### 2. System prompt template

Paste the department system prompt (from `Records.dc.html`
`_recContextDefs.<dept>.prompt`) as the model preset's system message.

The owner does not need to re-paste the prompt on every session — it is
already baked into the preset. The "Send Context" / "Copy Context" buttons in
the Records panel provide an **updated prompt** that includes the active
`project_id` for per-project context.

### 3. Knowledge collections

Create a knowledge collection per department (optional but recommended):

```
12sgi-writing         — scripts/, dialogue/, characters/
12sgi-director        — storyboards/, shot_plans/, continuity/
12sgi-editor          — edit_decisions/, fcp_timelines/, cuts/
12sgi-audio           — logic_sessions/, adr/, foley/, music_cues/
12sgi-game            — game_projects/, levels/, npcs/, quests/
12sgi-civic           — reports/, minutes/, civic_records/
12sgi-media           — assets/, renders/, production_files/
12sgi-graph           — graph exports, Neo4j dumps
12sgi-board           — dispatch_log summaries, workboard snapshots
```

### 4. Frame-embedding (iframe in Records panel)

Open WebUI must be started with:

```bash
WEBUI_URL=https://<your-domain>/openwebui
```

And the nginx proxy block must include:

```nginx
add_header Content-Security-Policy "frame-ancestors 'self' https://<your-naga-origin>" always;
```

See `docs/nginx-tailnet-proxy.example.conf` for the full proxy block.

---

## Department Context Flow

```
Studio.dc.html (dept tab active)
        │
        │  "Records ↗" button clicked
        ▼
Records.dc.html?dept=writing&project_id=<uuid>
        │
        │  _initRecordsPanel() reads URL params
        │  setRecordsContext('writing', project_id)
        ▼
context prompt auto-selected + project_id appended
        │
        │  "Copy Context" / "Send Context"
        ▼
Owner pastes into Open WebUI dept preset
```

---

## Project Brain integration

When a workboard job is submitted from a studio department, include
`project_id` in the payload:

```python
emit_workboard_job(
    source="studio:writing",
    action="script:advance",
    event="writing.script.advanced",
    lane="creative",
    payload={
        "project_id": "uuid-of-active-project",
        "production_id": "prod-001",
        "scene_id": "scene-3",
        "title": "Act 2 Opening",
    },
)
```

This is the only requirement for a job to appear in the Studio Timeline panel.
The `project_id` + `scene_id` fields drive the scene grouping in
`GET /studio/projects/{id}/timeline`.

---

## Timeline stage-to-panel navigation

| Stage      | Navigates to      | Notes |
|:-----------|:------------------|:------|
| Script     | studiodepts (writing) | Writing Room tab |
| Storyboard | studiodepts (storyboard) | Storyboards tab |
| Kandinsky  | gpu               | Kandinsky is default local image engine |
| LTX        | gpu               | LTX video generation |
| Editor     | studiodepts (fcp) | FCP tab |
| Logic      | studiodepts (logic) | Logic tab |
| FCP        | studiodepts (fcp) | FCP tab |
| Release    | ops               | Owner ops board |

Clicking a stage cell in the Timeline panel calls
`navigateToPanel(panel, dept)` which stores the dept in
`localStorage('king.studioDept')` and navigates to `index.html#<panel>`.

---

`PRESERVED`: private Naga origin, king-server credentials, and owner
OAuth tokens are never stored in this document.

`NEXT`: On king-server, create the Open WebUI model presets using the
system prompts from `Records.dc.html _recContextDefs`, then set
`WEBUI_URL=https://<your-domain>/openwebui` and reload nginx.
