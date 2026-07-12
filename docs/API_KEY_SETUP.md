# API Key Setup Guide

> **One-click links** to every API key page. No more hunting through dashboards.

## Quick Links Table

Click any link below to go directly to the API key page for that service.

### LLM Providers

| Service                | Get API Key                                                                        | Notes                         |
| ---------------------- | ---------------------------------------------------------------------------------- | ----------------------------- |
| **Anthropic Claude**   | [console.anthropic.com/settings/keys](https://console.anthropic.com/settings/keys) | Click "Create Key" → Copy     |
| **Google AI / Gemini** | [aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey)           | Click "Create API Key"        |
| **OpenRouter**         | [openrouter.ai/keys](https://openrouter.ai/keys)                                   | Access 50+ models via one key |
| **Groq**               | [console.groq.com/keys](https://console.groq.com/keys)                             | Ultra-fast LPU inference      |
| **Cerebras**           | [cloud.cerebras.ai/platform](https://cloud.cerebras.ai/platform)                   | 1000+ tokens/second           |
| **Together AI**        | [api.together.xyz/settings/api-keys](https://api.together.xyz/settings/api-keys)   | Fine-tuned models             |
| **Hugging Face**       | [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens)           | Models, Spaces, Inference API |

### Voice AI - Text-to-Speech (TTS)

| Service        | Get API Key                                                                        | Pricing                  |
| -------------- | ---------------------------------------------------------------------------------- | ------------------------ |
| **Cartesia**   | [play.cartesia.ai/console](https://play.cartesia.ai/console)                       | $0.042/second            |
| **ElevenLabs** | [elevenlabs.io/app/settings/api-keys](https://elevenlabs.io/app/settings/api-keys) | $0.30/1K chars (Starter) |

### Voice AI - Speech-to-Text (STT)

| Service        | Get API Key                                                           | Pricing                 |
| -------------- | --------------------------------------------------------------------- | ----------------------- |
| **Deepgram**   | [console.deepgram.com](https://console.deepgram.com) → Project → Keys | $0.0043/minute (Nova 2) |
| **AssemblyAI** | [assemblyai.com/app/account](https://www.assemblyai.com/app/account)  | $0.0037/second          |

### Infrastructure

| Service      | Get API Key                                                                     | What You Need                          |
| ------------ | ------------------------------------------------------------------------------- | -------------------------------------- |
| **Supabase** | [supabase.com/dashboard](https://supabase.com/dashboard/project/_/settings/api) | URL, Anon Key, Service Key, JWT Secret |
| **Vercel**   | [vercel.com/account/tokens](https://vercel.com/account/tokens)                  | Token, Org ID, Project ID              |
| **Railway**  | [railway.app/account/tokens](https://railway.app/account/tokens)                | API Token                              |
| **RunPod**   | [runpod.io/console/user/settings](https://www.runpod.io/console/user/settings)  | API Key                                |

### AI Media

| Service    | Get API Key                                                                    | Notes               |
| ---------- | ------------------------------------------------------------------------------ | ------------------- |
| **Runway** | [app.runwayml.com/account/api-keys](https://app.runwayml.com/account/api-keys) | AI video generation |

### Observability

| Service       | Get API Key                                                          | Notes                   |
| ------------- | -------------------------------------------------------------------- | ----------------------- |
| **LangSmith** | [smith.langchain.com/settings](https://smith.langchain.com/settings) | LLM tracing & debugging |

### Billing

| Service    | Get API Key                                                          | Notes                  |
| ---------- | -------------------------------------------------------------------- | ---------------------- |
| **Stripe** | [dashboard.stripe.com/apikeys](https://dashboard.stripe.com/apikeys) | Use test keys for dev! |

---

## Setup Steps

### 1. Copy the Template

```bash
cp .env.template .env
```

### 2. Get Your API Keys

Click the links above for each service you use. Each link goes directly to the API key page.

### 3. Paste Keys into .env

```env
# Example
ANTHROPIC_API_KEY=sk-ant-api03-xxxxx
GOOGLE_API_KEY=AIzaSyxxxxx
OPENROUTER_API_KEY=sk-or-v1-xxxxx
```

### 4. Validate Your Keys

```bash
python scripts/validate_api_keys.py
```

Expected output:

```
╭──────────────────────────────────────────────────────╮
│           AI Stack Optimizer - Key Validator         │
├──────────────────────────────────────────────────────┤
│ ANTHROPIC_API_KEY     ✅ Connected  (Claude 4.5)    │
│ GOOGLE_API_KEY        ✅ Connected  (Gemini 1.5)    │
│ OPENROUTER_API_KEY    ✅ Connected  (50+ models)    │
│ GROQ_API_KEY          ⚠️  Not configured            │
│ DEEPGRAM_API_KEY      ✅ Connected  (Nova 2)        │
│ SUPABASE_URL          ✅ Connected                   │
├──────────────────────────────────────────────────────┤
│ Total: 5/14 configured                               │
╰──────────────────────────────────────────────────────╯
```

---

## Troubleshooting

### "Invalid API Key" Error

| Provider   | Common Issues                                                |
| ---------- | ------------------------------------------------------------ |
| Anthropic  | Key starts with `sk-ant-` not just `sk-`                     |
| OpenRouter | Key starts with `sk-or-`                                     |
| Groq       | Key is case-sensitive                                        |
| Supabase   | Need ALL four values: URL, Anon Key, Service Key, JWT Secret |

### "Rate Limited" Error

Most providers have free tiers with rate limits:

| Provider   | Free Tier Limit    |
| ---------- | ------------------ |
| Anthropic  | $5 credit to start |
| Groq       | 100 req/min        |
| Deepgram   | $200 credit        |
| OpenRouter | Pay-as-you-go      |

### "Connection Refused"

1. Check your internet connection
2. Some providers block VPNs
3. Check if the service has regional restrictions

---

## Provider-Specific Notes

### Anthropic Claude

- Keys start with `sk-ant-api03-`
- Models: claude-opus-4-5, claude-sonnet-4-5, claude-haiku-4-5
- Pricing: $15/$3/$1 per 1M input tokens

### OpenRouter

- Single key gives access to 50+ models
- DeepSeek V3: $0.30/1M tokens (90% cheaper than Claude!)
- Qwen 2.5 72B: $0.35/1M tokens

### Supabase

You need 4 values from Settings → API:

1. **URL**: `https://xxxxx.supabase.co`
2. **Anon Key**: `eyJhbGc...` (public, respects RLS)
3. **Service Key**: `eyJhbGc...` (admin, bypasses RLS)
4. **JWT Secret**: For token validation

### Vercel

You need 3 values:

1. **Token**: Account → Tokens → Create
2. **Org ID**: Found in URL when viewing organization
3. **Project ID**: Project Settings → General

---

## Security Best Practices

1. **Never commit `.env` to git** - It's already in `.gitignore`
2. **Use test keys for development** - Stripe has `sk_test_*` keys
3. **Rotate keys regularly** - Especially if exposed
4. **Use different keys per environment** - Dev, staging, production

---

## Need Help?

- **Dashboard**: Check `/settings` for live provider status
- **Validator**: Run `python scripts/validate_api_keys.py`
- **Support**: Open an issue on GitHub
