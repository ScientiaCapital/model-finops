# Project Shortcuts & Quick Commands

## Convenience Scripts

- `./morning_start.sh` - Project status overview (docs, git, TODOs)
- `./refresh_docs.sh` - Refresh documentation with DeepSeek (~$0.01)
- `./quick_review.sh` - Code review prompt guide

## Superpowers Skills Available

Use these via Claude Code for automated workflows:

### Planning & Design

- `superpowers:brainstorming` - Refine ideas before coding
- `superpowers:writing-plans` - Create detailed implementation plans

### Development

- `superpowers:test-driven-development` - TDD workflow
- `superpowers:subagent-driven-development` - Multi-task parallelization

### Quality Assurance

- `superpowers:code-reviewer` - Review against project standards
- `superpowers:verification-before-completion` - Verify before claiming done
- `superpowers:systematic-debugging` - Root cause analysis

### Git & Collaboration

- `superpowers:finishing-a-development-branch` - Branch completion workflow
- `superpowers:requesting-code-review` - Prepare for PR
- `superpowers:receiving-code-review` - Handle review feedback

## Common Workflows

### Morning Start

```bash
./morning_start.sh
```

### After Coding Session

Ask Claude: "Use superpowers:code-reviewer to review recent changes"

### Before Commit

Ask Claude: "Use superpowers:verification-before-completion"

### Feature Development

1. Ask Claude: "Use superpowers:brainstorming to design [feature]"
2. Ask Claude: "Use superpowers:test-driven-development to implement [feature]"
3. Run: `./quick_review.sh`
4. Ask Claude: "Use superpowers:verification-before-completion"

### After Major Changes

```bash
./refresh_docs.sh
```

## Documentation

- **CLAUDE.md** - Project setup, workflow, commands
- **context.md** - Current state, focus areas, next steps
- **architecture.md** - Technical design, patterns, dependencies
- **shortcuts.md** - This file

## Monthly Automation

Documentation auto-refreshes first Sunday of every month at 2 AM using DeepSeek.

Manual refresh anytime: `./refresh_docs.sh`
