---
name: fabric-cli
description: Referência de comandos de LEITURA do Microsoft Fabric CLI (fab) neste projeto. Use ao consultar workspaces, itens, propriedades, tabelas e schemas do Fabric, ou ao diagnosticar login e certificados.
---

# Fabric CLI (fab) – somente leitura

O `fab` é instalado pelo `uv sync` (versão fixa no `pyproject.toml`). Sempre execute
via **`uv run python scripts/fab_ro.py ...`** (mesmos argumentos do `fab`), um comando por vez
(modo script, nunca o modo interativo). O `fab_ro.py` aplica as regras da guarda e confere a
conta logada antes de executar, em qualquer ferramenta. Não chame `uv run fab` diretamente.
Login: `uv run python scripts/entrar.py` (ver skill `iniciar-projeto`, Passo 1).

## Regras
- Somente leitura e sem cópias. A guarda (`scripts/guarda.py`) bloqueia `rm`, `mv`, `cp`, `export`,
  `import`, `mkdir`, `set`, `run`, `job`, `table load/optimize/vacuum`, `config set`,
  qualquer `-o/--output` e `fab api` com método diferente de GET.
- Somente o workspace de `projeto/projeto.yaml` (`workspace_alvo` e, se autorizados,
  `workspaces_leitura_extra`). Não tente outros workspaces.
- Caminhos no padrão `Workspace.Workspace/Item.Tipo`, entre aspas quando houver espaços:
  `"Meu WS.Workspace/lakehouse_x.Lakehouse"`.
- Não invente flags: `uv run python scripts/fab_ro.py <comando> --help` ou MCP `microsoft-learn`.
- Nunca imprima tokens (`fab auth status` já mascara).

## Comandos úteis
| Objetivo | Comando |
|---|---|
| Sessão | `uv run python scripts/fab_ro.py auth status` |
| Login (abre o navegador; o usuário escolhe a conta) | `uv run python scripts/entrar.py` |
| Trocar de conta (SÓ com permissão do usuário) | `uv run python scripts/entrar.py --trocar` |
| Existe? | `uv run python scripts/fab_ro.py exists "<ws>.Workspace"` |
| Itens do workspace | `uv run python scripts/fab_ro.py ls "<ws>.Workspace" -l` |
| Propriedade específica | `uv run python scripts/fab_ro.py get "<ws>.Workspace" -q id` |
| Tabelas de um Lakehouse | `uv run python scripts/fab_ro.py ls "<ws>.Workspace/<lh>.Lakehouse/Tables"` (com schemas: `.../Tables/<schema>`) |
| Schema de tabela | `uv run python scripts/fab_ro.py table schema "<ws>.Workspace/<lh>.Lakehouse/Tables/<schema>/<tabela>"` |
| Arquivos (Files) | `uv run python scripts/fab_ro.py ls "<ws>.Workspace/<lh>.Lakehouse/Files" -l` |
| API REST (GET) | `uv run python scripts/fab_ro.py api "workspaces/<id>/items"` |
| Capacidades visíveis | `uv run python scripts/fab_ro.py ls .capacities -l` |

Para levantar o workspace use a skill `fabric-inventario` (`scripts/inventario.py` e
`scripts/ler_item.py`). Nunca copie itens ou arquivos do workspace: `fab export`, `fab cp`,
`fab get -o` e redirecionar leituras para arquivo são bloqueados pela guarda.

## Problemas comuns
| Sintoma | Causa provável | Ação |
|---|---|---|
| `CERTIFICATE_VERIFY_FAILED` / `SSLError` | Antivírus ou proxy com inspeção HTTPS (ex.: Avast Web Shield) | O `pip-system-certs` do projeto costuma resolver. Se persistir: exceção no antivírus para `login.microsoftonline.com`, `api.fabric.microsoft.com` e `*.dfs.fabric.microsoft.com` |
| `Logged In: False` | Sem login ou login expirado | Avise o usuário e rode `uv run python scripts/entrar.py` |
| `NotFound` em workspace | Nome errado ou sem acesso | `uv run python scripts/fab_ro.py ls` e confirmar com o usuário |
| MCP `microsoft-learn` não conecta | Mesma inspeção HTTPS | Exceção no antivírus para `learn.microsoft.com`, depois reconectar o MCP na ferramenta (Claude Code: `/mcp`) |
| Capacidade não aparece em `.capacities` | Conta sem papel na capacidade | Consumo de CU não é acessível pelo `fab`; ver README |
