/**
 * Email Service - ModelFinOps
 *
 * Handles transactional emails using Resend.
 * Uses lazy initialization to avoid build-time errors.
 */

import { Resend } from 'resend'

let resendInstance: Resend | null = null

function getResend(): Resend {
  if (!resendInstance) {
    const apiKey = process.env.RESEND_API_KEY
    if (!apiKey) {
      throw new Error('RESEND_API_KEY environment variable is not set')
    }
    resendInstance = new Resend(apiKey)
  }
  return resendInstance
}

const FROM_EMAIL = process.env.EMAIL_FROM || 'Model FinOps <noreply@modelfinops.com>'
const APP_URL = process.env.NEXT_PUBLIC_APP_URL || 'https://modelfinops.com'

/**
 * Send payment failure notification email
 */
export async function sendPaymentFailedEmail(email: string, customerName?: string): Promise<void> {
  const greeting = customerName ? `Hi ${customerName},` : 'Hi,'

  await getResend().emails.send({
    from: FROM_EMAIL,
    to: email,
    subject: 'Payment Failed - Action Required',
    html: `
      <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
        <h2 style="color: #1a1a1a;">Payment Failed</h2>
        <p>${greeting}</p>
        <p>We were unable to process your payment for your Model FinOps subscription.</p>
        <p>To avoid any interruption to your service, please update your payment method as soon as possible.</p>
        <p style="margin: 30px 0;">
          <a href="${APP_URL}/billing"
             style="background-color: #2563eb; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; display: inline-block;">
            Update Payment Method
          </a>
        </p>
        <p>If you have any questions, please reply to this email and we'll be happy to help.</p>
        <p style="color: #666; margin-top: 30px;">
          — The Model FinOps Team
        </p>
      </div>
    `,
  })
}

/**
 * Send subscription cancelled confirmation email
 */
export async function sendSubscriptionCancelledEmail(
  email: string,
  customerName?: string
): Promise<void> {
  const greeting = customerName ? `Hi ${customerName},` : 'Hi,'

  await getResend().emails.send({
    from: FROM_EMAIL,
    to: email,
    subject: 'Subscription Cancelled',
    html: `
      <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
        <h2 style="color: #1a1a1a;">Subscription Cancelled</h2>
        <p>${greeting}</p>
        <p>Your Model FinOps subscription has been cancelled. You've been downgraded to our free tier.</p>
        <p>You can still access basic features with the following limits:</p>
        <ul>
          <li>100 API calls per month</li>
          <li>Basic routing optimization</li>
        </ul>
        <p>If you'd like to resubscribe at any time, you can do so from your billing page.</p>
        <p style="margin: 30px 0;">
          <a href="${APP_URL}/billing"
             style="background-color: #2563eb; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; display: inline-block;">
            View Plans
          </a>
        </p>
        <p style="color: #666; margin-top: 30px;">
          — The Model FinOps Team
        </p>
      </div>
    `,
  })
}

/**
 * Send welcome email for new subscribers
 */
export async function sendWelcomeEmail(
  email: string,
  customerName?: string,
  planName?: string
): Promise<void> {
  const greeting = customerName ? `Hi ${customerName},` : 'Hi,'
  const plan = planName || 'your new plan'

  await getResend().emails.send({
    from: FROM_EMAIL,
    to: email,
    subject: 'Welcome to Model FinOps!',
    html: `
      <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
        <h2 style="color: #1a1a1a;">Welcome to Model FinOps! 🎉</h2>
        <p>${greeting}</p>
        <p>Thanks for subscribing to ${plan}! You now have access to intelligent LLM routing that can reduce your AI costs by up to 60%.</p>
        <p><strong>Here's how to get started:</strong></p>
        <ol>
          <li>Generate your API key from the dashboard</li>
          <li>Configure your LLM providers</li>
          <li>Start routing requests through our optimization engine</li>
        </ol>
        <p style="margin: 30px 0;">
          <a href="${APP_URL}/dashboard"
             style="background-color: #2563eb; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; display: inline-block;">
            Go to Dashboard
          </a>
        </p>
        <p>If you have any questions, just reply to this email!</p>
        <p style="color: #666; margin-top: 30px;">
          — The Model FinOps Team
        </p>
      </div>
    `,
  })
}
