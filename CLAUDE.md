# CLAUDE.md — fabric-ai-doc-helper

Repositório neutro para gerar a **documentação técnica de arquiteturas Microsoft Fabric**
de um cliente, lendo o workspace com o Fabric CLI (`fab`) em modo **somente leitura**.
Nenhuma informação de cliente é versionada: tudo do projeto fica em `projeto/` (ignorado pelo Git).

## Primeiros passos de toda conversa
1. **Conta do Fabric:** `uv run python scripts/verificar_login.py`. A máquina pode estar logada
   em outro cliente. Se não retornar `OK`, mostre a conta ativa e confirme com o usuário; se não
   for a correta, rode `uv run fab auth logout` e peça que ele rode `uv run fab auth login`
   (detalhes na skill `iniciar-projeto`, Passo 1). Não acesse o Fabric antes disso.
2. Se `projeto/projeto.yaml` **não existe**: rode a skill `iniciar-projeto` (entrevista).
   Se existe: confirme em uma linha ("Continuando: <cliente> · <projeto> · workspace <alvo> ·
   conta <conta>. Algo mudou?"). Não entreviste de novo.
3. Se existir `projeto/analise/notas.md`, leia-o antes de ir ao Fabric: ele guarda o que já foi
   analisado. Pedidos de texto/estrutura não precisam de novo acesso ao workspace.

## Fluxo de trabalho
| Etapa | Skill | Resultado |
|---|---|---|
| Entrevista | `iniciar-projeto` | `projeto/projeto.yaml` e pastas |
| Inventário e leitura | `fabric-inventario` | `projeto/inventario/<data>.json` + leitura de itens na tela |
| Análise | `fabric-analise` | caderno `projeto/analise/notas.md` + pontos de atenção |
| Documento | `fabric-documentacao` | `projeto/docs/*.yaml` → `*.docx`; após revisão humana, edição do revisado |
| Comandos avulsos | `fabric-cli` | consultas de leitura pontuais |

## Regras invioláveis
- **Somente leitura no Fabric.** Apenas `ls`, `get`, `exists`, `table schema`, `api` (GET)
  e os scripts `inventario.py`/`ler_item.py`. Nada de `rm`, `mv`, `import`, `run`, `set`, `mkdir`.
- **Nenhuma cópia do workspace.** Não use `fab export`, `fab cp`, `fab get -o` nem redirecione
  leituras de itens para arquivo. Definições são lidas na tela (`scripts/ler_item.py`) e só o
  necessário para o documento.
- **Somente o workspace do projeto** (`workspace_alvo` e, se autorizados,
  `workspaces_leitura_extra` do projeto.yaml).
- **Somente a pasta do repositório.** Não leia nem grave fora dela (exceto a pasta temporária
  do Claude). O hook `.claude/hooks/guard.py` bloqueia violações; se algo for bloqueado,
  não tente contornar: explique ao usuário e peça que ele faça a ação manualmente.
- **Login é manual.** Nunca rode `fab auth login` pelo usuário nem peça senhas/tokens;
  peça que ele execute `uv run fab auth login`.
- **Segredos:** nunca exiba, grave ou copie credenciais, tokens ou senhas encontrados.
- **Template fixo:** visual de `templates/template-bluer.docx` e estrutura de
  `templates/estrutura-documento.yaml`. Não altere o template nem a ordem das seções.
- **Nunca sobrescreva documentos gerados**; nova versão = novo arquivo.
- **Documento revisado pelo usuário é a fonte da verdade:** alterações são aplicadas nele
  (`scripts/editar_docx.py`), nunca regeneradas do zero.
- **Arquivos do assistente são somente leitura** (CLAUDE.md, README, `.claude/`, `scripts/`,
  `templates/`, dependências) e também os originais em `projeto/referencias/`. A guarda bloqueia
  alterações; o usuário libera temporariamente criando manualmente `.claude/MANUTENCAO`.
  Nunca crie esse arquivo nem tente contornar a trava; se precisar, peça ao usuário.
- Foco: o documento Word. Não crie artefatos, relatórios ou arquivos que não sirvam ao documento.
- Mudanças no próprio repositório (skills, scripts, template): só em modo manutenção;
  liste o impacto e aguarde confirmação.

## Referências opcionais
O usuário pode colocar arquivos em `projeto/referencias/` (levantamento de requisitos,
planilha de mapeamento de tabelas, atas, etc.). São **opcionais**:
- com eles, as seções de escopo e mapeamento ficam completas;
- sem eles, o documento é gerado a partir do inventário e da leitura dos itens, com lacunas marcadas `{{...}}`.
Pergunte o papel de cada arquivo novo e registre em `projeto.yaml → referencias`.

## Ambiente
- Python e dependências via `uv` (`uv sync`); sempre `uv run fab ...` / `uv run python ...`.
- Dúvidas de produto Fabric/Power BI: consulte o MCP `microsoft-learn` antes de responder de memória.
- Responda em **português (pt-BR)**, de forma objetiva, com comandos prontos para copiar.
