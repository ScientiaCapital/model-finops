import Link from 'next/link'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Zap, DollarSign, Layers, Brain, ArrowRight } from 'lucide-react'

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-background">
      {/* Hero Section */}
      <header className="border-b">
        <div className="container mx-auto px-4 py-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Zap className="h-8 w-8 text-primary" />
            <span className="text-xl font-bold">ModelFinOps</span>
          </div>
          <div className="flex items-center gap-4">
            <Button variant="ghost" asChild>
              <Link href="/login">Sign in</Link>
            </Button>
            <Button asChild>
              <Link href="/signup">Get Started</Link>
            </Button>
          </div>
        </div>
      </header>

      <main>
        {/* Hero */}
        <section className="py-20 md:py-32">
          <div className="container mx-auto px-4 text-center">
            <h1 className="text-4xl md:text-6xl font-bold tracking-tight mb-6">
              Cut Your AI Costs by <span className="text-primary">60%+</span>
            </h1>
            <p className="text-xl text-muted-foreground max-w-2xl mx-auto mb-8">
              Intelligent routing and semantic caching for your LLM workloads. Same quality,
              dramatically lower costs.
            </p>
            <div className="flex flex-col sm:flex-row gap-4 justify-center">
              <Button size="lg" asChild>
                <Link href="/signup">
                  Start Free
                  <ArrowRight className="ml-2 h-4 w-4" />
                </Link>
              </Button>
              <Button size="lg" variant="outline" asChild>
                <Link href="/login">View Demo</Link>
              </Button>
            </div>
            <p className="mt-4 text-sm text-muted-foreground">
              No credit card required. 10,000 free tokens.
            </p>
          </div>
        </section>

        {/* Features */}
        <section className="py-20 bg-muted/50">
          <div className="container mx-auto px-4">
            <h2 className="text-3xl font-bold text-center mb-12">Why ModelFinOps?</h2>
            <div className="grid md:grid-cols-3 gap-8 max-w-5xl mx-auto">
              {/* Feature 1: Cost Savings */}
              <Card>
                <CardHeader>
                  <div className="h-12 w-12 rounded-lg bg-green-500/10 flex items-center justify-center mb-4">
                    <DollarSign className="h-6 w-6 text-green-500" />
                  </div>
                  <CardTitle>60%+ Cost Reduction</CardTitle>
                  <CardDescription>
                    Our intelligent routing automatically selects the most cost-effective model for
                    each prompt, without sacrificing quality.
                  </CardDescription>
                </CardHeader>
              </Card>

              {/* Feature 2: Multi-Provider */}
              <Card>
                <CardHeader>
                  <div className="h-12 w-12 rounded-lg bg-blue-500/10 flex items-center justify-center mb-4">
                    <Layers className="h-6 w-6 text-blue-500" />
                  </div>
                  <CardTitle>Multi-Provider Support</CardTitle>
                  <CardDescription>
                    Access Claude, Gemini, DeepSeek, Groq, and more through a single API. Automatic
                    fallback ensures 99.9% uptime.
                  </CardDescription>
                </CardHeader>
              </Card>

              {/* Feature 3: Semantic Caching */}
              <Card>
                <CardHeader>
                  <div className="h-12 w-12 rounded-lg bg-purple-500/10 flex items-center justify-center mb-4">
                    <Brain className="h-6 w-6 text-purple-500" />
                  </div>
                  <CardTitle>Semantic Caching</CardTitle>
                  <CardDescription>
                    Similar prompts hit the cache. &quot;What is Python?&quot; and &quot;Explain
                    Python&quot; return instant cached responses.
                  </CardDescription>
                </CardHeader>
              </Card>
            </div>
          </div>
        </section>

        {/* CTA */}
        <section className="py-20">
          <div className="container mx-auto px-4 text-center">
            <h2 className="text-3xl font-bold mb-4">Ready to reduce your AI costs?</h2>
            <p className="text-muted-foreground mb-8">
              Join teams saving thousands on their AI infrastructure.
            </p>
            <Button size="lg" asChild>
              <Link href="/signup">
                Get Started Free
                <ArrowRight className="ml-2 h-4 w-4" />
              </Link>
            </Button>
          </div>
        </section>
      </main>

      {/* Footer */}
      <footer className="border-t py-8">
        <div className="container mx-auto px-4 text-center text-sm text-muted-foreground">
          <p>&copy; {new Date().getFullYear()} ModelFinOps. All rights reserved.</p>
        </div>
      </footer>
    </div>
  )
}
