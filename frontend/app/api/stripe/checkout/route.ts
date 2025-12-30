/**
 * Stripe Checkout Session API - ModelFinOps
 *
 * Creates checkout sessions for subscription purchases.
 *
 * POST /api/stripe/checkout
 * {
 *   planId: 'starter' | 'pro' | 'enterprise',
 *   email: string,
 *   interval?: 'month' | 'year',
 *   successUrl?: string,
 *   cancelUrl?: string
 * }
 */

import { NextRequest, NextResponse } from 'next/server';
import { stripe } from '@/lib/stripe/client';
import { PLANS, STRIPE_PRICES, type PlanId } from '@/lib/stripe/plans';

type CheckoutRequest = {
  planId: string;
  email: string;
  interval?: 'month' | 'year';
  successUrl?: string;
  cancelUrl?: string;
  userId?: string;
  metadata?: Record<string, string>;
};

export async function POST(request: NextRequest) {
  try {
    const body = (await request.json()) as CheckoutRequest;

    const {
      planId,
      email,
      interval = 'month',
      successUrl,
      cancelUrl,
      userId,
      metadata = {},
    } = body;

    // Validate required fields
    if (!planId || !email) {
      return NextResponse.json(
        { error: 'planId and email are required' },
        { status: 400 }
      );
    }

    // Validate plan
    const plan = PLANS[planId as PlanId];
    if (!plan || planId === 'free') {
      return NextResponse.json(
        { error: 'Invalid plan. Choose starter, pro, or enterprise' },
        { status: 400 }
      );
    }

    // Get price ID
    const priceKey = `${planId}_${interval === 'year' ? 'annual' : 'monthly'}` as keyof typeof STRIPE_PRICES;
    const priceId = STRIPE_PRICES[priceKey];

    if (!priceId) {
      return NextResponse.json(
        { error: 'Price not configured for this plan' },
        { status: 500 }
      );
    }

    // Build URLs
    const origin = request.headers.get('origin') || 'https://modelfinops.com';
    const success = successUrl || `${origin}/dashboard?checkout=success`;
    const cancel = cancelUrl || `${origin}/pricing?checkout=cancelled`;

    // Find or create customer
    const customers = await stripe.customers.list({ email, limit: 1 });
    let customer = customers.data[0];

    if (!customer) {
      customer = await stripe.customers.create({
        email,
        metadata: {
          source: 'modelfinops-checkout',
          ...(userId ? { user_id: userId } : {}),
        },
      });
    }

    // Create checkout session
    const session = await stripe.checkout.sessions.create({
      customer: customer.id,
      mode: 'subscription',
      line_items: [{ price: priceId, quantity: 1 }],
      subscription_data: {
        trial_period_days: 14,
        metadata: {
          plan_id: planId,
          interval,
          api_calls_monthly: plan.apiCallsMonthly.toString(),
        },
      },
      payment_method_collection: 'if_required',
      success_url: `${success}&session_id={CHECKOUT_SESSION_ID}`,
      cancel_url: cancel,
      allow_promotion_codes: true,
      billing_address_collection: 'auto',
      metadata: {
        plan_id: planId,
        interval,
        source: 'modelfinops-checkout',
        ...(userId ? { user_id: userId } : {}),
        ...metadata,
      },
    });

    return NextResponse.json({
      sessionId: session.id,
      url: session.url,
    });
  } catch (error) {
    console.error('Stripe checkout error:', error);

    if (error instanceof Error) {
      return NextResponse.json({ error: error.message }, { status: 500 });
    }

    return NextResponse.json(
      { error: 'Failed to create checkout session' },
      { status: 500 }
    );
  }
}
