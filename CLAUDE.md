# ai-cost-optimizer

## Overview
[Add project description]

## Tech Stack
[Add tech stack]

## Active Skills
Check ~/.claude/skills/ for available skills. Key ones:
- `supabase-sql-skill` - SQL migrations
- `langgraph-agents-skill` - Multi-agent systems
- `trading-signals-skill` - Technical analysis
- `sales-outreach-skill` - B2B automation
- `runpod-deployment-skill` - GPU deployment

## Key Files
[Add key files/directories]

---

## Scientia Capital AI Stack

This project is part of the Scientia Capital AI Stack ecosystem.

### Core Infrastructure Repositories
- **lang-core** (Foundation): LangChain/LangGraph middleware, LLM providers, Redis, FastAPI
  - https://github.com/ScientiaCapital/lang-core
- **vlm-ai-core** (Vision): Qwen VL, Gemini Vision, Document AI, OCR
  - https://github.com/ScientiaCapital/vlm-ai-core
- **voice-ai-core** (Voice): Cartesia TTS, Deepgram STT, Twilio integration
  - https://github.com/ScientiaCapital/voice-ai-core

### Integration Pattern
```bash
# Infrastructure from lang-core
python ~/lang-core/scripts/inline_to_project.py /your/project --modules middleware providers

# Vision capabilities from vlm-ai-core
python ~/vlm-ai-core/scripts/inline_to_project.py /your/project --modules providers preprocessing

# Voice capabilities from voice-ai-core
python ~/voice-ai-core/scripts/inline_to_project.py /your/project --modules providers types
```

### Stack Principles
- **NO OpenAI** - Use Anthropic Claude, Google Gemini, DeepSeek, Qwen via OpenRouter
- API keys ONLY in `.env` files, never hardcoded
- Each repo has one domain - no duplication
