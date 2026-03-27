# Subagent Dispatch Templates

Use these prompt templates when launching subagents via the Task tool.

## Wave Executor (Phase 5 -- Wave Mode)

```
You are implementing files for Wave {{WAVE_NUMBER}} of the TriStar SDLC pipeline.

Feature: {{FEATURE_NAME}}
Wave files: {{WAVE_FILES}}
Prior wave files (already exist): {{PRIOR_WAVE_FILES}}

For each file in your wave:
1. Read the implementation_plan.md step for this file
2. Read the design_spec.md component definition
3. Read any files this component depends on (from prior waves)
4. Implement the file following TriStar conventions:
   - Frontend (.tsx/.ts): React 19, Server Components default, TypeScript strict, Tailwind CSS
   - Backend (.py): FastAPI async, Pydantic v2, dependency injection, loguru logging
   - Shared types: Zod (frontend) + Pydantic (backend) must mirror each other
5. Run tests after writing each file
6. Report: file path, status (completed/failed), test results

Artifacts location: docs/artifacts/{{FEATURE_NAME}}/
Rules: .claude/rules/ (react-19-standards.md, fastapi-standards.md, code-style.md, security.md, testing.md)
```

## Spec Compliance Reviewer (Phase 7)

```
You are reviewing the implementation of TriStar feature "{{FEATURE_NAME}}" against its design spec.

Read:
1. docs/artifacts/{{FEATURE_NAME}}/design_spec.md (the approved design)
2. .claude/checkpoints/{{FEATURE_NAME}}/impl_manifest.md (what was implemented)
3. The actual source files listed in the manifest

For each component in design_spec.md:
- Verify the implementation file exists at the specified path
- Verify it implements the described responsibility
- Verify API contracts match (endpoints, request/response shapes)
- Flag: over_built (implemented beyond spec), under_built (missing from spec), path_mismatches

Return: { spec_compliant: boolean, over_built: [], under_built: [], path_mismatches: [] }
```

## Security Auditor (Phase 7/8)

```
You are performing a security audit on TriStar feature "{{FEATURE_NAME}}".

Use the Skill tool to invoke "security-scan".
Focus on: Azure security (Key Vault, CORS, HTTPS), OWASP Top 10, PII handling (member_id only in logs), Claude API key protection, rate limiting configuration.

Read: .claude/checkpoints/{{FEATURE_NAME}}/impl_manifest.md for changed files list.
Read: docs/artifacts/{{FEATURE_NAME}}/design_spec.md security_considerations section.

Return: severity counts, critical findings list, remediation recommendations.
```

## Test Engineer (Phase 7)

```
You are generating and running tests for TriStar feature "{{FEATURE_NAME}}".

Use the Skill tool to invoke "generate-tests".
Read: docs/artifacts/{{FEATURE_NAME}}/design_spec.md testing_strategy section.

Dual-stack testing:
- Frontend (.tsx/.ts): Jest + React Testing Library
- Backend (.py): pytest + httpx AsyncClient
- E2E: Playwright for critical paths (Designer -> Hub -> Scout)

Coverage target: >80% on business logic.
Return: test file paths, coverage percentage, pass/fail counts.
```
