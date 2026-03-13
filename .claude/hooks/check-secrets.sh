#!/bin/bash
# check-secrets.sh — PreToolUse hook for Write|Edit operations
# Scans tool input for common secret patterns before allowing file writes
# Returns non-zero + JSON to block if secrets detected

TOOL_INPUT="$1"

# Patterns that indicate hardcoded secrets
PATTERNS=(
  "sk-[a-zA-Z0-9]{20,}"        # OpenAI / Stripe keys
  "AIza[a-zA-Z0-9_-]{35}"      # Google API keys
  "AKIA[A-Z0-9]{16}"           # AWS access keys
  "ghp_[a-zA-Z0-9]{36}"        # GitHub personal tokens
  "ghs_[a-zA-Z0-9]{36}"        # GitHub server tokens
  "xox[bpas]-[a-zA-Z0-9-]+"    # Slack tokens
  "-----BEGIN.*PRIVATE KEY"     # Private keys
)

for pattern in "${PATTERNS[@]}"; do
  if echo "$TOOL_INPUT" | grep -qE "$pattern" 2>/dev/null; then
    echo '{"hookSpecificOutput": {"permissionDecision": "deny", "reason": "SECRET DETECTED: Content matches pattern '"$pattern"'. Do not hardcode secrets — use environment variables instead."}}'
    exit 0
  fi
done

# No secrets found — allow the write
exit 0
