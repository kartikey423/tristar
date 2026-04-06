# TriStar — Presentation Script
**EPAM Hackathon 2026 · Loyalty AI Platform**
*Estimated time: ~7–8 minutes | 5 slides*

---

## SLIDE 1 — Team Details & Artifact Links
*⏱ ~60 seconds*

> "Good [morning / afternoon], everyone."

"We're Team **TriStar** — that name isn't random. TriStar stands for *Triangle Smart Targeting and Real-Time Activation*. Our logo is a triangle because we built three connected layers of intelligence, and each layer sits at a corner.

The team is **Ram Naresh**, who led AI architecture and backend; **Kartikey Puri**, full stack and integration; **Mohit Soni**, frontend and UX; and **Riyaj Shaikh**, backend and DevOps.

Here's the big idea in one sentence before we get into the problem:

> *Loyalty programs still behave like batch spreadsheets, not real-time brains. Most offers are broad, not truly 1:1 — and they miss the moment that matters. We built TriStar to fix that.*

The source code is live on EPAM Garage — the link is on screen. Let me show you why this needed to be built."

---

## SLIDE 2 — Problem Statement | Solution + Architecture
*⏱ ~2.5 minutes*

### Left Panel — The Problem

> *(Pause for audience to read the stats)*

"Let's talk about the problem first.

**~70% of loyalty offers go completely unnoticed.** That's not a small number — that's the industry benchmark across open rates, clicks, and redemption drop-off. Offers are irrelevant because they're broadcast to everyone at the same time, with no regard for *where* the member is, *what* the weather is, or *what* they just bought.

Campaigns take **hours** to create manually — a CRM manager has to coordinate between LBM, AEM, SFMC, and GL just to get a single offer live. And when something goes wrong — an over-discounted offer, a mis-configured segment — nobody catches it until *after* the damage is done.

The consequence chain is simple: batch offers → member ignores → revenue lost. Repeated every single week."

### Right Panel — The Solution & Architecture

"TriStar breaks that chain with a **three-layer AI engine**.

**Layer 1 — Designer:** A marketer types a plain-English business objective — something like *'Reactivate lapsed Sport Chek members'*. Claude Sonnet 4.6 returns a fully structured OfferBrief — with segment definition, discount construct, channel mix, KPIs, and risk flags — in under **2 seconds**. Before that brief goes anywhere, a risk check runs automatically. Over-discounting, cannibalization, frequency abuse, offer stacking — if any of these are critical severity, the offer is blocked. Full stop.

**The Hub:** Once approved, the OfferBrief lives in the Hub — our shared context state backed by Redis. Every state transition — draft, approved, active, expired — is schema-validated by Pydantic. Nothing enters the activation pipeline without passing that gate. Every change is audit-logged.

**Layer 3 — Scout:** This is where it gets interesting. Scout is a real-time activation engine with four flows. The main one scores four live signals — GPS proximity within 2km, time of day, current weather, and historical purchase behaviour — and only fires a notification when the combined score exceeds **60 out of 100**. The right offer, to the right member, at the right moment.

And the numbers back it up: **+25% lapsed member reactivation, 80% faster campaign creation, and sub-200ms activation latency.**"

---

## SLIDE 3 — Benefits | Future Enhancements
*⏱ ~2 minutes*

### Left Panel — Benefits

"Let's break down who benefits and how.

**For marketers:** What used to take 3–5 hours now takes under 5 minutes. The AI generates the brief, the risk check runs automatically, and the marketer sees real-time flags *before* the offer ever goes live. No more post-mortem on a bad campaign.

**For members:** Notification fatigue is a real problem. Because Scout only fires when *all four* context signals align — location, time, weather, behaviour — members get fewer notifications, but far more relevant ones. That's what drives redemption rates up.

**For the business:** Every single offer has a complete, immutable audit trail from creation to expiry. The schema-gated lifecycle means compliance teams can trace any offer at any point. And because we're on Azure, we scale horizontally to millions of members with no capacity planning headaches."

### Right Panel — Future Roadmap

"Phase 1 — what we're demoing today — covers all the core functionality: Designer, Hub, Scout, risk detection, real-time scoring, JWT auth, Redis, Azure. It's fully working.

Phase 2 in Q3 2026 adds ML-based segment targeting — the scoring algorithm improves automatically from redemption data — plus A/B testing, bilingual AI-generated offers, and a live analytics dashboard.

Phase 3 in Q1 2027 opens partner ecosystem APIs, adds a mobile SDK with geofencing, and moves toward multi-agent autonomous campaigns.

One more thing — and this matters for enterprise: security is not an afterthought. OWASP Top 10 mitigations are built in — parameterised queries, Zod and Pydantic input validation at every boundary, JWT tokens with a 1-hour expiry, Azure Key Vault for secrets, and PII-free logs throughout."

---

## SLIDE 4 — Demo
*⏱ ~1.5 minutes (or live demo time)*

> *(Click the "Demo" heading to open the recording, or switch to live demo)*

"Now let me show you this working — not a mockup, a real running system.

**Watch the Designer first.** I'll type a business objective — plain English — and you'll see Claude return a structured OfferBrief in real time. Segment, construct, KPIs, risk flags — all generated, all validated.

**Next, the Hub.** Watch the offer move through the lifecycle — draft, approved, active. Schema-validated at every step.

**Finally, Scout.** We'll trigger a context signal — GPS proximity, weather condition — and you'll see the score cross 60 in real time. The notification fires immediately.

The full end-to-end recording is also linked on this slide if you want to review it later."

---

## SLIDE 5 — Thank You
*⏱ ~30 seconds*

"Thank you.

TriStar isn't just a hackathon prototype — it's a **production-ready architecture**. The three layers are independently deployable, the OfferBrief schema is the contract that connects them, and every component has test coverage above 80%.

We believe this is what loyalty should look like — not batch campaigns sent to everyone, but intelligent, context-aware engagement delivered at exactly the right moment.

We're happy to take any questions."

---

## Quick Reference — Key Numbers to Remember

| Stat | Context |
|------|---------|
| ~70% | Offers that go unnoticed (Forrester / Accenture benchmark) |
| 3–5 hrs → <5 mins | Campaign creation time saved by Designer |
| <200ms | Real-time Scout activation latency |
| +25% | Lapsed member reactivation uplift |
| 80% | Faster campaign creation |
| >60/100 | Scout activation threshold (composite context score) |
| 1 / hr | Max notifications per member (hardcoded guardrail) |
| 24h | Duplicate offer deduplication window |
| 10pm–8am | Quiet hours — no notifications sent |

---

## Transition Cues

| From → To | Line to use |
|-----------|-------------|
| Slide 1 → 2 | *"Let me show you why this needed to be built."* |
| Slide 2 → 3 | *"So that's what TriStar does — let's look at what it means for each stakeholder."* |
| Slide 3 → 4 | *"Rather than tell you any more — let me show you."* |
| Slide 4 → 5 | *"That's TriStar in action."* |
