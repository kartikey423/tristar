# PR Description Template

Use this template when generating PR descriptions for TriStar pull requests.

---

```markdown
## Summary
- <bullet point 1: what changed and why>
- <bullet point 2: key implementation detail>
- <bullet point 3: notable decision or trade-off>

## Layers Affected
- [ ] Designer (Layer 1)
- [ ] Hub (Layer 2)
- [ ] Scout (Layer 3)
- [ ] Shared Types

## Type of Change
- [ ] New feature (feat)
- [ ] Bug fix (fix)
- [ ] Refactor
- [ ] Documentation
- [ ] Tests

## Test Plan
- [ ] Unit tests pass (Jest / pytest)
- [ ] Integration tests pass
- [ ] E2E tests pass (Playwright)
- [ ] Coverage >80%

## Security
- [ ] Security scan passes (scripts/security-scan.sh)
- [ ] No PII in logs (member_id only)
- [ ] No secrets committed
- [ ] Input validation (Zod + Pydantic)

## Checklist
- [ ] TypeScript strict mode (no any)
- [ ] FastAPI async/await patterns
- [ ] OfferBrief schema validated (Zod + Pydantic)
- [ ] Code review completed
- [ ] Documentation updated

## SDLC Artifacts
- Problem Spec: docs/artifacts/<feature>/problem_spec.md
- Design Spec: docs/artifacts/<feature>/design_spec.md
- Verification Score: <N>/100
- Risk Assessment: <recommendation>
```

---

## Fill-In Rules

1. **Summary**: Write 2-3 bullet points. Focus on WHY, not WHAT. The diff shows what changed; the summary explains why.

2. **Layers Affected**: Check the boxes based on which directories have changes:
   - `src/frontend/` or `src/frontend/app/designer/` -> Designer
   - `src/backend/api/hub.py` or hub-related services -> Hub
   - `src/backend/api/scout.py` or scout-related services -> Scout
   - `src/shared/types/` -> Shared Types

3. **Type of Change**: Determine from commit messages and file changes. Only check one.

4. **Test Plan**: Check boxes based on what was actually run and verified.

5. **Security**: Check boxes based on security scan results. If scan was not run, note it.

6. **Checklist**: Check boxes based on code review findings. Only check if verified.

7. **SDLC Artifacts**: Fill in paths if artifacts exist. Use "N/A" if no artifacts for this change. Include verification score and risk recommendation if available.
