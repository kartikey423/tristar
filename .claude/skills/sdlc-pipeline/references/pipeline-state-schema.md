# Pipeline State Schema

Write/update `.claude/checkpoints/<feature>/pipeline_state.json` after each phase:

```json
{
  "feature": "<feature-name>",
  "mode": "gates",
  "started_at": "ISO-8601",
  "updated_at": "ISO-8601",
  "phases": {
    "requirements": { "status": "pending", "completed_at": null, "iterations": 0 },
    "architecture": { "status": "pending", "completed_at": null, "iterations": 0 },
    "design-review": { "status": "pending", "completed_at": null, "iterations": 0 },
    "impl-planning": { "status": "pending", "completed_at": null, "iterations": 0 },
    "implementation": { "status": "pending", "completed_at": null, "iterations": 0 },
    "simplify": { "status": "pending", "completed_at": null, "iterations": 0 },
    "review": { "status": "pending", "completed_at": null, "iterations": 0 },
    "verification": { "status": "pending", "completed_at": null, "iterations": 0 },
    "risk": { "status": "pending", "completed_at": null, "iterations": 0 },
    "pr": { "status": "pending", "completed_at": null, "iterations": 0 }
  },
  "current_phase": "requirements",
  "iteration_counts": {
    "design_review_to_architecture": 0,
    "risk_to_implementation": 0,
    "risk_to_architecture": 0,
    "spec_review_to_implementation": 0
  }
}
```

## Checkpoint Save Procedure

After each successful phase: update pipeline_state.json (status = completed, completed_at = now, current_phase = next, updated_at = now), write to disk, confirm artifact exists.
