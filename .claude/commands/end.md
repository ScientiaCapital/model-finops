---
description: "End Day workflow — observer report, security sweep, state sync, portfolio, git lockdown, handoff"
argument-hint: ""
allowed-tools: Read, Glob, Grep, Bash, Write, Edit, Agent
---

# /end — End Day Workflow v2

You are executing Tim's End Day workflow.

## Dynamic Context

Project context:
! `cat .claude/PROJECT_CONTEXT.md 2>/dev/null || echo "No PROJECT_CONTEXT.md found."`

Observer reports:
! `echo "=== QUALITY ===" && cat .claude/observers/QUALITY.md 2>/dev/null || echo "No quality report."`
! `echo "=== ARCH ===" && cat .claude/observers/ARCH.md 2>/dev/null || echo "No arch report."`
! `echo "=== ALERTS ===" && cat .claude/observers/ALERTS.md 2>/dev/null || echo "No alerts."`

Git state:
! `git status --short 2>/dev/null | head -10`
! `git log --since="today 00:00" --oneline 2>/dev/null`

Cost state:
! `jq '.' ~/.claude/daily-cost.json 2>/dev/null || echo '{"spent": 0, "budget_monthly": 100}'`

Active worktrees:
! `git worktree list 2>/dev/null`

## Instructions

Run all 6 phases in order. No phase is skippable.

### Phase 1: Observer Final Report (~3 min)

Pull `.claude/observers/QUALITY.md` and `.claude/observers/ARCH.md`.

Disposition every item — nothing silently dropped:

| Severity | Action |
|---|---|
| CRITICAL | Resolve now OR log to `Backlog.md` with owner + ETA |
| BLOCKER | Resolve now OR log to `Backlog.md` with owner + ETA |
| WARNING | Log to `Backlog.md`, prioritize by impact |
| RISK | Log to `Backlog.md`, prioritize by impact |
| INFO | Log or discard with justification |

**Devil's Advocate**: verify every flagged item was genuinely addressed, not just acknowledged. Confirm no work today introduced new issues observers missed.

### Phase 2: Security Sweep (~2 min)

Check if any new commits exist since the last security gate:

```bash
# Count commits since last build security gate
COMMITS_TODAY=$(git log --since="today 00:00" --oneline 2>/dev/null | wc -l | tr -d ' ')
echo "Commits today: $COMMITS_TODAY"
```

**Skip if:** no new commits since Build Phase 4 security gate passed (and Build Phase 4 was run today).

**Run if:** any commits after Build Phase 4:

```bash
gitleaks detect --source . --verbose 2>/dev/null || echo "gitleaks not available — running manual scan"
grep -rn "sk-\|AIza\|AKIA\|ghp_\|password\s*=" --include="*.py" --include="*.ts" --include="*.env" .
git log --all --full-history -- "*.env" "*.pem" "*.key"
```

Zero tolerance. Nothing ships with a secret in the codebase or git history.

### Phase 3: State Sync (~3 min)

Update all planning docs to reflect true end-of-day state:

| Doc | Action |
|---|---|
| `.claude/TASK.md` | Mark completed tasks done. Archive stale items (> 7 days, no movement) |
| `.claude/PLANNING.md` | Adjust timeline based on today's actual velocity |
| `.claude/Backlog.md` | Promote observer WARNINGs/RISKs to prioritized items with effort + impact |
| Observer files | Copy to `.claude/archive/YYYY-MM-DD-OBSERVER-*.md`, then reset both files |

### Phase 4: Portfolio Metrics (~2 min)

Extract and present:

```markdown
## Portfolio Capture — YYYY-MM-DD

### Output
- Lines shipped: [total] (backend: [N] | frontend: [N] | tests: [N])
- Features: [count] | Fixes: [count]

### Quality
- Observer CRITICALs resolved: [N]
- Observer BLOCKERs resolved: [N]
- Tech debt prevented: [what observers caught]

### Cost
- Session spend: $[X]
- MTD: $[X] / $100
- Cost per feature: $[X]

### GTME Value
- GTM motion enabled: [what sales/marketing process this enables]
- Operational leverage: [manual work reduced, time-to-value improved]
- Portfolio positioning: [how to present this as GTME evidence]
- Skill demonstrated: [rev ops | sales tooling | PLG | data-driven GTM]
```

Append to persistent metrics:

```bash
DATE=$(date +%Y-%m-%d)
COMMITS=$(git log --since="today 00:00" --oneline 2>/dev/null | wc -l | tr -d ' ')
FEATS=$(git log --since="today 00:00" --oneline --grep="^feat" 2>/dev/null | wc -l | tr -d ' ')
FIXES=$(git log --since="today 00:00" --oneline --grep="^fix" 2>/dev/null | wc -l | tr -d ' ')
COST=$(jq '.spent // 0' ~/.claude/daily-cost.json 2>/dev/null || echo 0)
mkdir -p ~/.claude/portfolio
echo "{\"date\":\"$DATE\",\"commits\":$COMMITS,\"features\":$FEATS,\"fixes\":$FIXES,\"cost\":$COST}" >> ~/.claude/portfolio/daily-metrics.jsonl
```

### Phase 5: Git Lockdown (~2 min)

```bash
# Verify clean state
git status --short
# If dirty → commit with conventional format before proceeding

# Push everything
git push origin main 2>/dev/null
git push origin --all 2>/dev/null

# List worktrees — clean merged ones
git worktree list

# Delete stale remote branches (merged into main)
git branch -r --merged main 2>/dev/null | grep -v main | head -5
```

Nothing closes with uncommitted work or orphaned worktrees.

### Phase 6: Tomorrow's Handoff (~1 min)

Write to `.claude/PROJECT_CONTEXT.md`:

```
Tomorrow: [task] via [skill] | [builder config] | Est: [time], $[cost] | Observer notes: [top unresolved flag]
```

Output a full end-of-day report covering all 6 phases with final status on every gate.

**GATE: Wait for user confirmation before marking session closed.**
