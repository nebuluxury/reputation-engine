# Reputation Engine - Technical Specification (v1.0)

Multi-tenant NFC "tap-to-review" platform with server-side routing, sentiment triage, reseller commissions, and Stripe subscriptions. Designed to be assembled quickly with AI coding tools.

---

## 1. Core architectural principle

**Write each card once. Control everything server-side.**

Every NFC card is encoded a single time with a permanent, unguessable URL:

```
https://app.DOMAIN.com/t/{cardId}
```

The card is never re-encoded. On tap, the server resolves `cardId -> business -> current settings` and decides where to route the visitor. "Activating" or re-pointing a card is a DB update, not physical access. This is what makes fulfillment instant and the system scalable.

### Tap request flow
```
GET /t/:cardId
  1. Look up card. If unassigned/disabled -> generic fallback page.
  2. Load business + brand + review_url + subscription flags.
  3. Render branded rating page (server-rendered, fast, edge-friendly).
  4. Visitor selects 1-5 stars (client POSTs to /api/tap):
       - 4-5 stars: record tap, 302 redirect to business.review_url
       - 1-3 stars: record tap, show private feedback form
                    (public review link is STILL shown -> stays compliant)
  5. On feedback submit -> store + Twilio SMS + Resend email to owner.
```

> **Compliance (non-negotiable in code):** the low-rating branch must still surface the public review link. Do **not** hard-gate reviews. Enforce "feedback-first, not review-blocking" at the component level so no config can turn it into review gating (a Google/Yelp/FTC violation that can get a client's reviews removed).

---

## 2. Recommended stack

| Layer | Choice | Notes |
|---|---|---|
| Framework | **Next.js (App Router)** | One codebase: marketing site, dashboards, tap pages, API. Alt: Lovable/React for visual AI build. |
| DB + Auth | **Supabase (Postgres)** | Row-Level Security for tenant isolation, built-in auth/roles. Alt: Postgres + Clerk/Auth.js. |
| Hosting | **Vercel** or **Cloudflare** | Run `/t/:cardId` at the edge for low-latency taps. |
| Payments | **Stripe** | $15/mo subscriptions, card-order checkout, optional Connect payouts. |
| SMS | **Twilio** | Instant low-rating alert to owner. |
| Email | **Resend** | Alerts, order confirmations, activation notices. |
| NFC | **NTAG213** + NFC Tools app | Or bulk pre-encoding by vendor via CSV of URLs. |

---

## 3. Roles & tenancy

- **Super Admin (us):** manage resellers, businesses, card inventory/batches, fulfillment, billing, payouts, global analytics.
- **Reseller (rep):** self-signup; buy wholesale cards, assign/activate cards to businesses, view own sales + commission ledger + payouts.
- **Business (client):** set review destination URL, customize landing page, read feedback inbox + star analytics, manage subscription.

Enforce isolation with Postgres RLS. Never rely on client-side checks alone.

---

## 4. Data model (minimum viable schema)

```
users        (id, email, role[admin|reseller|business], stripe_customer_id, created_at)
resellers    (id, user_id->users, display_name, commission_rate, payout_method, status)
businesses   (id, name, logo_url, brand_color, review_url, review_platform,
              owner_phone, owner_email, reseller_id->resellers,
              subscription_status[none|active|past_due|canceled],
              stripe_subscription_id, created_at)
cards        (id  // unguessable cardId in URL, e.g. 12-char base62,
              business_id->businesses  (nullable until assigned),
              status[unassigned|active|disabled], batch_id, activated_at)
taps         (id, card_id->cards, rating[1-5], redirected_to, user_agent, created_at)
feedback     (id, business_id->businesses, rating, customer_name, customer_phone,
              message, resolved[bool], created_at)
commissions  (id, reseller_id, business_id, stripe_invoice_id,
              type[card_sale|sub_month_1|sub_month_2], amount,
              status[pending|paid|reversed], created_at)
card_batches (id, quantity, printed[bool], notes, created_at)
```

`cardId` must be **random and unguessable** (e.g. 12-char nanoid), never sequential.

---

## 5. Key API endpoints

| Route | Purpose |
|---|---|
| `GET /t/:cardId` | Public. Resolve card, render branded rating page. Edge-cache per card where possible. |
| `POST /api/tap` | Public. Record rating; return redirect target (4-5) or feedback-form flag (1-3). |
| `POST /api/feedback` | Public. Store private feedback; fire Twilio SMS + Resend email to owner. |
| `POST /api/cards/assign` | Reseller/admin. Bind card to business, set status=active. |
| `POST /api/checkout/cards` | Reseller. Stripe Checkout for wholesale card orders. |
| `POST /api/checkout/subscription` | Business. Stripe Checkout for $15/mo subscription. |
| `POST /api/webhooks/stripe` | Stripe events -> activation + commission ledger. |
| `GET /api/business/feedback` | Business. Paginated feedback inbox + analytics. |

---

## 6. Payments & commission logic (Stripe webhooks)

All money automation is webhook-driven.

| Stripe event | Action |
|---|---|
| `checkout.session.completed` (subscription) | Set `subscription_status=active`. If card unassigned/inactive, **auto-activate now** (card goes live the moment payment clears). |
| `invoice.paid` | Count paid invoices on this subscription. 1st -> `commissions(sub_month_1, $15)` to reseller. 2nd -> `sub_month_2, $15`. 3rd+ -> no commission (100% company). |
| `charge.refunded` / `invoice.payment_failed` | If it matches a rep-credited invoice, set that commission `status=reversed` (clawback). |
| `customer.subscription.deleted` | Set `subscription_status=canceled`. |

> **Anchor commissions to successful paid invoices**, not calendar months or signup date. Handles retries, failed cards, and re-subscribes; pairs with refund clawback so reps are paid only on money actually kept. Make webhook handlers idempotent (dedupe on event id) and verify signatures.

**Rep comp summary:** card spread (~$35, set by reseller's retail price) + first 2 paid subscription months ($15 x 2). Month 3+ subscription is 100% company.

---

## 7. NFC card production

- **Chip:** NTAG213 (URL fits easily). ~$2/card low volume.
- **Encoding:** single NDEF URI record = `https://app.DOMAIN.com/t/{cardId}`. NFC Tools app writes in ~5s; lock tag read-only after writing.
- **At volume:** pre-generate a batch of `unassigned` cardIds, export CSV of URLs, write in-house or hand CSV to an NFC print vendor for pre-encoding + custom print.
- Assignment happens later in software, so generic stock can be produced ahead of demand.

---

## 8. Security checklist

- Unguessable `cardId` (nanoid 12+); rate-limit `/api/tap` and `/api/feedback`.
- Postgres RLS on every tenant table; server-side authorization on all mutations.
- Verify Stripe webhook signatures; idempotent handlers (dedupe on event id).
- Minimize customer PII (name/phone optional on feedback); privacy notice on public pages.
- Bot/abuse protection + tap caps per card per window.
- Least-privilege API keys per integration; secrets server-only.

---

## 9. Build phases

- **Phase 1 - Prove the mechanic:** tap resolver, branded rating page, 4-5 vs 1-3 split, private feedback form, Twilio SMS + Resend email. One hardcoded demo business. Goal: a card you can tap live in front of an owner.
- **Phase 2 - Make it a product:** auth + roles, business dashboard (review URL, page customization, feedback inbox, analytics), card assignment/activation.
- **Phase 3 - The business engine:** public marketing site + reseller signup, Stripe card checkout + $15/mo subscriptions, commission ledger + reseller dashboard, super-admin panel + fulfillment, batch/inventory tooling.

---

## 10. Environment

```
# .env (server-only; never expose service keys to client)
NEXT_PUBLIC_APP_URL=https://app.DOMAIN.com
SUPABASE_URL= / SUPABASE_ANON_KEY= / SUPABASE_SERVICE_ROLE_KEY=
STRIPE_SECRET_KEY= / STRIPE_WEBHOOK_SECRET=
STRIPE_PRICE_SUBSCRIPTION=price_...   # $15/mo recurring
TWILIO_ACCOUNT_SID= / TWILIO_AUTH_TOKEN= / TWILIO_FROM_NUMBER=
RESEND_API_KEY= / ALERT_FROM_EMAIL=
```

---

## 11. Extensibility (design for the endgame)

This platform is a lead-gen engine for higher-ticket website + AI services. Build the business dashboard with room for upsell modules and clean contact capture. Keep `businesses` records rich (industry, contact, engagement) for later segmentation and cross-sell.
