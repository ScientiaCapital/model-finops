import { SubscriptionTracker } from '@/components/SubscriptionTracker'

export default function SubscriptionsPage() {
  return (
    <div className="container mx-auto py-8 px-4">
      <div className="mb-8">
        <h1 className="text-4xl font-bold mb-2">Subscription Tracker</h1>
        <p className="text-muted-foreground text-lg">
          Track your AI services and never miss a billing date
        </p>
      </div>
      <SubscriptionTracker />
    </div>
  )
}
