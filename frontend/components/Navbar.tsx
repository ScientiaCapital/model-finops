'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { cn } from '@/lib/utils'
import { ThemeToggle } from '@/components/ThemeToggle'
import { UserMenu } from '@/components/UserMenu'
import {
  LayoutDashboard,
  Key,
  Settings,
  Activity,
  Zap,
  Building2,
  CreditCard,
  Receipt,
} from 'lucide-react'

const navigation = [
  { name: 'Dashboard', href: '/dashboard', icon: LayoutDashboard },
  { name: 'Subscriptions', href: '/subscriptions', icon: CreditCard },
  { name: 'Pricing', href: '/pricing', icon: Zap },
  { name: 'Billing', href: '/billing', icon: Receipt },
  { name: 'API Keys', href: '/api-keys', icon: Key },
  { name: 'Enterprise', href: '/enterprise', icon: Building2 },
  { name: 'Settings', href: '/settings', icon: Settings },
]

export function Navbar() {
  const pathname = usePathname()

  return (
    <nav className="border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="flex h-16 justify-between">
          <div className="flex">
            {/* Logo */}
            <div className="flex flex-shrink-0 items-center">
              <Zap className="h-8 w-8 text-primary" />
              <span className="ml-2 text-xl font-bold">ModelFinOps</span>
            </div>

            {/* Navigation Links */}
            <div className="hidden sm:ml-10 sm:flex sm:space-x-8">
              {navigation.map(item => {
                const isActive = pathname === item.href
                return (
                  <Link
                    key={item.name}
                    href={item.href}
                    className={cn(
                      'inline-flex items-center border-b-2 px-1 pt-1 text-sm font-medium',
                      isActive
                        ? 'border-primary text-foreground'
                        : 'border-transparent text-muted-foreground hover:border-border hover:text-foreground'
                    )}
                  >
                    <item.icon className="mr-2 h-4 w-4" />
                    {item.name}
                  </Link>
                )
              })}
            </div>
          </div>

          {/* Right side: Status + Theme Toggle + User Menu */}
          <div className="flex items-center gap-4">
            <div className="hidden sm:flex items-center text-sm text-muted-foreground">
              <Activity className="mr-1 h-4 w-4 text-green-500" />
              <span>Connected</span>
            </div>
            <ThemeToggle />
            <UserMenu />
          </div>
        </div>
      </div>
    </nav>
  )
}
