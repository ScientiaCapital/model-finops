/**
 * Stripe Customer Portal API - ModelFinOps
 *
 * Creates a billing portal session for subscription management.
 * Allows customers to update payment methods, cancel, view invoices.
 *
 * POST /api/stripe/portal
 * {
 *   customerId: string,
 *   returnUrl?: string
 * }
 */

import { NextRequest, NextResponse } from 'next/server';
import { stripe } from '@/lib/stripe/client';

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();

    const { customerId, returnUrl } = body as {
      customerId: string;
      returnUrl?: string;
    };

    if (!customerId) {
      return NextResponse.json(
        { error: 'customerId is required' },
        { status: 400 }
      );
    }

    // Verify customer exists
    try {
      await stripe.customers.retrieve(customerId);
    } catch {
      return NextResponse.json(
        { error: 'Customer not found' },
        { status: 404 }
      );
    }

    // Build return URL
    const origin = request.headers.get('origin') || 'https://modelfinops.com';
    const returnPath = returnUrl || `${origin}/dashboard`;

    // Create portal session
    const session = await stripe.billingPortal.sessions.create({
      customer: customerId,
      return_url: returnPath,
    });

    return NextResponse.json({
      url: session.url,
    });
  } catch (error) {
    console.error('Stripe portal error:', error);

    if (error instanceof Error) {
      return NextResponse.json(
        { error: error.message },
        { status: 500 }
      );
    }

    return NextResponse.json(
      { error: 'Failed to create portal session' },
      { status: 500 }
    );
  }
}
