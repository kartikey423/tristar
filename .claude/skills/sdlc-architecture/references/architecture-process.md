# Architecture Process

10-phase architecture design process adapted for the TriStar 3-layer loyalty offer system.

---

## Phase 1: Load Problem Specification

**Input:** `docs/artifacts/<feature>/problem_spec.md`

**Actions:**
1. Read the full problem specification
2. Extract all requirements (P0, P1, P2) into a working list
3. Extract acceptance criteria for each requirement
4. Note layers affected (Designer, Hub, Scout)
5. Note non-goals (these constrain the design space)
6. Note edge cases (these must be handled in the design)
7. Note assumptions (these may affect design decisions)

**Output:** Requirements checklist that will be tracked through remaining phases

---

## Phase 2: Codebase Analysis

**Actions:**
1. Read `docs/ARCHITECTURE.md` for the baseline TriStar architecture
2. Scan `src/` directory structure to understand what exists:
   - `src/frontend/` - React 19 + Next.js 15 components
   - `src/backend/` - FastAPI routes, services, models
   - `src/shared/` - Shared types (OfferBrief, etc.)
3. Read relevant `.claude/rules/` files for coding standards:
   - `react-19-standards.md` - Frontend patterns
   - `fastapi-standards.md` - Backend patterns
   - `code-style.md` - Naming, formatting
   - `testing.md` - Test strategy
   - `security.md` - Security requirements
4. Identify existing components that can be reused or extended
5. Identify existing patterns that should be followed

**Output:** Current architecture snapshot relevant to this feature

---

## Phase 3: Document Current Architecture

**Actions:**
1. Map the current 3-layer system as it relates to this feature
2. Document existing data flows between layers
3. Document current Hub state machine
4. Document current context signals processed by Scout
5. Document current OfferBrief schema fields
6. Identify the "before" state clearly (so the "after" state is unambiguous)

**Output:** Current state section of design_spec.md

---

## Phase 4: Architecture Pattern Selection

**Actions:**
1. Review `references/tristar-patterns.md` for established patterns
2. Determine if any new architectural patterns are needed
3. For each new pattern, write an ADR:
   - Title: ADR-NNN: <decision title>
   - Context: Why this decision is needed
   - Alternatives: At least 2 options with pros and cons
   - Decision: Which option was chosen and why
   - Consequences: Impact on the system (positive and negative)
4. Verify no pattern violates the 3-layer architecture

**Output:** ADRs for new patterns, confirmation that existing patterns are followed

---

## Phase 5: Component Design

**Actions:**
1. Define every new or modified component:
   - **COMP-ID**: Unique identifier (COMP-001, COMP-002, ...)
   - **Name**: Descriptive name (e.g., WeatherContextProvider)
   - **Path**: Exact file path (e.g., `src/backend/services/weather_context.py`)
   - **Layer**: Designer / Hub / Scout / Shared
   - **Responsibility**: Single sentence describing what this component does (single responsibility)
   - **Dependencies**: List of other COMP-IDs or external services it depends on
   - **Interface**: Public API - function signatures, React props, or API endpoint

2. Verify each component:
   - Has a single responsibility
   - Lives in the correct layer directory
   - Follows naming conventions from `code-style.md`
   - Does not bypass the 3-layer architecture

**Output:** Component catalog with full specifications

---

## Phase 6: Data Flow Design

**Actions:**
1. Map each user journey as a sequence of component interactions:
   - **Happy path**: Normal operation from trigger to completion
   - **Error path**: What happens when each step fails
   - **Edge case paths**: Identified edge cases from problem spec

2. TriStar-specific flows to document:
   - **Designer -> Hub**: How does the offer get from generation to the state store?
   - **Hub -> Scout**: How does Scout discover offers to activate?
   - **End-to-end**: From marketer objective to member notification
   - **Fraud detection**: Where in the flow does fraud detection run?
   - **Rate limiting**: Where in the flow are rate limits checked?

3. Format as sequence diagrams or numbered step lists

**Output:** Data flow diagrams for each major flow

---

## Phase 7: API Contract Design

**Actions:**
1. For each new or modified API endpoint:
   - HTTP method and path (e.g., `POST /api/designer/generate`)
   - Request model name and fields (Pydantic v2 BaseModel)
   - Response model name and fields (Pydantic v2 BaseModel)
   - HTTP status codes (200, 201, 400, 401, 404, 500)
   - Error response format
   - Authentication requirement (public / JWT-authenticated)
   - Rate limit configuration

2. Verify API contracts:
   - Follow RESTful conventions
   - Use proper HTTP methods (GET for reads, POST for creates, PUT for updates)
   - Return appropriate status codes
   - Include pagination for list endpoints
   - Use async/await pattern (per fastapi-standards.md)

**Output:** API contract specifications

---

## Phase 8: Data Model Design

**Actions:**
1. Document OfferBrief schema changes (if any):
   - New fields with types and validation rules
   - Modified fields with migration strategy
   - Both Zod (frontend) and Pydantic (backend) representations

2. Document new models:
   - Pydantic v2 models for backend
   - Zod schemas for frontend validation
   - TypeScript interfaces for type safety

3. Document Hub state machine changes (if any):
   - New states
   - New transitions
   - Modified transition guards
   - Verify no orphan states possible

4. Document database schema changes (if any):
   - New tables or columns
   - Migration strategy
   - Index requirements

**Output:** Data model specifications with both TypeScript and Python representations

---

## Phase 9: Architecture Decision Records (ADRs)

**Actions:**
1. Write one ADR per significant architectural decision
2. Each ADR must include:
   - **Title**: ADR-NNN: Descriptive title
   - **Status**: Proposed
   - **Context**: Background and why this decision is needed
   - **Alternatives**: At least 2 alternatives, each with:
     - Description
     - Pros (at least 2)
     - Cons (at least 2)
   - **Decision**: Which alternative was chosen
   - **Rationale**: Why this alternative was chosen over others
   - **Consequences**: What changes as a result (positive and negative)

3. Common ADR topics for TriStar features:
   - State management approach (Redis vs in-memory)
   - Caching strategy (TTL, invalidation)
   - Context signal processing (real-time vs batch)
   - Notification delivery (sync vs async, queue choice)
   - Data model evolution (additive vs breaking change)

**Output:** ADRs section in design_spec.md

---

## Phase 10: Implementation Guidelines

**Actions:**
1. Reference the scoped rules that implementers must follow:
   - `.claude/rules/react-19-standards.md` for frontend implementation
   - `.claude/rules/fastapi-standards.md` for backend implementation
   - `.claude/rules/code-style.md` for naming and formatting
   - `.claude/rules/testing.md` for test requirements
   - `.claude/rules/security.md` for security constraints

2. Call out specific guidelines for this feature:
   - Which React 19 patterns to use (Server Components, useOptimistic, etc.)
   - Which FastAPI patterns to use (Depends, async, BackgroundTasks, etc.)
   - Security considerations specific to this feature
   - Performance targets and how to achieve them

3. Define the suggested implementation order (which components first)

4. Define integration test scenarios (how to verify the components work together)

**Output:** Implementation guidelines section in design_spec.md
