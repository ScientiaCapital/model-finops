# model-finops

**Branch**: main | **Updated**: 2026-01-12

## Status
Pricing page complete and pushed to production. 3-tier subscription UI ($49/$149/$399) with Stripe checkout integration ready. Next: configure Stripe price IDs in .env.local and test checkout flow end-to-end.

## Today's Focus
1. [ ] Add real Stripe price IDs to .env.local
2. [ ] Test checkout flow with Stripe test cards
3. [ ] Verify Vercel deployment working

## Done (This Session)
- Created pricing page UI (`frontend/app/pricing/page.tsx`) with 3 tiers
- Added billing interval toggle (monthly/annual with 20% discount)
- Wired checkout buttons to Stripe via `createCheckoutSession`
- Fixed lazy initialization for Resend email client (build-time fix)
- Fixed lazy initialization for Supabase in webhook handler
- Updated `lib/stripe/plans.ts` with correct API limits (10K/100K/unlimited)
- Added Stripe price ID env vars to `.env.example`
- Added Pricing link to Navbar
- Passed security audit (0 secrets, 0 CVEs)
- Pushed commit `494609c` to origin/main

## Blockers
None

## Tech Stack
Next.js 16 + FastAPI backend + Supabase + Stripe (test mode)

## Stripe Products (Test Mode)
| Tier | Monthly Price ID | Annual Price ID |
|------|------------------|-----------------|
| Starter ($49) | price_1Sk4QECI542nEcDoQeNLga18 | price_1Sk4QFCI542nEcDoJULQA08z |
| Pro ($149) | price_1Sk4QFCI542nEcDoB1MX8Kcf | price_1Sk4QGCI542nEcDoKUz9MNqZ |
| Enterprise ($399) | price_1Sk4QGCI542nEcDoBGFo4tSp | price_1Sk4QHCI542nEcDownZbTP8c |

## Webhook
- URL: `https://modelfinops.com/api/stripe/webhook`
- Secret: `whsec_Og52T5HiZaQ7etOwxwxlLYHSnGtZCONq`
