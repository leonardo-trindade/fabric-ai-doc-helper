# CLAUDE.md — fabric-ai-doc-helper

@AGENTS.md

## Específico do Claude Code
- Skills: carregadas de `.claude/skills/`, cópia gerada de `.agents/skills/`. Edite sempre a fonte
  e rode `uv run python scripts/sincronizar_skills.py` (modo manutenção).
- Guarda: hook PreToolUse em `.claude/settings.json` → `scripts/adaptadores/claude_code.py`.
- Entrevista: use a ferramenta de perguntas (AskUserQuestion).
- MCP `microsoft-learn`: configurado em `.mcp.json`.