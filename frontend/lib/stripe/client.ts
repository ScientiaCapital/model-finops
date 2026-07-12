/**
 * Stripe Server-Side Client - ModelFinOps
 *
 * Lazy initialization pattern to avoid build-time errors.
 * Only initializes Stripe when first used in runtime.
 */

import Stripe from 'stripe'

let stripeInstance: Stripe | null = null

function getStripeInstance(): Stripe {
  if (!stripeInstance) {
    const secretKey = process.env.STRIPE_SECRET_KEY

    if (!secretKey) {
      throw new Error('STRIPE_SECRET_KEY is not set in environment variables')
    }

    if (!secretKey.startsWith('sk_')) {
      throw new Error('STRIPE_SECRET_KEY must start with "sk_"')
    }

    stripeInstance = new Stripe(secretKey, {
      apiVersion: '2025-12-15.clover',
      typescript: true,
    })
  }

  return stripeInstance
}

// Proxy pattern for lazy initialization
export const stripe = new Proxy({} as Stripe, {
  get(_, prop) {
    return getStripeInstance()[prop as keyof Stripe]
  },
})

export type { Stripe }
