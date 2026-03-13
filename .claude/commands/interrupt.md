---
description: "Interrupt Protocol — snapshot current work and pivot to urgent task"
argument-hint: "[reason for pivot]"
allowed-tools: Read, Bash, Write, Edit
---

# /interrupt — Pivot Protocol

You are executing the Interrupt Protocol. Reason: **$ARGUMENTS**

## Dynamic Context

Current git state:
! `git status --short 2>/dev/null`
! `git branch --show-current 2>/dev/null`

## Instructions

Execute these 4 steps in order. No ceremony, no guilt.

### Step 1: Snapshot Current State

```bash
# Commit WIP with descriptive message
git add -A
git commit -m "wip: $ARGUMENTS — snapshot before pivot"
```

### Step 2: Log the Pivot

Append to `.claude/observers/ALERTS.md`:

```
[PIVOT] — $ARGUMENTS — original sprint plan suspended at [timestamp]
```

### Step 3: Acknowledge

Tell the user:
- Current work is safely committed on branch `[branch]`
- Original sprint plan is paused
- Ready to work the urgent item
- When done, they can either resume original work or run `/end`

### Step 4: Ready

Ask the user what the urgent task is and proceed.
