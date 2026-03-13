---
description: "Start Day workflow — context sync, observer audit, standup, sprint plan"
argument-hint: "[full|light]"
allowed-tools: Read, Glob, Grep, Bash, Write, Edit, Agent
---

# /begin — Start Day Workflow v2

You are executing Tim's Start Day workflow. Mode: **$ARGUMENTS** (default: "full" if blank).

## Dynamic Context

Current project state:
! `cat .claude/PROJECT_CONTEXT.md 2>/dev/null || echo "No PROJECT_CONTEXT.md found — will generate one."`

Git state:
! `git status --short 2>/dev/null | head -10`
! `git log --oneline -5 2>/dev/null`

Unresolved blockers:
! `cat .claude/observers/ALERTS.md 2>/dev/null || echo "No alerts."`

Cost state:
! `jq '.' ~/.claude/daily-cost.json 2>/dev/null || echo '{"spent": 0, "budget_monthly": 100}'`

## Instructions

### Mode Detection

If `$1` is "light" OR the only planned work today is docs/typos/config/single-file patches:
- Run **Phase 1 only**, then report ready status
- Skip Phases 2-4

If `$1` is "full" or blank:
- Run **all 4 phases** in order

### Phase 1: Context Sync + Environment Health (~3 min)

1. Read `.claude/PROJECT_CONTEXT.md` — verify it matches the current project. If missing, auto-generate from git log + package.json/pyproject.toml
2. Show git state (branch, ahead/behind, dirty files)
3. Environment health checks:
   - `package.json` exists but no `node_modules`? → warn "Run npm install"
   - `requirements.txt` exists but no `.venv`? → warn "Run pip install"
   - `.env.example` exists but no `.env`? → warn "Copy .env.example → .env"
4. Cost check: show MTD spend vs $100/mo budget with percentage
5. Show any unresolved items from `.claude/observers/ALERTS.md`
   - BLOCKERs must be cleared or moved to Backlog.md with owner + ETA before new feature work

### Phase 2: Observer Audit (~5 min) [FULL DAY ONLY]

Run two observer audits as point-in-time checks (NOT persistent daemons):

**Code Quality Observer** (use haiku model if spawning subagent):
- Audit `git diff HEAD~5..HEAD` for: tech debt, test gaps, silent exception handlers, hardcoded values, unused imports
- Write findings to `.claude/observers/QUALITY.md`
- Format: `[CRITICAL | WARNING | INFO] — file:line — description — fix`

**Architecture Observer** (use sonnet model):
- Check for: contract violations, scope creep, duplicate logic, unresolved TODOs blocking other work, missing deps
- Write findings to `.claude/observers/ARCH.md`
- Format: `[BLOCKER | RISK | SMELL] — component — description — impact`
- Hard blockers also go to `.claude/observers/ALERTS.md`

**Devil's Advocate**: Challenge both reports. Are flagged issues real and actionable, or noise? Any gaps between last session and today's assumptions?

### Phase 3: Standup Report (~2 min) [FULL DAY ONLY]

Present this report before sprint plan:

```markdown
## Standup: [PROJECT_NAME] — YYYY-MM-DD

### Git State
Branch: [branch] | Ahead/Behind: [N/N] | Dirty files: [N]

### Budget
Yesterday: $[X] | MTD: $[X] | % of $100/mo cap: [N]%

### Completed Since Last Session
- [task] → [outcome metric]

### Carry-Overs
| Task | Worktree/Branch | % Complete |
|------|-----------------|------------|

### Observer Flags
- CRITICALs: [count] | BLOCKERs: [count]
- [list each]

### Devil's Advocate Findings
- [gaps, drift, or hidden blockers]
```

### Phase 4: Sprint Plan (~3 min) [FULL DAY ONLY]

**Hard gate:** All observer BLOCKERs must be cleared first.

For each proposed task:
- Route through agent-capability-matrix → assign skill + model tier
- Show parallelization strategy (worktrees vs subagents)
- Include cost forecast

```markdown
## Sprint Plan — YYYY-MM-DD

| # | Task | Agent/Skill | Model | Worktree | Est Cost |
|---|------|-------------|-------|----------|----------|

**Session forecast:** $[X] | **Parallelization:** [strategy]
```

**GATE: Wait for user approval before any work begins. Do not proceed without explicit confirmation.**
