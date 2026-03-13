---
description: "Build workflow — contract setup, execute, polish, security gate, ship"
argument-hint: "[feature-name]"
allowed-tools: Read, Glob, Grep, Bash, Write, Edit, Agent
---

# /build — Feature Build Workflow v2

You are executing Tim's Build workflow for feature: **$ARGUMENTS**

## Dynamic Context

Project context:
! `cat .claude/PROJECT_CONTEXT.md 2>/dev/null || echo "No PROJECT_CONTEXT.md — run /begin first."`

Current sprint plan (if exists):
! `grep -A 20 "Sprint Plan" .claude/TASK.md 2>/dev/null || echo "No sprint plan found."`

Active worktrees:
! `git worktree list 2>/dev/null`

Cost state:
! `jq '.' ~/.claude/daily-cost.json 2>/dev/null || echo '{"spent": 0, "budget_monthly": 100}'`

Existing contracts:
! `ls .claude/contracts/ 2>/dev/null || echo "No contracts directory yet."`

## Instructions

### Phase 1: Contract + Team Setup (~5 min)

1. Load `.claude/PROJECT_CONTEXT.md` — confirm build targets match approved sprint plan
2. Check for feature contract at `.claude/contracts/$1.ts` (or `.claude/contracts/$1.py`)
   - If exists → load and confirm scope
   - If missing → **create it now** with interface definitions, input/output types, error contracts
   - **No builder touches code without a contract**
3. Decompose work into independent tasks
4. Route each task through agent-capability-matrix (use skills on-demand, don't preload)
5. Present assignment map:

```markdown
## Build Assignment — $ARGUMENTS

| Task | Agent | Skill | Worktree | Model | Est Cost |
|------|-------|-------|----------|-------|----------|

Contract: .claude/contracts/$1.ts
```

**GATE: Wait for user approval before spawning any agents or writing code.**

### Phase 2: Execute (~variable)

**Builders** — each receives a task with:
- Task description (< 50 words)
- Contract file path
- Scope boundary (what this agent owns / does NOT touch)
- Verification checklist

Builders run tests inline. Commit only when checklist is green. Push branch — never merge to main directly.

Use conventional commits: `feat:`, `fix:`, `test:`, `refactor:`, `docs:`

**Observers** — run at commit boundaries (point-in-time, not persistent):
- Code Quality Observer: audit `git diff` across builder work
- Architecture Observer: check for contract drift, scope creep, duplicate logic
- Devil's Advocate: at each gate, challenge both teams per §Roles

**Rollback Protocol** — if something breaks:
1. `git stash` current work
2. `git log --oneline -10` — find last known good commit
3. `git diff [good]..HEAD` — identify what broke
4. Selective revert or full reset
5. Run tests to confirm recovery
6. Use `debug-like-expert` skill for root cause if needed
7. Document in `.claude/observers/ALERTS.md`

### Phase 3: Polish + Hardening [SKIP ON LIGHT DAY]

No new features in this phase. Address observer findings in priority order:

1. All CRITICALs from `QUALITY.md`
2. All BLOCKERs from `ARCH.md`
3. Test coverage: net positive delta on every modified file
4. Refactor scope creep or duplicate logic flagged by observers
5. Update API docs and inline comments for modified interfaces

Observers continue monitoring during hardening.

### Phase 4: Security + Quality Gate (blocking) [SKIP ON LIGHT DAY]

Run in order. Any failure stops the phase — fix and re-run:

```bash
# 1. Secrets scan
gitleaks detect --source . 2>/dev/null || echo "gitleaks not installed — run manual grep"

# 2. Targeted credential grep
grep -rn "sk-\|AIza\|AKIA\|ghp_\|password\s*=" --include="*.py" --include="*.ts" --include="*.env" .

# 3. Git history check
git log --all --full-history -- "*.env" "*.pem" "*.key"

# 4. Dependency audit
npm audit --audit-level=critical 2>/dev/null || pip-audit 2>/dev/null || echo "No package auditor available"

# 5. Full test suite
pytest --cov=src 2>/dev/null || npm test -- --coverage 2>/dev/null || echo "No test runner configured"

# 6. Observer gates — CRITICAL count in QUALITY.md must be 0, BLOCKER count in ARCH.md must be 0

# 7. Cost check
SPENT=$(jq '.spent // 0' ~/.claude/daily-cost.json 2>/dev/null || echo 0)
echo "Session spend check — MTD: \$$SPENT"
```

**GATE: Devil's Advocate sign-off required. All 7 checks must pass before shipping.**

### Phase 5: Ship + Capture

```bash
# Conventional commits per change type
git add [specific-files]
git commit -m "feat: [description]"

# Push branch
git push origin [branch]

# Merge to main ONLY after Phase 4 is fully green
# git checkout main && git merge [branch] && git push

# Clean merged worktrees
git worktree list
```

Capture portfolio metrics for End Day:
- Lines shipped (backend / frontend / tests / hardening)
- Observer findings resolved
- Tech debt prevented
- Security findings caught before merge
- Cost: actual vs forecast

Write tomorrow's handoff to `.claude/PROJECT_CONTEXT.md`.
Archive observer files to `.claude/archive/YYYY-MM-DD-OBSERVER-*.md` and reset.

**GATE: Wait for approval between major phases.**
