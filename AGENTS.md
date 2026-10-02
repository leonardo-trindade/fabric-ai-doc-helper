# AGENTS.md — fabric-ai-doc-helper

Repositório neutro para gerar a **documentação técnica de arquiteturas Microsoft Fabric**
de um cliente, lendo o workspace com o Fabric CLI (`fab`) em modo **somente leitura**.
Nenhuma informação de cliente é versionada: tudo do projeto fica em `projeto/` (ignorado pelo Git).

Este arquivo vale para qualquer assistente (Claude Code, Codex, Copilot, Cursor, Gemini…).
Instruções específicas de uma ferramenta ficam no arquivo dela (ex.: `CLAUDE.md`).

## Primeiros passos de toda conversa
1. **Conta do Fabric:** `uv run python scripts/verificar_login.py`. A máquina pode estar logada
   em outro cliente. Se não retornar `OK`, mostre a conta ativa e confirme com o usuário; se não
   for a correta, rode `uv run python scripts/fab_ro.py auth logout` e peça que ele rode
   `uv run fab auth login` (detalhes na skill `iniciar-projeto`, Passo 1). Não acesse o Fabric antes disso.
2. Se `projeto/projeto.yaml` **não existe**: rode a skill `iniciar-projeto` (entrevista).
   Se existe: confirme em uma linha ("Continuando: <cliente> · <projeto> · workspace <alvo> ·
   conta <conta>. Algo mudou?"). Não entreviste de novo.
3. Se existir `projeto/analise/notas.md`, leia-o antes de ir ao Fabric: ele guarda o que já foi
   analisado. Pedidos de texto/estrutura não precisam de novo acesso ao workspace.

## Skills
As skills ficam em **`.agents/skills/<nome>/SKILL.md`** (formato aberto Agent Skills: frontmatter
`name`/`description` + instruções). Se a sua ferramenta não as carrega automaticamente, leia o
`SKILL.md` correspondente antes de executar a etapa. `.claude/skills/` é cópia gerada; não edite.

| Etapa | Skill | Resultado |
|---|---|---|
| Entrevista | `iniciar-projeto` | `projeto/projeto.yaml` e pastas |
| Inventário e leitura | `fabric-inventario` | `projeto/inventario/<data>.json` + leitura de itens na tela |
| Análise | `fabric-analise` | caderno `projeto/analise/notas.md` + pontos de atenção |
| Documento | `fabric-documentacao` | `projeto/docs/*.yaml` → `*.docx`; após revisão humana, edição do revisado |
| Comandos avulsos | `fabric-cli` | consultas de leitura pontuais |

## Regras invioláveis
- **Somente leitura no Fabric.** Use o `fab` sempre via `uv run python scripts/fab_ro.py ...`
  (aplica as regras abaixo e confere a conta) e os scripts `inventario.py`/`ler_item.py`.
  Apenas `ls`, `get`, `exists`, `table schema`, `api` (GET). Nada de `rm`, `mv`, `import`, `run`, `set`, `mkdir`.
- **Nenhuma cópia do workspace.** Não use `fab export`, `fab cp`, `fab get -o` nem redirecione
  leituras de itens para arquivo. Definições são lidas na tela (`scripts/ler_item.py`) e só o
  necessário para o documento.
- **Somente o workspace do projeto** (`workspace_alvo` e, se autorizados,
  `workspaces_leitura_extra` do projeto.yaml).
- **Somente a pasta do repositório.** Não leia nem grave fora dela (exceto a área temporária
  da própria ferramenta). Não leia `~/.config/fab`, `~/.ssh`, `~/.azure` nem `.env`.
- **Login é manual.** Nunca rode `fab auth login` pelo usuário nem peça senhas/tokens;
  peça que ele execute `uv run fab auth login`.
- **Segredos:** nunca exiba, grave ou copie credenciais, tokens ou senhas encontrados.
- **Template fixo:** visual de `templates/template-bluer.docx` e estrutura de
  `templates/estrutura-documento.yaml`. Não altere o template nem a ordem das seções.
- **Nunca sobrescreva documentos gerados**; nova versão = novo arquivo.
- **Documento revisado pelo usuário é a fonte da verdade:** alterações são aplicadas nele
  (`scripts/editar_docx.py`), nunca regeneradas do zero.
- **Arquivos do assistente são somente leitura** (AGENTS.md, CLAUDE.md, README, `.agents/`,
  `.claude/`, `scripts/`, `templates/`, dependências) e também os originais em `projeto/referencias/`.
  O usuário libera temporariamente criando manualmente `.agents/MANUTENCAO`.
  Nunca crie, altere ou apague esse arquivo nem tente contornar a trava; se precisar, peça ao usuário.
- Foco: o documento Word. Não crie artefatos, relatórios ou arquivos que não sirvam ao documento.
- Mudanças no próprio repositório (skills, scripts, template): só em modo manutenção;
  liste o impacto e aguarde confirmação. Skills são editadas em `.agents/skills/` e depois
  copiadas com `uv run python scripts/sincronizar_skills.py`.

## Guarda
As regras acima são aplicadas por `scripts/guarda.py` em duas camadas:
1. **Em qualquer ferramenta:** `scripts/fab_ro.py` e os scripts do projeto validam todo comando `fab`.
2. **Nas ferramentas com adaptador** (`scripts/adaptadores/`; hoje: Claude Code): a guarda também
   intercepta leitura/escrita de arquivos e comandos de terminal antes da execução.

Se algo for bloqueado, não tente contornar: explique ao usuário e peça que ele faça a ação
manualmente. Sem adaptador, as regras valem do mesmo jeito: siga-as por conta própria.

## Referências opcionais
O usuário pode colocar arquivos em `projeto/referencias/` (levantamento de requisitos,
planilha de mapeamento de tabelas, atas, etc.). São **opcionais**:
- com eles, as seções de escopo e mapeamento ficam completas;
- sem eles, o documento é gerado a partir do inventário e da leitura dos itens, com lacunas marcadas `{{...}}`.
Pergunte o papel de cada arquivo novo e registre em `projeto.yaml → referencias`.

## Ambiente
- Python e dependências via `uv` (`uv sync`); sempre `uv run python ...` (o `fab` via `scripts/fab_ro.py`).
- Dúvidas de produto Fabric/Power BI: consulte o MCP `microsoft-learn`
  (`https://learn.microsoft.com/api/mcp`) antes de responder de memória. Se a ferramenta não
  tiver o MCP, diga isso ao usuário e indique o que precisa ser confirmado na documentação.
- Responda em **português (pt-BR)**, de forma objetiva, com comandos prontos para copiar.
