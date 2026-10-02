---
name: fabric-cli
description: Referência de comandos de LEITURA do Microsoft Fabric CLI (fab) neste projeto. Use ao consultar workspaces, itens, propriedades, tabelas e schemas do Fabric, ou ao diagnosticar login e certificados.
---

# Fabric CLI (fab) – somente leitura

O `fab` é instalado pelo `uv sync` (versão fixa no `pyproject.toml`). Sempre execute
via `uv run fab ...`, um comando por vez (modo script, nunca o modo interativo).

## Regras
- Somente leitura e sem cópias. O hook de guarda bloqueia `rm`, `mv`, `cp`, `export`,
  `import`, `mkdir`, `set`, `run`, `job`, `table load/optimize/vacuum`, `config set`,
  qualquer `-o/--output` e `fab api` com método diferente de GET.
- Somente o workspace de `projeto/projeto.yaml` (`workspace_alvo` e, se autorizados,
  `workspaces_leitura_extra`). Não tente outros workspaces.
- Caminhos no padrão `Workspace.Workspace/Item.Tipo`, entre aspas quando houver espaços:
  `"Meu WS.Workspace/lakehouse_x.Lakehouse"`.
- Não invente flags: `uv run fab <comando> --help` ou MCP `microsoft-learn`.
- Nunca imprima tokens (`fab auth status` já mascara).

## Comandos úteis
| Objetivo | Comando |
|---|---|
| Sessão | `uv run fab auth status` |
| Login (o USUÁRIO executa) | `uv run fab auth login` |
| Existe? | `uv run fab exists "<ws>.Workspace"` |
| Itens do workspace | `uv run fab ls "<ws>.Workspace" -l` |
| Propriedade específica | `uv run fab get "<ws>.Workspace" -q id` |
| Tabelas de um Lakehouse | `uv run fab ls "<ws>.Workspace/<lh>.Lakehouse/Tables"` (com schemas: `.../Tables/<schema>`) |
| Schema de tabela | `uv run fab table schema "<ws>.Workspace/<lh>.Lakehouse/Tables/<schema>/<tabela>"` |
| Arquivos (Files) | `uv run fab ls "<ws>.Workspace/<lh>.Lakehouse/Files" -l` |
| API REST (GET) | `uv run fab api "workspaces/<id>/items"` |
| Capacidades visíveis | `uv run fab ls .capacities -l` |

Para levantar o workspace use a skill `fabric-inventario` (`scripts/inventario.py` e
`scripts/ler_item.py`). Nunca copie itens ou arquivos do workspace: `fab export`, `fab cp`,
`fab get -o` e redirecionar leituras para arquivo são bloqueados pela guarda.

## Problemas comuns
| Sintoma | Causa provável | Ação |
|---|---|---|
| `CERTIFICATE_VERIFY_FAILED` / `SSLError` | Antivírus ou proxy com inspeção HTTPS (ex.: Avast Web Shield) | O `pip-system-certs` do projeto costuma resolver. Se persistir: exceção no antivírus para `login.microsoftonline.com`, `api.fabric.microsoft.com` e `*.dfs.fabric.microsoft.com` |
| `Logged In: False` | Sem login | Usuário roda `uv run fab auth login` |
| `NotFound` em workspace | Nome errado ou sem acesso | `uv run fab ls` e confirmar com o usuário |
| MCP `microsoft-learn` não conecta | Mesma inspeção HTTPS | Exceção no antivírus para `learn.microsoft.com`, depois `/mcp` |
| Capacidade não aparece em `.capacities` | Conta sem papel na capacidade | Consumo de CU não é acessível pelo `fab`; ver README |
