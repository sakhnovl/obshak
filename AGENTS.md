# Project Agent Protocol

This repository uses `.agent/` as the primary operating system for task routing, skills, workflows, and validation.

## ⚠️ MANDATORY: Session Start Protocol

**При начале КАЖДОЙ новой сессии или потере контекста необходимо:**

1. **Сначала** прочитать `.agent/ARCHITECTURE.md` — полная структура проекта
2. **Затем** прочитать `.agent/rules/GEMINI.md` — правила и конвенции
3. **Только после этого** приступать к выполнению задач

> Это не рекомендация, а **обязательное требование**. Без чтения этих файлов НЕ начинать реализацию.

## Always-On Rule

For every task in this project, consult `.agent` before implementation.

1. Read `.agent/ARCHITECTURE.md` at the start of a session or after losing context.
2. Read `.agent/rules/GEMINI.md` before code, design, orchestration, or validation work.
3. Identify the task domain, then open the matching file in `.agent/agents/`.
4. Read the selected agent's frontmatter `skills:` list.
5. Open each required `.agent/skills/<skill>/SKILL.md`, then read only the relevant referenced files.
6. For multi-step or multi-domain tasks, consult `.agent/workflows/` and prefer `orchestrate.md`, `plan.md`, `debug.md`, `enhance.md`, or `test.md` as appropriate.
7. After edits, run the relevant `.agent/scripts/checklist.py` flow or the skill-specific validation scripts.

## Rule Priority

If instructions overlap or conflict, apply them in this order:

1. `.agent/rules/GEMINI.md`
2. `.agent/agents/*.md`
3. `.agent/skills/**/SKILL.md`
4. `.agent/workflows/*.md`

## Agent Routing Defaults

- Frontend/UI: `.agent/agents/frontend-specialist.md`
- Backend/API/Auth: `.agent/agents/backend-specialist.md`
- Database/Schema: `.agent/agents/database-architect.md`
- Debugging/Bugfix: `.agent/agents/debugger.md`
- Testing: `.agent/agents/test-engineer.md`
- Security: `.agent/agents/security-auditor.md`
- Performance: `.agent/agents/performance-optimizer.md`
- Planning: `.agent/agents/project-planner.md`
- Multi-domain work: `.agent/agents/orchestrator.md`
- Repo discovery and analysis: `.agent/agents/explorer-agent.md`

## Working Convention

When responding about implementation work in this repository, explicitly state which `.agent` role or skill is being applied.

## Completion Notification Gate

Before marking any task as complete, send a Telegram message first and only then finish the task.

1. Run `python .agent/scripts/notify_telegram.py "<short completion summary>"` before the final completion response.
2. Prefer `CODEX_TELEGRAM_CHAT_ID` when set.
3. Otherwise fall back to the first id from `TELEGRAM_ADMIN_IDS`.
4. If neither is available, `TELEGRAM_CHANNEL_ID` may be used as a last fallback.
5. If the Telegram notification fails, do not treat the task as complete until the failure is reported or fixed.
