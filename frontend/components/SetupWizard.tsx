'use client'

import { useState, useEffect } from 'react'
import { Card, CardContent, CardHeader, CardTitle, CardDescription, CardFooter } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Checkbox } from '@/components/ui/checkbox'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { cn } from '@/lib/utils'
import {
  CheckCircle2,
  XCircle,
  ExternalLink,
  ArrowRight,
  ArrowLeft,
  Loader2,
  Cpu,
  Mic,
  Database,
  Activity,
  CreditCard,
  Copy,
  Check,
  AlertCircle,
  Video,
} from 'lucide-react'
import {
  getSetupLinks,
  getProviderCategories,
  validateApiKey,
  type SetupLink,
  type ProviderCategories,
} from '@/lib/api'

interface SetupWizardProps {
  className?: string
  onComplete?: (selectedProviders: string[]) => void
}

type WizardStep = 'select' | 'configure' | 'complete'

const categoryIcons: Record<string, React.ReactNode> = {
  'LLM Providers': <Cpu className="h-5 w-5" />,
  'Voice AI (TTS)': <Mic className="h-5 w-5" />,
  'Voice AI (STT)': <Mic className="h-5 w-5" />,
  Infrastructure: <Database className="h-5 w-5" />,
  'AI Media': <Video className="h-5 w-5" />,
  Observability: <Activity className="h-5 w-5" />,
  Billing: <CreditCard className="h-5 w-5" />,
}

const categoryDescriptions: Record<string, string> = {
  'LLM Providers': 'AI language models for text generation',
  'Voice AI (TTS)': 'Text-to-speech synthesis',
  'Voice AI (STT)': 'Speech-to-text transcription',
  Infrastructure: 'Database and deployment services',
  'AI Media': 'AI video and image generation',
  Observability: 'Tracing and monitoring',
  Billing: 'Payment processing',
}

interface ProviderCardProps {
  link: SetupLink
  selected: boolean
  onToggle: () => void
}

function ProviderSelectCard({ link, selected, onToggle }: ProviderCardProps) {
  return (
    <div
      onClick={onToggle}
      className={cn(
        'flex items-center gap-3 p-4 rounded-lg border cursor-pointer transition-all',
        selected ? 'border-primary bg-primary/5' : 'border-border hover:border-muted-foreground/50'
      )}
    >
      <Checkbox checked={selected} onCheckedChange={() => onToggle()} className="pointer-events-none" />
      <div className="flex-1">
        <p className="font-medium">{link.display_name}</p>
        <p className="text-xs text-muted-foreground">{link.instructions}</p>
      </div>
    </div>
  )
}

interface ProviderConfigCardProps {
  link: SetupLink
  onValidated: (valid: boolean) => void
}

function ProviderConfigCard({ link, onValidated }: ProviderConfigCardProps) {
  const [apiKey, setApiKey] = useState('')
  const [validating, setValidating] = useState(false)
  const [status, setStatus] = useState<'idle' | 'valid' | 'invalid'>('idle')
  const [message, setMessage] = useState('')
  const [copied, setCopied] = useState(false)

  const handleValidate = async () => {
    if (!apiKey.trim()) return

    setValidating(true)
    try {
      const result = await validateApiKey({
        provider: link.provider,
        api_key: apiKey,
      })
      setStatus(result.valid ? 'valid' : 'invalid')
      setMessage(result.message)
      onValidated(result.valid)
    } catch {
      setStatus('invalid')
      setMessage('Validation failed')
      onValidated(false)
    } finally {
      setValidating(false)
    }
  }

  const copyEnvVar = () => {
    navigator.clipboard.writeText(link.env_vars[0])
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="space-y-4 p-4 rounded-lg border">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          {status === 'valid' && <CheckCircle2 className="h-5 w-5 text-green-500" />}
          {status === 'invalid' && <XCircle className="h-5 w-5 text-red-500" />}
          {status === 'idle' && <AlertCircle className="h-5 w-5 text-yellow-500" />}
          <span className="font-medium">{link.display_name}</span>
        </div>
        <Button variant="outline" size="sm" asChild>
          <a href={link.setup_url} target="_blank" rel="noopener noreferrer">
            Get API Key <ExternalLink className="h-3 w-3 ml-1" />
          </a>
        </Button>
      </div>

      <div className="space-y-2">
        <div className="flex items-center gap-2">
          <Label htmlFor={`key-${link.provider}`} className="text-sm">
            {link.env_vars[0]}
          </Label>
          <Button variant="ghost" size="icon" className="h-6 w-6" onClick={copyEnvVar}>
            {copied ? <Check className="h-3 w-3" /> : <Copy className="h-3 w-3" />}
          </Button>
        </div>
        <div className="flex gap-2">
          <Input
            id={`key-${link.provider}`}
            type="password"
            placeholder="sk-..."
            value={apiKey}
            onChange={(e) => {
              setApiKey(e.target.value)
              setStatus('idle')
            }}
            className={cn(
              status === 'valid' && 'border-green-500',
              status === 'invalid' && 'border-red-500'
            )}
          />
          <Button onClick={handleValidate} disabled={!apiKey.trim() || validating}>
            {validating ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Validate'}
          </Button>
        </div>
        {message && (
          <p className={cn('text-xs', status === 'valid' ? 'text-green-500' : 'text-red-500')}>
            {message}
          </p>
        )}
      </div>

      <p className="text-xs text-muted-foreground">{link.instructions}</p>
    </div>
  )
}

export function SetupWizard({ className, onComplete }: SetupWizardProps) {
  const [step, setStep] = useState<WizardStep>('select')
  const [categories, setCategories] = useState<ProviderCategories | null>(null)
  const [links, setLinks] = useState<SetupLink[]>([])
  const [selectedProviders, setSelectedProviders] = useState<Set<string>>(new Set())
  const [validatedProviders, setValidatedProviders] = useState<Set<string>>(new Set())
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [categoriesData, linksData] = await Promise.all([
          getProviderCategories(),
          getSetupLinks(),
        ])
        setCategories(categoriesData)
        setLinks(linksData)
      } catch (err) {
        console.error('Failed to fetch setup data:', err)
      } finally {
        setLoading(false)
      }
    }
    fetchData()
  }, [])

  const toggleProvider = (provider: string) => {
    setSelectedProviders((prev) => {
      const next = new Set(prev)
      if (next.has(provider)) {
        next.delete(provider)
      } else {
        next.add(provider)
      }
      return next
    })
  }

  const handleProviderValidated = (provider: string, valid: boolean) => {
    setValidatedProviders((prev) => {
      const next = new Set(prev)
      if (valid) {
        next.add(provider)
      } else {
        next.delete(provider)
      }
      return next
    })
  }

  const selectedLinks = links.filter((l) => selectedProviders.has(l.provider))
  const progress =
    selectedProviders.size > 0 ? (validatedProviders.size / selectedProviders.size) * 100 : 0

  if (loading) {
    return (
      <Card className={className}>
        <CardContent className="flex justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </CardContent>
      </Card>
    )
  }

  if (!categories) {
    return (
      <Card className={className}>
        <CardContent className="py-8 text-center text-muted-foreground">
          Failed to load setup wizard
        </CardContent>
      </Card>
    )
  }

  return (
    <Card className={className}>
      <CardHeader>
        <CardTitle>
          {step === 'select' && 'Which services do you use?'}
          {step === 'configure' && 'Connect your services'}
          {step === 'complete' && 'Setup Complete!'}
        </CardTitle>
        <CardDescription>
          {step === 'select' && 'Select the AI services you want to track costs for'}
          {step === 'configure' && 'Add your API keys to enable cost tracking'}
          {step === 'complete' && 'Your services are now connected'}
        </CardDescription>
      </CardHeader>

      <CardContent>
        {step === 'select' && (
          <Tabs defaultValue={categories.categories[0]} className="space-y-4">
            <TabsList className="flex flex-wrap h-auto gap-1">
              {categories.categories.map((category) => (
                <TabsTrigger key={category} value={category} className="gap-2">
                  {categoryIcons[category]}
                  <span className="hidden sm:inline">{category}</span>
                </TabsTrigger>
              ))}
            </TabsList>

            {categories.categories.map((category) => (
              <TabsContent key={category} value={category} className="space-y-3">
                <p className="text-sm text-muted-foreground mb-4">
                  {categoryDescriptions[category]}
                </p>
                {links
                  .filter((l) => l.category === category)
                  .map((link) => (
                    <ProviderSelectCard
                      key={link.provider}
                      link={link}
                      selected={selectedProviders.has(link.provider)}
                      onToggle={() => toggleProvider(link.provider)}
                    />
                  ))}
              </TabsContent>
            ))}
          </Tabs>
        )}

        {step === 'configure' && (
          <div className="space-y-4">
            <div className="space-y-2">
              <div className="flex justify-between text-sm">
                <span>Configuration Progress</span>
                <span>
                  {validatedProviders.size} of {selectedProviders.size} validated
                </span>
              </div>
              <Progress value={progress} className="h-2" />
            </div>

            <div className="space-y-4">
              {selectedLinks.map((link) => (
                <ProviderConfigCard
                  key={link.provider}
                  link={link}
                  onValidated={(valid) => handleProviderValidated(link.provider, valid)}
                />
              ))}
            </div>
          </div>
        )}

        {step === 'complete' && (
          <div className="text-center py-8 space-y-4">
            <div className="mx-auto w-16 h-16 rounded-full bg-green-500/10 flex items-center justify-center">
              <CheckCircle2 className="h-8 w-8 text-green-500" />
            </div>
            <div>
              <p className="text-lg font-medium">All set!</p>
              <p className="text-muted-foreground">
                You&apos;ve connected {validatedProviders.size} services
              </p>
            </div>
            <div className="flex flex-wrap justify-center gap-2">
              {Array.from(validatedProviders).map((provider) => (
                <Badge key={provider} variant="secondary">
                  {links.find((l) => l.provider === provider)?.display_name || provider}
                </Badge>
              ))}
            </div>
          </div>
        )}
      </CardContent>

      <CardFooter className="flex justify-between">
        {step === 'select' && (
          <>
            <div className="text-sm text-muted-foreground">
              {selectedProviders.size} selected
            </div>
            <Button
              onClick={() => setStep('configure')}
              disabled={selectedProviders.size === 0}
            >
              Continue <ArrowRight className="h-4 w-4 ml-2" />
            </Button>
          </>
        )}

        {step === 'configure' && (
          <>
            <Button variant="outline" onClick={() => setStep('select')}>
              <ArrowLeft className="h-4 w-4 mr-2" /> Back
            </Button>
            <Button onClick={() => setStep('complete')}>
              {validatedProviders.size === selectedProviders.size ? 'Complete' : 'Skip for now'}{' '}
              <ArrowRight className="h-4 w-4 ml-2" />
            </Button>
          </>
        )}

        {step === 'complete' && (
          <>
            <Button variant="outline" onClick={() => setStep('configure')}>
              <ArrowLeft className="h-4 w-4 mr-2" /> Configure more
            </Button>
            <Button onClick={() => onComplete?.(Array.from(validatedProviders))}>
              Go to Dashboard <ArrowRight className="h-4 w-4 ml-2" />
            </Button>
          </>
        )}
      </CardFooter>
    </Card>
  )
}
