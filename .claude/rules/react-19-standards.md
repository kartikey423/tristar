# React 19 Standards

**Purpose:** Component patterns, hooks usage, and React 19 features for TriStar project
**Scope:** All React components in `src/frontend/`
**Enforcement:** Code review checks for React 19 best practices

---

## React 19 Key Features

1. **React.use()** - Data fetching with Suspense
2. **Server Components** - Render on server, send HTML to client
3. **Actions** - Form mutations with automatic pending states
4. **useOptimistic** - Optimistic UI updates
5. **Document Metadata** - Built-in `<title>` and `<meta>` support
6. **Asset Loading** - Preload resources with `<link rel="preload">`

---

## Component Structure

### Server Components (Default)

**Use by default** - No 'use client' directive needed

```tsx
// app/designer/page.tsx (Server Component)
import { fetchOffers } from '@/services/api';

export default async function DesignerPage() {
  const offers = await fetchOffers(); // Fetch on server

  return (
    <div>
      <h1>Marketer Copilot</h1>
      <OfferList offers={offers} />
    </div>
  );
}
```

**Benefits:**
- Faster initial page load (HTML sent to client)
- Smaller bundle size (server-only code not sent to client)
- Direct database/API access (no need for API routes)

### Client Components

**Use 'use client' only when needed** - For interactivity, hooks, or browser APIs

```tsx
'use client';

import { useState } from 'react';

export function OfferBriefForm({ onSubmit }: { onSubmit: (data: FormData) => void }) {
  const [objective, setObjective] = useState('');

  return (
    <form onSubmit={(e) => { e.preventDefault(); onSubmit(new FormData(e.currentTarget)); }}>
      <input
        value={objective}
        onChange={(e) => setObjective(e.target.value)}
        placeholder="Enter business objective"
      />
      <button type="submit">Generate</button>
    </form>
  );
}
```

**When to use 'use client':**
- Event handlers (onClick, onChange, onSubmit)
- React hooks (useState, useEffect, useContext)
- Browser APIs (window, document, localStorage)
- Third-party libraries that expect client-side environment

---

## Data Fetching with React.use()

### Basic Usage

```tsx
import { use, Suspense } from 'react';

function OfferDetails({ offerId }: { offerId: string }) {
  const offer = use(fetchOffer(offerId)); // Suspends until promise resolves

  return (
    <div>
      <h2>{offer.objective}</h2>
      <p>Segment: {offer.segment.name}</p>
    </div>
  );
}

export default function OfferPage({ params }: { params: { id: string } }) {
  return (
    <Suspense fallback={<LoadingSpinner />}>
      <OfferDetails offerId={params.id} />
    </Suspense>
  );
}
```

### With Error Boundaries

```tsx
import { use, Suspense } from 'react';
import { ErrorBoundary } from 'react-error-boundary';

export default function OfferPage({ params }: { params: { id: string } }) {
  return (
    <ErrorBoundary fallback={<ErrorMessage />}>
      <Suspense fallback={<LoadingSpinner />}>
        <OfferDetails offerId={params.id} />
      </Suspense>
    </ErrorBoundary>
  );
}
```

**Benefits of React.use():**
- Automatic loading states (Suspense boundary handles)
- Automatic error states (ErrorBoundary handles)
- No need for useEffect + useState pattern

---

## Server Actions (Forms)

### Basic Action

```tsx
// app/designer/actions.ts
'use server';

export async function generateOfferBrief(formData: FormData) {
  const objective = formData.get('objective') as string;

  // Validate
  if (!objective || objective.length < 10) {
    return { error: 'Objective must be at least 10 characters' };
  }

  // Call Claude API
  const offerBrief = await claudeApi.generateOfferBrief(objective);

  // Save to database
  await db.offers.create(offerBrief);

  return { success: true, offerBrief };
}
```

### Use in Form Component

```tsx
'use client';

import { generateOfferBrief } from './actions';
import { useFormStatus } from 'react-dom';

function SubmitButton() {
  const { pending } = useFormStatus();
  return (
    <button type="submit" disabled={pending}>
      {pending ? 'Generating...' : 'Generate'}
    </button>
  );
}

export function OfferBriefForm() {
  return (
    <form action={generateOfferBrief}>
      <input name="objective" placeholder="Enter business objective" required />
      <SubmitButton />
    </form>
  );
}
```

**Benefits:**
- Automatic pending states (useFormStatus)
- Progressive enhancement (works without JS)
- No need for useState + async handler

---

## Optimistic Updates with useOptimistic

### Example: Approve Offer

```tsx
'use client';

import { useOptimistic } from 'react';
import { approveOffer } from './actions';

export function OfferCard({ offer }: { offer: Offer }) {
  const [optimisticStatus, setOptimisticStatus] = useOptimistic(
    offer.status,
    (current, newStatus: string) => newStatus
  );

  async function handleApprove() {
    setOptimisticStatus('approved'); // Update UI immediately
    await approveOffer(offer.offer_id); // Send to server
  }

  return (
    <div>
      <h3>{offer.objective}</h3>
      <p>Status: {optimisticStatus}</p>
      {optimisticStatus === 'draft' && (
        <button onClick={handleApprove}>Approve</button>
      )}
    </div>
  );
}
```

**When to use:**
- Actions that should feel instant (like/approve/delete)
- When network latency is noticeable
- When action is likely to succeed (not for payments/critical ops)

---

## Hooks Best Practices

### useState

```tsx
// Good
const [objective, setObjective] = useState('');

// Bad (use reducer for complex state)
const [state, setState] = useState({
  objective: '',
  segments: [],
  loading: false,
  error: null,
});
```

### useEffect

```tsx
// Good (cleanup)
useEffect(() => {
  const controller = new AbortController();

  fetch('/api/offers', { signal: controller.signal })
    .then(res => res.json())
    .then(setOffers);

  return () => controller.abort(); // Cleanup
}, []);

// Bad (no cleanup, memory leak)
useEffect(() => {
  fetch('/api/offers').then(res => res.json()).then(setOffers);
}, []);
```

**Prefer React.use() over useEffect for data fetching**

### useCallback

```tsx
// Good (memoize callback passed to child)
const handleSubmit = useCallback((data: FormData) => {
  api.post('/generate', data);
}, []);

<OfferBriefForm onSubmit={handleSubmit} />

// Bad (creates new function on every render)
<OfferBriefForm onSubmit={(data) => api.post('/generate', data)} />
```

### useMemo

```tsx
// Good (expensive computation)
const filteredOffers = useMemo(() => {
  return offers.filter(o => o.status === 'active').sort((a, b) => b.created_at - a.created_at);
}, [offers]);

// Bad (cheap computation, no need for memo)
const fullName = useMemo(() => `${firstName} ${lastName}`, [firstName, lastName]);
```

---

## Performance Optimization

### Code Splitting

```tsx
import { lazy, Suspense } from 'react';

// Lazy load heavy component
const OfferAnalyticsDashboard = lazy(() => import('./OfferAnalyticsDashboard'));

export default function AnalyticsPage() {
  return (
    <Suspense fallback={<LoadingSpinner />}>
      <OfferAnalyticsDashboard />
    </Suspense>
  );
}
```

### Image Optimization (Next.js)

```tsx
import Image from 'next/image';

<Image
  src="/hero.jpg"
  alt="Hero image"
  width={1200}
  height={600}
  priority // Load immediately (above fold)
/>
```

### Asset Preloading

```tsx
export default function RootLayout({ children }) {
  return (
    <html>
      <head>
        <link rel="preload" href="/fonts/inter.woff2" as="font" type="font/woff2" crossOrigin="anonymous" />
        <link rel="preload" href="/api/offers" as="fetch" crossOrigin="anonymous" />
      </head>
      <body>{children}</body>
    </html>
  );
}
```

---

## Styling Patterns

### Tailwind CSS (Preferred for Hackathon)

```tsx
export function OfferCard({ offer }: { offer: Offer }) {
  return (
    <div className="rounded-lg border border-gray-200 p-6 shadow-sm hover:shadow-md transition">
      <h3 className="text-xl font-semibold text-gray-900">{offer.objective}</h3>
      <p className="mt-2 text-sm text-gray-600">Segment: {offer.segment.name}</p>
      <button className="mt-4 rounded bg-blue-600 px-4 py-2 text-white hover:bg-blue-700">
        View Details
      </button>
    </div>
  );
}
```

### Conditional Classes

```tsx
import { cn } from '@/lib/utils';

<div className={cn(
  'rounded-lg border p-4',
  offer.status === 'active' && 'border-green-500 bg-green-50',
  offer.status === 'expired' && 'border-gray-300 bg-gray-50 opacity-60'
)}>
  ...
</div>
```

---

## Accessibility

### Semantic HTML

```tsx
// Good
<button onClick={handleClick}>Click me</button>
<nav><a href="/designer">Designer</a></nav>

// Bad
<div onClick={handleClick}>Click me</div> {/* Not keyboard accessible */}
<div><span onClick={() => navigate('/designer')}>Designer</span></div>
```

### ARIA Labels

```tsx
<button aria-label="Approve offer" onClick={handleApprove}>
  <CheckIcon />
</button>

<input
  aria-label="Business objective"
  aria-describedby="objective-hint"
  placeholder="Enter objective"
/>
<p id="objective-hint" className="text-sm text-gray-500">
  Describe the marketing goal in 1-2 sentences
</p>
```

### Keyboard Navigation

```tsx
function Dialog({ isOpen, onClose }: { isOpen: boolean; onClose: () => void }) {
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };

    if (isOpen) {
      document.addEventListener('keydown', handleEscape);
      return () => document.removeEventListener('keydown', handleEscape);
    }
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return (
    <div role="dialog" aria-modal="true">
      <button onClick={onClose} aria-label="Close dialog">×</button>
      {/* Dialog content */}
    </div>
  );
}
```

---

## Testing

### Component Tests

```tsx
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { OfferBriefForm } from './OfferBriefForm';

test('submits form with valid data', async () => {
  const onSubmit = jest.fn();
  render(<OfferBriefForm onSubmit={onSubmit} />);

  await userEvent.type(screen.getByLabelText('Objective'), 'Reactivate lapsed members');
  await userEvent.click(screen.getByRole('button', { name: 'Generate' }));

  await waitFor(() => expect(onSubmit).toHaveBeenCalled());
});
```

### Testing Server Actions

```tsx
import { generateOfferBrief } from './actions';

test('generates offer brief from objective', async () => {
  const formData = new FormData();
  formData.set('objective', 'Reactivate lapsed members');

  const result = await generateOfferBrief(formData);

  expect(result.success).toBe(true);
  expect(result.offerBrief.objective).toBe('Reactivate lapsed members');
});
```

---

## Anti-Patterns to Avoid

### Don't Use useEffect for Data Fetching

```tsx
// Bad
function OfferDetails({ offerId }: { offerId: string }) {
  const [offer, setOffer] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`/api/offers/${offerId}`)
      .then(res => res.json())
      .then(data => {
        setOffer(data);
        setLoading(false);
      });
  }, [offerId]);

  if (loading) return <LoadingSpinner />;
  return <div>{offer.objective}</div>;
}

// Good (use React.use())
function OfferDetails({ offerId }: { offerId: string }) {
  const offer = use(fetchOffer(offerId));
  return <div>{offer.objective}</div>;
}
```

### Don't Overuse Client Components

```tsx
// Bad (entire page is client component)
'use client';

export default function DesignerPage() {
  return (
    <div>
      <Header /> {/* Static, could be server component */}
      <OfferBriefForm /> {/* Interactive, needs 'use client' */}
      <Footer /> {/* Static, could be server component */}
    </div>
  );
}

// Good (only interactive parts are client)
export default function DesignerPage() {
  return (
    <div>
      <Header />
      <OfferBriefFormClient /> {/* 'use client' only here */}
      <Footer />
    </div>
  );
}
```

### Don't Mutate State Directly

```tsx
// Bad
const [offers, setOffers] = useState([]);
offers.push(newOffer); // Mutates state!
setOffers(offers);

// Good
setOffers([...offers, newOffer]);
```

---

## File Organization

```
src/frontend/
├── app/                      # Next.js 15 App Router
│   ├── layout.tsx           # Root layout (Server Component)
│   ├── designer/
│   │   ├── page.tsx         # Designer page (Server Component)
│   │   ├── actions.ts       # Server Actions
│   │   └── layout.tsx
│   ├── hub/
│   │   └── page.tsx
│   └── scout/
│       └── page.tsx
├── components/              # Reusable components
│   ├── Designer/
│   │   ├── OfferBriefForm.tsx   # Client Component
│   │   └── RiskFlagDisplay.tsx
│   ├── Hub/
│   │   ├── OfferList.tsx
│   │   └── StatusBadge.tsx
│   └── Scout/
│       ├── ContextDashboard.tsx
│       └── ActivationLog.tsx
├── hooks/                   # Custom hooks
│   ├── useOfferValidation.ts
│   └── useContextMatcher.ts
└── services/               # API clients
    └── api.ts
```

---

**Remember:** React 19 Server Components are the default—only add 'use client' when you need interactivity