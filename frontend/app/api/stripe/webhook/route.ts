/**
 * Stripe Webhook Handler - ModelFinOps
 *
 * Handles subscription lifecycle events from Stripe.
 *
 * Events handled:
 * - checkout.session.completed: Initial subscription creation
 * - customer.subscription.created/updated: Sync subscription changes
 * - customer.subscription.deleted: Downgrade to free tier
 * - invoice.paid: Monthly renewal, reset API usage
 * - invoice.payment_failed: Mark as past_due
 */

import { NextRequest, NextResponse } from 'next/server';
import { createClient } from '@supabase/supabase-js';
import { stripe } from '@/lib/stripe/client';
import { getPlan, type PlanId } from '@/lib/stripe/plans';
import { sendPaymentFailedEmail } from '@/lib/email';
import type Stripe from 'stripe';

// Server-side Supabase client with service role for webhook operations
const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.SUPABASE_SERVICE_ROLE_KEY!
);

export async function POST(request: NextRequest) {
  const body = await request.text();
  const signature = request.headers.get('stripe-signature');

  if (!signature) {
    return NextResponse.json(
      { error: 'Missing stripe-signature header' },
      { status: 400 }
    );
  }

  const webhookSecret = process.env.STRIPE_WEBHOOK_SECRET;
  if (!webhookSecret) {
    console.error('STRIPE_WEBHOOK_SECRET is not set');
    return NextResponse.json(
      { error: 'Webhook secret not configured' },
      { status: 500 }
    );
  }

  let event: Stripe.Event;

  try {
    event = stripe.webhooks.constructEvent(body, signature, webhookSecret);
  } catch (err) {
    console.error('Webhook signature verification failed:', err);
    return NextResponse.json(
      { error: 'Invalid signature' },
      { status: 400 }
    );
  }

  console.log(`Processing webhook event: ${event.type} (${event.id})`);

  try {
    switch (event.type) {
      case 'checkout.session.completed':
        await handleCheckoutComplete(event.data.object as Stripe.Checkout.Session);
        break;

      case 'customer.subscription.created':
      case 'customer.subscription.updated':
        await handleSubscriptionChange(event.data.object as Stripe.Subscription);
        break;

      case 'customer.subscription.deleted':
        await handleSubscriptionDeleted(event.data.object as Stripe.Subscription);
        break;

      case 'invoice.paid':
        await handleInvoicePaid(event.data.object as Stripe.Invoice);
        break;

      case 'invoice.payment_failed':
        await handlePaymentFailed(event.data.object as Stripe.Invoice);
        break;

      default:
        console.log(`Unhandled event type: ${event.type}`);
    }

    return NextResponse.json({ received: true });
  } catch (error) {
    console.error(`Error processing webhook ${event.type}:`, error);
    return NextResponse.json(
      { error: 'Webhook handler failed' },
      { status: 500 }
    );
  }
}

/**
 * Handle successful checkout session
 */
async function handleCheckoutComplete(session: Stripe.Checkout.Session) {
  const customerId = session.customer as string;
  const subscriptionId = session.subscription as string;
  const planId = (session.metadata?.plan_id || 'starter') as PlanId;
  const userId = session.metadata?.user_id;

  console.log(`Checkout complete for customer ${customerId}, plan ${planId}`);

  const plan = getPlan(planId);

  // Upsert subscription record in database
  const { error } = await supabase.from('subscriptions').upsert({
    user_id: userId,
    stripe_customer_id: customerId,
    stripe_subscription_id: subscriptionId,
    plan_id: planId,
    api_calls_limit: plan.apiCallsMonthly,
    api_calls_used: 0,
    status: 'active',
  }, { onConflict: 'stripe_subscription_id' });

  if (error) {
    console.error('Failed to create subscription:', error);
    throw error;
  }

  console.log(`Subscription created: ${subscriptionId} (${plan.name})`);
}

/**
 * Handle subscription changes (upgrade/downgrade)
 */
async function handleSubscriptionChange(subscription: Stripe.Subscription) {
  const customerId = subscription.customer as string;
  const subscriptionId = subscription.id;
  const status = subscription.status;

  // Get plan from metadata
  let planId = subscription.metadata?.plan_id as PlanId;
  if (!planId) {
    const item = subscription.items.data[0];
    planId = (item?.price?.metadata?.plan_id as PlanId) || 'starter';
  }

  const plan = getPlan(planId);

  console.log(`Subscription ${subscriptionId} changed: ${status}`);

  // Update subscription in database
  const { error } = await supabase.from('subscriptions').update({
    plan_id: planId,
    api_calls_limit: plan.apiCallsMonthly,
    status: status,
  }).eq('stripe_subscription_id', subscriptionId);

  if (error) {
    console.error('Failed to update subscription:', error);
    throw error;
  }

  console.log(`Subscription synced: ${subscriptionId}`);
}

/**
 * Handle subscription cancellation
 */
async function handleSubscriptionDeleted(subscription: Stripe.Subscription) {
  const subscriptionId = subscription.id;
  const freePlan = getPlan('free');

  console.log(`Subscription ${subscriptionId} cancelled`);

  // Downgrade user to free tier
  const { error } = await supabase.from('subscriptions').update({
    plan_id: 'free',
    api_calls_limit: freePlan.apiCallsMonthly,
    status: 'cancelled',
  }).eq('stripe_subscription_id', subscriptionId);

  if (error) {
    console.error('Failed to cancel subscription:', error);
    throw error;
  }

  console.log(`User downgraded to free tier`);
}

/**
 * Handle successful invoice payment (monthly renewal)
 * Reset API usage counters for new billing period
 */
async function handleInvoicePaid(invoice: Stripe.Invoice) {
  const subscriptionId = (invoice as Stripe.Invoice & { subscription?: string | Stripe.Subscription | null }).subscription as string | null;

  if (!subscriptionId) {
    return; // One-time payment
  }

  console.log(`Invoice paid for subscription ${subscriptionId}`);

  // Reset API usage counters for new billing period
  const { error } = await supabase.from('subscriptions').update({
    api_calls_used: 0,
    status: 'active',
  }).eq('stripe_subscription_id', subscriptionId);

  if (error) {
    console.error('Failed to reset usage counters:', error);
    throw error;
  }

  console.log(`API usage reset for new billing period`);
}

/**
 * Handle failed invoice payment
 */
async function handlePaymentFailed(invoice: Stripe.Invoice) {
  const subscriptionId = (invoice as Stripe.Invoice & { subscription?: string | Stripe.Subscription | null }).subscription as string | null;
  const customerId = invoice.customer as string;

  if (!subscriptionId) {
    return;
  }

  console.log(`Payment failed for subscription ${subscriptionId}`);

  // Mark subscription as past_due
  const { error } = await supabase.from('subscriptions').update({
    status: 'past_due',
  }).eq('stripe_subscription_id', subscriptionId);

  if (error) {
    console.error('Failed to update subscription status:', error);
    throw error;
  }

  // Send email notification to customer
  try {
    const customer = await stripe.customers.retrieve(customerId);
    if (customer && !customer.deleted && customer.email) {
      await sendPaymentFailedEmail(customer.email, customer.name ?? undefined);
      console.log(`Payment failure email sent to ${customer.email}`);
    }
  } catch (emailError) {
    // Don't fail the webhook if email fails
    console.error('Failed to send payment failure email:', emailError);
  }

  console.log(`Subscription marked as past_due`);
}
