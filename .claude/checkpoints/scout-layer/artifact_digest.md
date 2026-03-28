# Artifact Digest: scout-layer

## Pipeline Stage: impl-planning COMPLETE → implementation NEXT

## Artifacts Produced

| Phase | Artifact | Path | Status |
|-------|----------|------|--------|
| 1 Requirements | problem_spec.md | `docs/artifacts/scout-layer/problem_spec.md` | ✅ Approved |
| 2 Architecture | design_spec.md | `docs/artifacts/scout-layer/design_spec.md` | ✅ Complete |
| 3 Design Review | design_review.md | `docs/artifacts/scout-layer/design_review.md` | ✅ APPROVE_WITH_CONCERNS (66/100) |
| 4 Impl Planning | implementation_plan.md | `docs/artifacts/scout-layer/implementation_plan.md` | ✅ Complete |
| 5 Implementation | impl_manifest.md | `.claude/checkpoints/scout-layer/impl_manifest.md` | ⏳ Pending |
| 6 Simplify | (appended to manifest) | `.claude/checkpoints/scout-layer/impl_manifest.md` | ⏳ Pending |
| 7 Review | code_review findings | (in context) | ⏳ Pending |
| 8 Verification | verification_report.md | `.claude/checkpoints/scout-layer/verification_report.md` | ⏳ Pending |
| 9 Risk | risk_assessment.md | `.claude/checkpoints/scout-layer/risk_assessment.md` | ⏳ Pending |
| 10 PR | PR URL | GitHub | ⏳ Pending |

## Key Numbers
- Files to implement: 24 (20 new, 4 modified)
- Waves: 6 (Wave 1 skipped — no OfferBrief changes)
- Test files: 9 new test files
- Baseline tests: TBD (run pytest --co before Wave 2)
- Target: baseline + ≥30 new passing tests, ≥80% coverage on new files

## Design Review Concerns (must address in implementation)
- F-001: Use `asyncio.wait_for(asyncio.to_thread(...), timeout=3.0)` for Claude — NOT ClaudeApiService
- F-003: All `RedisDeliveryConstraintService` methods catch `redis.RedisError` → fail-open
- F-004: `purchase_location` is Optional in model; HTTP 400 enforced at route level in scout.py
- F-005: Cap candidates at N=5, stop on first score > 60
