# CLAUDE.md — fabric-ai-doc-helper

@AGENTS.md

## Específico do Claude Code
- Skills: carregadas de `.claude/skills/` (cópia gerada; ver AGENTS.md → Skills).
- Guarda: hook PreToolUse em `.claude/settings.json` → `scripts/adaptadores/claude_code.py`.
- Entrevista: use a ferramenta de perguntas (AskUserQuestion).
- MCP `microsoft-learn`: configurado em `.mcp.json`.