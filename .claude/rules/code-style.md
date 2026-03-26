# Code Style Rules

**Purpose:** Naming conventions, formatting, and linting standards for TriStar project
**Scope:** All TypeScript and Python code
**Enforcement:** ESLint (frontend), Black + isort (backend)

---

## Naming Conventions

### TypeScript/JavaScript

**Files:**
- React components: `PascalCase.tsx` (e.g., `OfferBriefForm.tsx`)
- Hooks: `use + PascalCase.ts` (e.g., `useOfferValidation.ts`)
- Utils: `camelCase.ts` (e.g., `formatCurrency.ts`)
- Types: `PascalCase.types.ts` (e.g., `OfferBrief.types.ts`)
- Tests: `<ComponentName>.test.tsx` or `<moduleName>.test.ts`

**Code:**
- Variables & functions: `camelCase`
- Types & interfaces: `PascalCase`
- Enums: `PascalCase` (keys in UPPER_SNAKE_CASE)
- Constants: `UPPER_SNAKE_CASE`
- Private properties: Prefix with `_` (e.g., `_internalState`)

**Examples:**
```typescript
// Good
const offerBriefData = {...};
function generateOfferBrief() {...}
interface OfferBrief {...}
const MAX_DISCOUNT_PCT = 30;

// Bad
const OfferbriefData = {...};
function GenerateOfferBrief() {...}
interface offerBrief {...}
const maxDiscountPct = 30;
```

### Python

**Files:**
- Modules: `snake_case.py` (e.g., `offer_generator.py`)
- Tests: `test_<module>.py` (e.g., `test_offer_generator.py`)

**Code:**
- Variables & functions: `snake_case`
- Classes: `PascalCase`
- Constants: `UPPER_SNAKE_CASE`
- Private methods: Prefix with `_` (e.g., `_validate_internal`)

**Examples:**
```python
# Good
offer_brief_data = {...}
def generate_offer_brief(): ...
class OfferBriefGenerator: ...
MAX_DISCOUNT_PCT = 0.30

# Bad
offerBriefData = {...}
def GenerateOfferBrief(): ...
class offer_brief_generator: ...
max_discount_pct = 0.30
```

---

## Formatting

### TypeScript
- **Formatter:** Prettier
- **Line width:** 100 characters
- **Indentation:** 2 spaces
- **Quotes:** Single quotes (strings), double quotes (JSX attributes)
- **Semicolons:** Required
- **Trailing commas:** Always (multiline)

**Prettier Config (`.prettierrc.json`):**
```json
{
  "printWidth": 100,
  "tabWidth": 2,
  "useTabs": false,
  "semi": true,
  "singleQuote": true,
  "trailingComma": "all",
  "arrowParens": "always"
}
```

### Python
- **Formatter:** Black
- **Line width:** 100 characters
- **Indentation:** 4 spaces
- **Import sorting:** isort (group by stdlib, third-party, local)
- **Docstrings:** Google style

**Black Config (`pyproject.toml`):**
```toml
[tool.black]
line-length = 100
target-version = ['py311']
include = '\.pyi?$'
```

---

## Linting

### TypeScript: ESLint
**Config:** Extends `@typescript-eslint/recommended`, `react/recommended`, `prettier`

**Key Rules:**
- `no-any`: Error (use `unknown` instead)
- `no-explicit-any`: Error
- `no-console`: Warn (use logger instead)
- `no-unused-vars`: Error
- `prefer-const`: Error
- `react/prop-types`: Off (TypeScript handles this)

### Python: Ruff
**Config:** Replaces flake8, isort, pyupgrade

**Key Rules:**
- `E501`: Line too long (100 chars)
- `F401`: Unused import
- `F841`: Unused variable
- `I001`: Unsorted imports
- `UP`: pyupgrade rules (modern Python syntax)

---

## Import Organization

### TypeScript
**Order:**
1. React imports
2. Third-party libraries
3. Internal modules (absolute imports)
4. Relative imports
5. Type imports (grouped at end)

**Example:**
```typescript
import React, { useState, useEffect } from 'react';
import { z } from 'zod';
import { api } from '@/services/api';
import { OfferBriefForm } from '../components/OfferBriefForm';
import type { OfferBrief, Segment } from '@/types/offer-brief';
```

### Python
**Order (isort):**
1. Standard library
2. Third-party libraries
3. Local modules

**Example:**
```python
import asyncio
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.services.offer_generator import OfferGenerator
from app.models.offer_brief import OfferBrief
```

---

## Code Organization

### File Length
- **Max file length:** 400 lines
- **If exceeding:** Split into smaller modules by responsibility

### Function Length
- **Max function length:** 50 lines
- **If exceeding:** Extract helper functions or refactor logic

### Cyclomatic Complexity
- **Max complexity:** 10
- **If exceeding:** Simplify conditionals, extract functions

---

## Comments & Documentation

### When to Comment
- **Why, not what:** Explain reasoning, not obvious code
- **Complex algorithms:** Explain non-obvious logic
- **Workarounds:** Document why hack exists and link to issue
- **TODOs:** Format as `// TODO(username): Description` with issue link

### When NOT to Comment
- **Obvious code:** `// Increment counter` for `counter++`
- **Redundant JSDoc:** If type signature is self-explanatory
- **Commented-out code:** Delete it (git history preserves)

**Good Examples:**
```typescript
// Use exponential backoff to avoid overwhelming Claude API during retries
await retryWithBackoff(generateOfferBrief, { maxAttempts: 3 });

// TODO(kpuri): Implement Redis caching after hackathon (Issue #42)
const cachedResult = null; // Temporary: return fresh data
```

**Bad Examples:**
```typescript
// Create offer brief
const offerBrief = createOfferBrief();

// Loop through members
members.forEach((member) => {...});
```

---

## TypeScript Specific

### Type Annotations
- **Function parameters:** Always annotate
- **Function return types:** Always annotate (except inline arrow functions)
- **Variables:** Omit if type is obvious from initializer

```typescript
// Good
function generateOfferBrief(objective: string): Promise<OfferBrief> {
  const segments = ['high_value', 'lapsed']; // Type inferred: string[]
  return api.post('/generate', { objective, segments });
}

// Bad
function generateOfferBrief(objective) {
  return api.post('/generate', { objective });
}
```

### Prefer Interfaces Over Types
```typescript
// Good
interface OfferBrief {
  offer_id: string;
  objective: string;
}

// Bad (use type only for unions/intersections)
type OfferBrief = {
  offer_id: string;
  objective: string;
};
```

### Avoid `any`
```typescript
// Good
function processData(data: unknown): string {
  if (typeof data === 'string') {
    return data.toUpperCase();
  }
  throw new Error('Invalid data type');
}

// Bad
function processData(data: any): string {
  return data.toUpperCase(); // No type safety
}
```

---

## Python Specific

### Type Hints
- **Function parameters:** Always annotate
- **Return types:** Always annotate
- **Use `typing` module:** For complex types (List, Dict, Optional, Union)

```python
# Good
from typing import List, Optional

def generate_offer_brief(objective: str, segments: List[str]) -> OfferBrief:
    ...

# Bad
def generate_offer_brief(objective, segments):
    ...
```

### Docstrings (Google Style)
```python
def generate_offer_brief(objective: str, segments: List[str]) -> OfferBrief:
    """Generate an OfferBrief from business objective and segment criteria.

    Args:
        objective: Business objective (e.g., "Reactivate lapsed members").
        segments: List of segment criteria (e.g., ["high_value", "lapsed"]).

    Returns:
        Generated OfferBrief with segment, construct, channels, and KPIs.

    Raises:
        ValidationError: If objective is empty or segments list is invalid.
    """
    ...
```

---

## Git Commit Messages

**Format:** Conventional Commits (`<type>: <description>`)

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation only
- `style`: Formatting (no code change)
- `refactor`: Code restructure (no behavior change)
- `test`: Add/update tests
- `chore`: Tooling, dependencies

**Examples:**
```
feat: add OfferBrief validation logic
fix: correct context matching scoring algorithm
docs: update ARCHITECTURE.md with Hub state diagram
refactor: extract fraud detection into separate service
test: add unit tests for semantic-context-matching
```

---

## Pre-Commit Hooks

**Run automatically before each commit:**
1. Prettier (format TypeScript)
2. Black + isort (format Python)
3. ESLint (lint TypeScript)
4. Ruff (lint Python)
5. TypeScript compiler (`tsc --noEmit`)
6. Unit tests (fast tests only)

**If checks fail:** Commit is blocked until fixed

---

**Enforcement:** All rules enforced via CI/CD pipeline—PRs blocked if linting fails