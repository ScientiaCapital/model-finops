# Security Policy

## 🔒 Credential Management

### CRITICAL RULES - NEVER VIOLATE

1. **NEVER hardcode API keys, tokens, or secrets in code**
   - ❌ `const API_KEY = "sk-123456789"`
   - ✅ `const API_KEY = process.env.API_KEY` (Node.js)
   - ✅ `API_KEY = os.getenv("API_KEY")` (Python)

2. **ALL credentials MUST be in .env files ONLY**
   - `.env` - Real credentials (gitignored)
   - `.env.local` - Local overrides (gitignored)
   - `.env.example` - Placeholders only (tracked in git)

3. **NEVER commit .env files to git**
   - Already protected by `.gitignore`
   - Double-check before every commit: `git status`

## 🛡️ Protected Files (Gitignored)

These files contain secrets and are automatically ignored by git:

```
.env
.env.local
.env.*.local
*.db
*.sqlite
optimizer.db
```

## ✅ Security Audit Checklist

Before every commit, verify:

- [ ] No API keys in code files (`.py`, `.ts`, `.js`)
- [ ] All secrets loaded from `process.env` or `os.getenv()`
- [ ] `.env` files not staged for commit
- [ ] Only `.env.example` contains placeholders
- [ ] No database files committed

## 🔍 How to Scan for Leaked Secrets

### Quick Scan (before commit)

```bash
# Check staged files for API key patterns
git diff --cached | grep -E "sk-[a-zA-Z0-9]{48}|AIza[a-zA-Z0-9_-]{35}|eyJ[a-zA-Z0-9_-]*\."

# If any matches found - STOP! Remove the keys before committing
```

### Full Repository Scan

```bash
# Scan all Python/JS/TS files for hardcoded keys
grep -r "API_KEY\s*=\s*['\"]" --include="*.py" --include="*.js" --include="*.ts" --exclude-dir=node_modules --exclude-dir=.venv .

# Should return empty or only examples/comments
```

### Check Git History

```bash
# Check if .env was ever committed
git log --all --full-history -- "*.env"

# If found, you need to:
# 1. Rotate all exposed keys immediately
# 2. Use git-filter-repo or BFG Repo-Cleaner to remove from history
```

## 🚨 If Credentials Are Exposed

### Immediate Actions

1. **STOP! Do not push to GitHub** (if not pushed yet)
2. **Rotate ALL exposed API keys immediately**:
   - Supabase: Project Settings → API → Generate new service role key
   - OpenRouter: https://openrouter.ai/keys → Revoke & create new
   - Anthropic: https://console.anthropic.com/settings/keys
   - Google AI: https://aistudio.google.com/app/apikey
3. **Remove from git history**:

   ```bash
   # Install git-filter-repo
   pip install git-filter-repo

   # Remove .env from all commits
   git-filter-repo --invert-paths --path .env

   # Force push (ONLY if safe)
   git push origin --force --all
   ```

4. **Update .env with new keys**
5. **Notify team if shared repository**

## 📋 Environment Variable Patterns

### Python (FastAPI Backend)

```python
import os
from dotenv import load_dotenv

load_dotenv()  # Load from .env file

# CORRECT ✅
API_KEY = os.getenv("OPENROUTER_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")

# INCORRECT ❌ - Never do this!
# API_KEY = "sk-or-v1-abc123..."
```

### Node.js / Next.js (Frontend/API Routes)

```typescript
// CORRECT ✅
const apiKey = process.env.OPENROUTER_API_KEY
const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL

// INCORRECT ❌ - Never do this!
// const apiKey = "sk-or-v1-abc123..."
```

### Environment File Hierarchy

```
Project Root:
├── .env              ← Your real secrets (gitignored)
├── .env.local        ← Local dev overrides (gitignored)
├── .env.example      ← Template with placeholders (tracked in git)
└── .gitignore        ← Protects .env files
```

## 🔐 Pre-Commit Hook (Optional but Recommended)

Create `.git/hooks/pre-commit` to automatically block commits with secrets:

```bash
#!/bin/bash

# Scan staged files for API key patterns
if git diff --cached --diff-filter=ACM | grep -qE "sk-[a-zA-Z0-9]{48}|AIza[a-zA-Z0-9_-]{35}|eyJ[a-zA-Z0-9_-]*\."; then
    echo "❌ ERROR: Potential API key detected in staged changes!"
    echo "Please remove hardcoded credentials before committing."
    exit 1
fi

# Check if .env files are staged
if git diff --cached --name-only | grep -qE "^\.env$|^\.env\.local$"; then
    echo "❌ ERROR: .env file staged for commit!"
    echo "Remove it with: git reset HEAD .env"
    exit 1
fi

echo "✅ Pre-commit security check passed"
exit 0
```

Make it executable:

```bash
chmod +x .git/hooks/pre-commit
```

## 📚 Security Tools (Recommended)

### 1. git-secrets (AWS tool, works for all secrets)

```bash
# Install
brew install git-secrets  # macOS
# or: https://github.com/awslabs/git-secrets

# Setup
git secrets --install
git secrets --register-aws
git secrets --add 'sk-[a-zA-Z0-9]{48}'
git secrets --add 'eyJ[a-zA-Z0-9_-]*\.[a-zA-Z0-9_-]*\.[a-zA-Z0-9_-]*'
```

### 2. gitleaks (Comprehensive secret scanner)

```bash
# Install
brew install gitleaks  # macOS

# Scan repository
gitleaks detect --source . --verbose

# Scan before commit
gitleaks protect --staged
```

### 3. trufflehog (Deep history scanning)

```bash
# Install
brew install trufflehog  # macOS

# Scan entire git history
trufflehog git file://. --only-verified
```

## 🎯 Incident Response Plan

### If Keys Were Pushed to GitHub:

1. **Immediate (< 5 min)**:
   - Revoke all exposed keys
   - Generate new keys
   - Update .env locally

2. **Short-term (< 1 hour)**:
   - Remove from git history using git-filter-repo
   - Force push cleaned history
   - Verify keys are gone: `git log --all --full-history -- "*.env"`

3. **Long-term**:
   - Install pre-commit hooks
   - Add gitleaks to CI/CD pipeline
   - Team training on secret management

## 📞 Contacts for Key Rotation

- **Supabase**: Dashboard → Project Settings → API
- **OpenRouter**: https://openrouter.ai/keys
- **Anthropic**: https://console.anthropic.com/settings/keys
- **Google AI**: https://aistudio.google.com/app/apikey
- **Cerebras**: https://cloud.cerebras.ai/
- **Cartesia**: https://cartesia.ai/dashboard

## ✅ Security Best Practices

1. Use different keys for dev/staging/production
2. Rotate keys every 90 days
3. Never share .env files via Slack/email
4. Use 1Password / Bitwarden for team secret sharing
5. Enable 2FA on all provider accounts
6. Monitor API key usage for anomalies
7. Set spending limits on all API providers

---

**Last Updated**: 2025-01-17
**Incident Count**: 1 (2025-01-XX - .env committed to GitHub, keys rotated)
