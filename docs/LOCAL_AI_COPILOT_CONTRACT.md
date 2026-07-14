# Local AI ↔ Copilot Contract

`PRIVATE` + `BRIDGE` operating contract for local-first task execution.

## 1) Complete task packet contract

Local AI must send a full packet before execution:

- `packet_id`
- `goal`
- `constraints` (non-empty list)
- `boundary_label` (`PUBLIC`, `PRIVATE`, `BRIDGE`, `DO NOT TOUCH`, `VERIFY`)
- `expected_output`
- `verification_target`
- `lane` (`engineering`, `creative`, `output`)

Validation helper: `/home/runner/work/12sgi-king/12sgi-king/services/local_ai_contract.py::validate_task_packet()`.

Template: `/home/runner/work/12sgi-king/12sgi-king/docs/local_ai_templates/task_packet.template.json`.

## 2) Lane alignment and approval behavior

Use existing workboard lane rules from `services/v2_workboard.py`:

- `engineering`: can auto-resolve when confidence is high and visibility is full.
- `creative`: owner review required.
- `output`: owner review required.

Decision helper: `/home/runner/work/12sgi-king/12sgi-king/services/local_ai_contract.py::lane_resolution_policy()`.

## 3) Standard handoff format (every cycle)

Every cycle records:

1. `context_in`
2. `decision_request`
3. `execution_result`
4. `verification_result`
5. `next_action`

Builder helper: `/home/runner/work/12sgi-king/12sgi-king/services/local_ai_contract.py::build_handoff_record()`.

Template: `/home/runner/work/12sgi-king/12sgi-king/docs/local_ai_templates/handoff_cycle.template.json`.

## 4) Refinement loop (required)

After each task, record:

- friction points
- missing context
- memory candidates
- tuning actions (prompt/routing/lane defaults)

Helper: `/home/runner/work/12sgi-king/12sgi-king/services/local_ai_contract.py::record_refinement_entry()`.

Template: `/home/runner/work/12sgi-king/12sgi-king/docs/local_ai_templates/refinement_entry.template.json`.

## 5) Authority and fallback

- Local AI is control authority by default.
- Copilot is execution/support.
- Fallback to owner-review is deterministic on:
  - lane requiring approval (`creative`, `output`)
  - confidence `< 0.70`
  - non-full visibility
  - local authority disabled

## 6) Efficiency scorecard

Track and tune collaboration quality with:

- `rework_count`
- `clarification_count`
- `avg_turnaround_seconds`
- `approval_pass_rate`

Helpers:

- `/home/runner/work/12sgi-king/12sgi-king/services/local_ai_contract.py::scorecard_from_cycles()`
- `/home/runner/work/12sgi-king/12sgi-king/services/local_ai_contract.py::scorecard_from_jsonl()`

Use scorecard trends to improve prompts, routing, and lane defaults.
