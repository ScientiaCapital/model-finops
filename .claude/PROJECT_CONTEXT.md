# model-finops

**Branch**: main | **Updated**: 2025-12-30

## Status
Stripe subscription integration complete with full API routes, products, prices, and webhooks configured via CLI. Test mode ready - switch to live keys for production.

## Today's Focus
1. [ ] Add pricing page UI component
2. [ ] Connect checkout flow to frontend
3. [ ] Test subscription flow end-to-end

## Done (This Session)
- Added Stripe lib (`frontend/lib/stripe/`) with lazy-init client, plans config
- Created API routes: checkout, portal, webhook handlers
- Created Stripe products via CLI: Starter ($49), Pro ($149), Enterprise ($399)
- Created monthly + annual prices for all tiers
- Configured webhook endpoint with subscription lifecycle events
- Updated .env.local with all Stripe credentials (test mode)

## Blockers
None

## Tech Stack
Next.js 15 + FastAPI backend + Supabase + Stripe (test mode)

## Stripe Products (Test Mode)
| Tier | Monthly Price ID | Annual Price ID |
|------|------------------|-----------------|
| Starter ($49) | price_1Sk4QECI542nEcDoQeNLga18 | price_1Sk4QFCI542nEcDoJULQA08z |
| Pro ($149) | price_1Sk4QFCI542nEcDoB1MX8Kcf | price_1Sk4QGCI542nEcDoKUz9MNqZ |
| Enterprise ($399) | price_1Sk4QGCI542nEcDoBGFo4tSp | price_1Sk4QHCI542nEcDownZbTP8c |

## Webhook
- URL: `https://modelfinops.com/api/stripe/webhook`
- Secret: `whsec_Og52T5HiZaQ7etOwxwxlLYHSnGtZCONq`
