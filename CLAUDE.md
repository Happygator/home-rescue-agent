# Project Instructions

## gstack

This project uses [gstack](https://github.com/garrytan/gstack) — Garry Tan's role-based Claude Code skills toolkit.

### Web browsing
- **Always use the `/browse` skill** from gstack for all web browsing, QA, and site dogfooding.
- **Never use `mcp__claude-in-chrome__*` tools.** All browser automation goes through gstack's `/browse`.

### Available skills

| Skill | Purpose |
| --- | --- |
| `/office-hours` | YC Office Hours — two modes. |
| `/plan-ceo-review` | CEO/founder-mode plan review. |
| `/plan-eng-review` | Eng manager-mode plan review. |
| `/plan-design-review` | Designer's-eye plan review. |
| `/plan-devex-review` | Developer experience plan review. |
| `/design-consultation` | Propose a complete design system with previews. |
| `/design-shotgun` | Generate multiple design variants and compare. |
| `/design-html` | Generate production-quality HTML/CSS. |
| `/design-review` | Designer's-eye QA: visual inconsistency, hierarchy, AI-slop. |
| `/devex-review` | Live developer experience audit. |
| `/review` | Review the current diff. |
| `/ship` | Ship workflow: test, review, bump version, changelog, commit, PR. |
| `/land-and-deploy` | Land and deploy workflow. |
| `/canary` | Post-deploy canary monitoring. |
| `/benchmark` | Performance regression detection. |
| `/browse` | Fast headless browser for QA and site dogfooding. |
| `/connect-chrome` | Connect to a Chromium browser session. |
| `/qa` | Systematically QA test a web app and fix bugs found. |
| `/qa-only` | Report-only QA testing. |
| `/setup-browser-cookies` | Import cookies from your real browser into browse. |
| `/setup-deploy` | Configure deployment settings for /land-and-deploy. |
| `/setup-gbrain` | Set up gbrain persistent memory for this agent. |
| `/retro` | Weekly engineering retrospective. |
| `/investigate` | Systematic debugging with root cause investigation. |
| `/document-release` | Post-ship documentation update. |
| `/document-generate` | Generate missing documentation from scratch. |
| `/codex` | OpenAI Codex CLI wrapper. |
| `/cso` | Chief Security Officer mode. |
| `/autoplan` | Auto-review pipeline (CEO, design, eng, DX) run sequentially. |
| `/careful` | Safety guardrails for destructive commands. |
| `/freeze` | Restrict file edits to a specific directory for the session. |
| `/guard` | Full safety mode: destructive warnings + directory-scoped edits. |
| `/unfreeze` | Clear the freeze boundary set by /freeze. |
| `/gstack-upgrade` | Upgrade gstack to the latest version. |
| `/learn` | Manage project learnings. |
