# Frontend Code Review Checklist

React 19 / TypeScript / Next.js 15 review checklist for TriStar project.

---

## 1. TypeScript and Type Safety
- [ ] No `any` type usage (use `unknown` and narrow)
- [ ] Strict mode enabled (no implicit any, strict null checks)
- [ ] All function parameters have type annotations
- [ ] All function return types explicitly annotated (except inline arrows)
- [ ] Interfaces preferred over type aliases for object shapes
- [ ] No type assertions (`as`) unless absolutely necessary with comment explaining why
- [ ] Generic types used where appropriate (no over-generalization)

## 2. React 19 Patterns
- [ ] Server Components are default (no unnecessary 'use client')
- [ ] React.use() for data fetching with Suspense (not useEffect + useState)
- [ ] useOptimistic for instant-feeling state updates where appropriate
- [ ] useFormStatus for form pending states
- [ ] Server Actions for form mutations (not manual fetch handlers)
- [ ] No class components
- [ ] No useEffect for data fetching (anti-pattern in React 19)
- [ ] Proper cleanup in useEffect when used (return cleanup function)

## 3. Next.js 15 (App Router)
- [ ] Pages in `app/` directory (not `pages/`)
- [ ] Server Actions in separate `actions.ts` files with 'use server'
- [ ] Proper use of 'use client' directive (only on interactive components)
- [ ] Metadata exported from page components (title, description)
- [ ] Image component used for images (`next/image`)
- [ ] Link component used for navigation (`next/link`)
- [ ] Loading and error states handled (loading.tsx, error.tsx)

## 4. Naming Conventions
- [ ] Variables and functions: camelCase
- [ ] Components: PascalCase (files and exports)
- [ ] Constants: UPPER_SNAKE_CASE
- [ ] Hooks: `use` prefix (e.g., useOfferValidation)
- [ ] Type files: PascalCase.types.ts
- [ ] Test files: ComponentName.test.tsx or moduleName.test.ts
- [ ] No abbreviations that obscure meaning

## 5. Error Handling
- [ ] Error Boundaries around Suspense components
- [ ] try/catch for async operations
- [ ] Typed error handling (not bare catch with any)
- [ ] User-friendly error messages (not raw exceptions)
- [ ] No empty catch blocks
- [ ] API errors handled with appropriate UI feedback
- [ ] Network failures handled gracefully

## 6. Imports
- [ ] Absolute imports via tsconfig paths (@/ prefix)
- [ ] No circular dependencies
- [ ] Import order: React > third-party > internal > relative > types
- [ ] No unused imports
- [ ] Tree-shakeable imports (named, not default where possible)

## 7. Async Patterns
- [ ] async/await used consistently (not .then() chains)
- [ ] No floating promises (unhandled async calls)
- [ ] AbortController used for cancellable requests
- [ ] Proper error handling on async operations
- [ ] Loading states managed during async operations

## 8. KISS and SOLID
- [ ] Components have single responsibility
- [ ] No component exceeds 400 lines (split if longer)
- [ ] No function exceeds 50 lines (extract helpers)
- [ ] No premature optimization (useMemo/useCallback only where needed)
- [ ] DRY without over-abstracting (some duplication is ok)
- [ ] No dead code or commented-out code

## 9. Performance
- [ ] Code splitting with lazy() for heavy components
- [ ] useMemo for expensive computations only
- [ ] useCallback for callbacks passed to child components
- [ ] No unnecessary re-renders (check dependency arrays)
- [ ] Images optimized (next/image, proper sizes)
- [ ] Bundle impact considered for new dependencies

## 10. Accessibility
- [ ] Semantic HTML elements (button, nav, main, article)
- [ ] ARIA labels on interactive elements without visible text
- [ ] Keyboard navigation supported (no click-only interactions)
- [ ] Focus management for modals and dynamic content
- [ ] Color contrast sufficient (not relying on color alone)
- [ ] Form inputs have associated labels

## 11. Styling (Tailwind CSS)
- [ ] Tailwind utility classes used (no inline styles)
- [ ] Responsive design (mobile-first, sm:/md:/lg: breakpoints)
- [ ] No hardcoded pixel values for spacing (use Tailwind scale)
- [ ] Conditional classes use cn() utility
- [ ] Dark mode considered (if applicable)
- [ ] Consistent spacing and layout patterns

## 12. Testing
- [ ] Test file exists for each component
- [ ] screen.getByRole preferred (not getByTestId)
- [ ] waitFor used for async assertions
- [ ] userEvent used for interactions (not fireEvent)
- [ ] Mock factories for complex test data
- [ ] Edge cases tested (empty state, error state, loading state)
- [ ] No test implementation details (test behavior, not internals)
