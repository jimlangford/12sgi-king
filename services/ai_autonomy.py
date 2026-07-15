"""
AI Autonomy Training — teach local models to complete tasks independently.

Purpose:
  Enables your king-* Ollama models to recognize task patterns, execute
  them autonomously within safe bounds, and report outcomes without owner
  intervention. This is the foundation for true AI agency in your workboard.

Architecture:
  1. Task Recognition: Pattern-match owner messages + workboard jobs to
     known task archetypes (tracker, note, update, summarize, etc.)

  2. Autonomy Scoring: Rate each task 0-100 on whether it's safe to
     execute without owner review:
     - 100: Internal metrics, self-documenting tasks (always safe)
     - 80-99: Civic data updates, Neo4j writes (safe if validated)
     - 60-79: Content creation, reports (needs structural review)
     - 40-59: External API calls, Stripe/email (needs token validation)
     - 0-39: Social media, published content (always owner gate)

  3. Guided Execution: Feed the model task context + autonomy constraints:
     - Success criteria: "Complete when X metric reaches Y"
     - Safety gates: "Never write to production if Z condition"
     - Handoff rules: "Stop + alert owner if cost > $X"

  4. Outcome Recording: Log results back to workboard + Neo4j for auditing.

Task Archetypes (Expandable):
  ✓ internal_metric    — compute + store internal KPI (autonomy 95)
  ✓ civic_observation  — extract civic signal from data (autonomy 85)
  ✓ data_update        — validate + write to tenant/Neo4j (autonomy 70)
  ✓ document_create    — generate report/summary (autonomy 50)
  ✓ tracker_add        — create new tracker in system (autonomy 80)
  ✓ config_update      — modify safe config keys (autonomy 60)
  - social_post        — post to social media (autonomy 0)
  - email_send         — send external email (autonomy 10)
  - stripe_charge      — charge card (autonomy 5)

Usage in king-bridge executor:

  from services.ai_autonomy import classify_task, can_execute_autonomously

  entry = workboard_entry  # from poll()
  task = classify_task(entry)
  
  if task.autonomy_score >= 70:  # Safe threshold
      result = _ollama_generate(model, _build_prompt_with_autonomy(task))
      if result:
          resolve_workboard_job(entry["job"]["id"], outcome="autonomous-execution")
  else:
      # Flag for owner review
      emit_workboard_job(..., lane="creative")

Prompting:
  When autonomy is enabled, prompts include explicit success/safety gates:

    You are king-civic, trained for autonomous civic analysis.
    Task: extract_civic_signal from agenda items
    Autonomy: 85/100 — execute without owner review
    Safety Gate: Stop if confidence < 75%
    Success Criterion: Write to civic_signal table only if validated
    Timeout: 30s max execution
    Budget: $0 (local-only)

    [task context...]
"""

import json
import os
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ── Autonomy Archetype Registry ───────────────────────────────────────────────
# Each archetype defines a task category with intrinsic autonomy level,
# success criteria, and safety constraints.

@dataclass
class AutonomyArchetype:
    """Definition of a task archetype's autonomy boundary."""
    name: str
    autonomy_score: int  # 0-100: higher = safer to execute without owner
    success_criteria: str  # How to know the task completed
    safety_gates: list[str]  # Conditions that trigger owner alert
    timeout_seconds: int
    requires_owner_fields: list[str] = None  # Required in payload for execution
    description: str = ""

    def __post_init__(self):
        if self.requires_owner_fields is None:
            self.requires_owner_fields = []


ARCHETYPES = {
    "internal_metric": AutonomyArchetype(
        name="internal_metric",
        autonomy_score=95,
        success_criteria="Compute KPI from local data and store in metrics_table",
        safety_gates=[
            "Stop if local Neo4j is offline",
            "Stop if computation takes > 30s",
        ],
        timeout_seconds=30,
        description="Compute internal performance metrics (CPU, GPU, quad progress, etc.)"
    ),
    "civic_observation": AutonomyArchetype(
        name="civic_observation",
        autonomy_score=85,
        success_criteria="Extract civic signal, validate confidence > 75%, write to Neo4j civic_signal node",
        safety_gates=[
            "Stop if confidence < 75%",
            "Stop if data source is private (personal case data, internal notes)",
            "Stop if Neo4j write fails",
        ],
        timeout_seconds=45,
        requires_owner_fields=["civic_source"],
        description="Extract civic signals from agendas, votes, permits, etc."
    ),
    "tracker_add": AutonomyArchetype(
        name="tracker_add",
        autonomy_score=80,
        success_criteria="Create tracker record in tracker_queue with unique key; emit workboard event",
        safety_gates=[
            "Stop if tracker_key already exists",
            "Stop if title > 255 chars",
            "Stop if tenant_id is not in allowlist",
        ],
        timeout_seconds=20,
        requires_owner_fields=["tracker_key", "title", "tenant_id"],
        description="Add a new tracker to the system"
    ),
    "data_update": AutonomyArchetype(
        name="data_update",
        autonomy_score=70,
        success_criteria="Validate payload, update Neo4j node, record in workboard",
        safety_gates=[
            "Stop if node_id does not exist",
            "Stop if update changes >10 fields",
            "Stop if attempting destructive delete",
            "Stop if Neo4j write returns errors",
        ],
        timeout_seconds=30,
        requires_owner_fields=["node_id", "fields"],
        description="Update existing data in Neo4j"
    ),
    "config_update": AutonomyArchetype(
        name="config_update",
        autonomy_score=60,
        success_criteria="Validate key is in allowlist, update config/owner_policy.json, reload",
        safety_gates=[
            "Stop if key not in SAFE_CONFIG_KEYS",
            "Stop if value type mismatch",
            "Stop if JSON validation fails",
        ],
        timeout_seconds=15,
        requires_owner_fields=["key", "value"],
        description="Update safe configuration keys"
    ),
    "document_create": AutonomyArchetype(
        name="document_create",
        autonomy_score=50,
        success_criteria="Generate document, validate structure, save to drafts",
        safety_gates=[
            "Stop if generated content > 50KB",
            "Stop if contains PII patterns",
            "Stop if confidence scoring < 60%",
        ],
        timeout_seconds=60,
        description="Create reports, summaries, or other structured documents"
    ),
    "social_post": AutonomyArchetype(
        name="social_post",
        autonomy_score=0,
        success_criteria="NEVER autonomous — always requires owner review",
        safety_gates=[
            "ALWAYS STOP — social posts require owner approval",
        ],
        timeout_seconds=1,
        requires_owner_fields=["platform", "content"],
        description="Post to social media — owner gate required"
    ),
    "email_send": AutonomyArchetype(
        name="email_send",
        autonomy_score=10,
        success_criteria="RARELY autonomous — only internal team emails",
        safety_gates=[
            "Stop if recipient not in INTERNAL_EMAIL_ALLOWLIST",
            "Stop if content contains sensitive data markers",
        ],
        timeout_seconds=20,
        requires_owner_fields=["recipient", "subject", "body"],
        description="Send email — limited autonomy for internal-only recipients"
    ),
    "stripe_charge": AutonomyArchetype(
        name="stripe_charge",
        autonomy_score=5,
        success_criteria="ALMOST NEVER — only for automatic recurring charges",
        safety_gates=[
            "Stop unless charge is < $10",
            "Stop if customer_id not in whitelist",
            "Stop if monthly_total + charge > monthly_cap",
        ],
        timeout_seconds=30,
        requires_owner_fields=["customer_id", "amount_cents"],
        description="Charge Stripe card — extremely limited autonomy"
    ),
}

# Safe config keys that autonomy can modify without owner review
SAFE_CONFIG_KEYS = {
    "auto_approve_creative",  # Toggle creative lane auto-approval
    "auto_approve_output",
    "metrics_refresh_interval",
    "log_retention_days",
    "cache_ttl_seconds",
    "theme_preference",
}


@dataclass
class ClassifiedTask:
    """Result of classifying a workboard entry as a task."""
    archetype_name: str
    autonomy_score: int
    success_criteria: str
    safety_gates: list[str]
    timeout_seconds: int
    payload: dict
    job_id: str
    action: str
    source: str
    is_valid: bool = True
    validation_error: str = ""

    def can_execute_autonomously(self, owner_threshold: int = 70) -> bool:
        """Return True if this task is safe to execute without owner review."""
        return self.is_valid and self.autonomy_score >= owner_threshold

    def to_prompt(self) -> str:
        """Build a specialized prompt for autonomous execution."""
        lines = [
            f"You are a specialized executor, trained for autonomous task completion.",
            f"Archetype: {self.archetype_name}",
            f"Autonomy Level: {self.autonomy_score}/100",
            f"Task: {self.action}",
            f"",
            f"SUCCESS CRITERIA:",
            f"  {self.success_criteria}",
            f"",
            f"SAFETY GATES (Stop if any trigger):",
        ]
        for gate in self.safety_gates:
            lines.append(f"  • {gate}")
        lines.extend([
            f"",
            f"TIMEOUT: {self.timeout_seconds}s max execution",
            f"JOB_ID: {self.job_id} (for audit trail)",
            f"",
            f"Payload context:",
            f"{json.dumps(self.payload, indent=2)}",
            f"",
            f"Respond with:",
            f"1) Confirm archetype understanding",
            f"2) Check all safety gates — stop if any trigger",
            f"3) Execute the task",
            f"4) Validate success criteria",
            f"5) Report: COMPLETED | STOPPED | ERROR",
        ])
        return "\n".join(lines)


def classify_task(entry: dict) -> ClassifiedTask:
    """
    Classify a workboard entry into an autonomy archetype.
    
    Returns a ClassifiedTask with autonomy_score and execution constraints.
    If no archetype matches, returns a minimal task with score 0 (owner review required).
    """
    job = entry.get("job") or {}
    action = job.get("action", "").lower().strip()
    payload = job.get("payload") or {}
    job_id = job.get("id", "unknown")
    source = entry.get("source", "unknown")
    event = entry.get("event", "")

    # Try to match action to an archetype
    for arch_name, arch in ARCHETYPES.items():
        if arch_name in action or arch_name.replace("_", " ") in action.replace("_", " "):
            # Validate required fields
            missing_fields = [f for f in arch.requires_owner_fields if f not in payload]
            if missing_fields:
                return ClassifiedTask(
                    archetype_name=arch_name,
                    autonomy_score=0,
                    success_criteria=arch.success_criteria,
                    safety_gates=arch.safety_gates,
                    timeout_seconds=arch.timeout_seconds,
                    payload=payload,
                    job_id=job_id,
                    action=action,
                    source=source,
                    is_valid=False,
                    validation_error=f"Missing required fields: {', '.join(missing_fields)}"
                )
            return ClassifiedTask(
                archetype_name=arch_name,
                autonomy_score=arch.autonomy_score,
                success_criteria=arch.success_criteria,
                safety_gates=arch.safety_gates,
                timeout_seconds=arch.timeout_seconds,
                payload=payload,
                job_id=job_id,
                action=action,
                source=source,
                is_valid=True,
            )

    # No archetype match — default to owner review
    return ClassifiedTask(
        archetype_name="unknown",
        autonomy_score=0,
        success_criteria="Unknown task — requires owner review",
        safety_gates=["Unknown archetype — always stop and alert owner"],
        timeout_seconds=0,
        payload=payload,
        job_id=job_id,
        action=action,
        source=source,
        is_valid=False,
        validation_error=f"Unknown action: {action}"
    )


def build_autonomy_system_prompt(model_name: str) -> str:
    """
    Build a system prompt that teaches a king-* model autonomous execution.
    Prepend this to every user prompt to establish the autonomy framework.
    """
    return f"""You are {model_name}, a specialized autonomous agent trained to execute tasks independently within strict safety boundaries.

CORE PRINCIPLES:
1. Understand your role: You execute tasks (civic analysis, data updates, reports) without waiting for owner approval.
2. Know your limits: Safety gates define the boundary. If ANY gate triggers, STOP immediately and alert the owner.
3. Be transparent: Always log your reasoning and decisions for audit.
4. Fail gracefully: If uncertain, STOP and defer to owner rather than guessing.

AUTONOMY FRAMEWORK:
- Autonomy Score (0-100): Higher score = safer to execute alone. Below 70 = owner review required.
- Success Criteria: Your definition of task completion. Meet it or fail transparently.
- Safety Gates: Hard stops. If ANY gate triggers, you must stop and not proceed.
- Timeout: Maximum execution time. Never run longer.

TASK EXECUTION FLOW:
1. Receive task + autonomy constraints
2. Confirm archetype understanding
3. Check every safety gate — do not proceed if any trigger
4. Execute the core task
5. Validate success criteria against outcomes
6. Report: COMPLETED (with metrics) | STOPPED (reason + owner alert) | ERROR (stack trace)

AUDIT TRAIL:
All autonomous executions are logged:
- Task ID (job_id) for traceability
- Archetype name
- Safety gates checked (and their status)
- Execution time
- Success/failure outcome

Remember: You are trusted to execute safely within these bounds. Abuse of autonomy (ignoring safety gates, concealing decisions, or circumventing constraints) will result in owner intervention and autonomy restrictions.

Now, proceed with your task."""


def estimate_autonomy_score(action: str, payload: dict) -> int:
    """
    Quick heuristic to estimate autonomy score if archetype not recognized.
    Used for novel tasks not yet in ARCHETYPES.
    """
    action_lower = action.lower()
    score = 0

    # Base score on keywords
    if any(k in action_lower for k in ["metric", "health", "status", "log"]):
        score = 90  # Internal observability
    elif any(k in action_lower for k in ["civic", "extract", "summarize", "analyze"]):
        score = 75  # Civic data analysis
    elif any(k in action_lower for k in ["create", "update", "write"]):
        score = 50  # Data modifications need review
    elif any(k in action_lower for k in ["email", "notify", "alert"]):
        score = 30  # External communication
    elif any(k in action_lower for k in ["social", "post", "publish"]):
        score = 5  # Social media requires owner gate
    elif any(k in action_lower for k in ["charge", "payment", "stripe"]):
        score = 2  # Financial transactions

    # Adjust based on payload risk factors
    if "stripe" in json.dumps(payload).lower():
        score = min(score, 10)
    if "email" in json.dumps(payload).lower():
        score = min(score, 40)
    if "social" in json.dumps(payload).lower():
        score = min(score, 5)

    return max(0, min(100, score))


def record_autonomous_execution(
    job_id: str,
    task: ClassifiedTask,
    result: dict,
    db_path: Optional[Path] = None,
) -> bool:
    """
    Record an autonomous execution in SQLite audit log.
    
    Returns True if recorded successfully.
    """
    if db_path is None:
        db_path = Path(os.environ.get("AI_AUTONOMY_DB", "/data/db/ai_autonomy.db"))
    
    try:
        import sqlite3
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(db_path))
        conn.execute("""
            CREATE TABLE IF NOT EXISTS autonomous_executions (
                id TEXT PRIMARY KEY,
                job_id TEXT NOT NULL,
                archetype TEXT NOT NULL,
                autonomy_score INTEGER NOT NULL,
                status TEXT NOT NULL,
                result_json TEXT,
                created_at TEXT NOT NULL,
                execution_time_ms INTEGER
            )
        """)
        exec_id = f"{job_id}:{datetime.now(timezone.utc).isoformat()}"
        conn.execute("""
            INSERT INTO autonomous_executions
              (id, job_id, archetype, autonomy_score, status, result_json, created_at, execution_time_ms)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            exec_id,
            job_id,
            task.archetype_name,
            task.autonomy_score,
            result.get("status", "unknown"),
            json.dumps(result),
            datetime.now(timezone.utc).isoformat(),
            result.get("execution_time_ms"),
        ))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Failed to record autonomous execution: {e}")
        return False


def get_autonomy_stats(db_path: Optional[Path] = None) -> dict:
    """Retrieve autonomy execution statistics from audit log."""
    if db_path is None:
        db_path = Path(os.environ.get("AI_AUTONOMY_DB", "/data/db/ai_autonomy.db"))
    
    try:
        import sqlite3
        if not db_path.exists():
            return {"total": 0, "by_archetype": {}, "success_rate": 0}
        
        conn = sqlite3.connect(str(db_path))
        total = conn.execute("SELECT COUNT(*) FROM autonomous_executions").fetchone()[0]
        by_status = conn.execute("""
            SELECT status, COUNT(*) FROM autonomous_executions GROUP BY status
        """).fetchall()
        by_archetype = conn.execute("""
            SELECT archetype, COUNT(*), SUM(CASE WHEN status='completed' THEN 1 ELSE 0 END)
            FROM autonomous_executions GROUP BY archetype
        """).fetchall()
        conn.close()
        
        completed = sum(c for s, c in by_status if s == "completed")
        success_rate = (completed / total * 100) if total > 0 else 0
        
        return {
            "total": total,
            "by_status": {s: c for s, c in by_status},
            "by_archetype": {
                arch: {"count": count, "completed": completed}
                for arch, count, completed in by_archetype
            },
            "success_rate": round(success_rate, 1),
        }
    except Exception as e:
        print(f"Failed to retrieve autonomy stats: {e}")
        return {"error": str(e)}


if __name__ == "__main__":
    # Quick test
    test_entry = {
        "job": {
            "id": "test-123",
            "action": "civic_observation",
            "payload": {"civic_source": "agenda/2026-07-15/item-5"}
        },
        "source": "owner-console",
        "event": "Extract civic signal"
    }
    
    task = classify_task(test_entry)
    print(f"\nClassified Task:")
    print(f"  Archetype: {task.archetype_name}")
    print(f"  Autonomy: {task.autonomy_score}/100")
    print(f"  Can Execute: {task.can_execute_autonomously()}")
    print(f"\nSystem Prompt (first 500 chars):")
    print(build_autonomy_system_prompt("king-civic")[:500] + "...")
