---
name: iniciar-projeto
description: Entrevista inicial do projeto de documentação e verificação da conta logada no Fabric. Use quando projeto/projeto.yaml não existir, quando o usuário pedir para iniciar/reconfigurar o projeto, ou quando informações do cliente (nome, projeto, workspace, conta) mudarem. Cria projeto/projeto.yaml e a estrutura de pastas.
---

# Iniciar projeto (login + entrevista)

Tudo que é específico do cliente é coletado aqui e salvo em `projeto/projeto.yaml`. O usuário
nunca precisa editar esse arquivo à mão.

## Passo 1 — Conta do Fabric (SEMPRE antes de qualquer acesso ao Fabric)
O login do `fab` é um só para o usuário do Windows (não é por pasta): entre uma conversa e outra
o usuário pode ter entrado na conta de outro cliente. Por isso a conta é registrada no projeto e
conferida em toda conversa (hook de início, quando houver) e em todo acesso ao Fabric (scripts).
Se o hook de início já trouxe o resultado, use-o; senão rode:
```
uv run python scripts/verificar_login.py
```
| Saída | O que fazer |
|---|---|
| `OK` (código 0) | Informe a conta em uma linha e siga. |
| Projeto sem conta registrada (código 5) | Mostre conta e tenant e **pergunte**: "Esta é a conta do cliente <cliente>?" |
| `CONTA DIFERENTE` (código 4) | Mostre as duas contas e **peça permissão** para sair da conta atual e entrar na do projeto. |
| `SEM LOGIN` (código 3) | Avise que a janela de login da Microsoft vai abrir e rode `uv run python scripts/entrar.py`. |

- **Confirmou a conta (código 5):** `uv run python scripts/verificar_login.py --registrar`
  (grava `conta_fabric` e `tenant_id`; se o projeto.yaml ainda não existe, registre logo após
  criá-lo no Passo 2). Dali em diante essa é a conta do projeto.
- **Não é a conta certa / conta diferente:** use a ferramenta de perguntas para pedir permissão
  ("Posso sair da conta X e abrir o login para você entrar com a conta do projeto?").
  Só com "sim":
  - código 4 (projeto já tem conta): `uv run python scripts/entrar.py --trocar`
    (o login já abre no tenant registrado);
  - código 5 (definindo a conta agora): `uv run python scripts/entrar.py --trocar --outro-tenant`,
    confirme a nova conta com o usuário e registre com `--registrar`.
  Com "não": não acesse o Fabric; explique que o projeto fica parado até a conta certa.
- `entrar.py` abre o login pelo navegador já na opção "Interactive with a web browser" e fica
  aguardando até o usuário concluir (use tempo limite de vários minutos). No fim mostra a
  conferência da conta (mesmos códigos acima).
- Usuário quer **mudar a conta do projeto** de propósito: com permissão,
  `entrar.py --trocar --outro-tenant` e depois `verificar_login.py --registrar`.
- Nunca rode `fab auth login`/`logout` direto, nunca faça logout sem permissão explícita e
  nunca peça senha/token.

## Passo 2 — Entrevista (projeto novo ou criado pelo app)
Use a ferramenta de perguntas quando disponível; senão, um único bloco numerado em texto.
Não invente respostas.

**Obrigatórias:** 1) nome do cliente · 2) nome do projeto/fase · 3) autor do documento ·
4) workspace a documentar (escolhido na lista, abaixo).

**Workspace (sempre escolhido pelo usuário, numa lista; nunca digitado nem deduzido):**
o nome não indica o ambiente (dev, prod…) e cada cliente nomeia do seu jeito; quem decide qual
documentar é o usuário. Com a conta já registrada (Passo 1):
1. `uv run python scripts/escolher_workspace.py --listar` (lista nomes da conta do projeto).
2. Peça a escolha: até 4 workspaces, como opções da ferramenta de perguntas; mais que isso, mostre
   a lista numerada e peça o número (ofereça `--filtro <texto>` se a lista for longa).
3. Grave: `uv run python scripts/escolher_workspace.py --definir <nº>` (nome exato + ID).
Um projeto documenta um único workspace. Se o usuário quiser documentar outro, oriente criar um
novo projeto no app. Não liste o conteúdo de nenhum workspace antes da escolha.

**Opcionais** (aceite "pular"): 5) participantes e papéis · 6) workspace de comparação, ex.: legado
(escolhido na mesma lista; pergunte se o assistente pode LÊ-lo e só grave com "sim" explícito:
`escolher_workspace.py --extra <nº>`) · 7) itens do escopo, se não houver levantamento
· 8) renomeações de nomenclatura · 9) classificação (padrão RESTRITO).

Referências opcionais: liste `projeto/referencias/`; para cada arquivo pergunte o papel
(levantamento | mapeamento | outro) e, em planilhas, quais abas considerar. Pasta vazia:
informe que são opcionais e siga.

**Projeto criado pelo app** (projeto.yaml com cliente/projeto/autor preenchidos, sem conta e sem
workspace): não repita essas perguntas. Faça o Passo 1 (registrar a conta), a escolha do
workspace e ofereça as opcionais em uma única pergunta (aceite "pular").

Se projeto.yaml JÁ existe com conta e workspace: não entreviste. Leia-o, faça o Passo 1 e
confirme em uma linha ("Continuando: <cliente> · <projeto> · workspace <alvo> · conta <conta>. Algo mudou?").
Se um comando disser que o workspace não foi encontrado, rode `escolher_workspace.py --conferir`:
`RENOMEADO` → confirme com o usuário e rode `--renomeado`; `NÃO ENCONTRADO` → pare e pergunte ao
usuário (acesso removido, workspace apagado ou conta errada).

**Outro cliente na mesma pasta:** se pedirem para iniciar um cliente diferente do registrado,
recuse: cada pasta é de um único projeto. Oriente criar um novo projeto no app Fabric Doc Helper.

## Estrutura criada
```
projeto/
  projeto.yaml
  referencias/     arquivos opcionais do usuário (somente leitura para o assistente)
  inventario/      metadados gerados por scripts/inventario.py
  analise/         notas.md — caderno de análise (skill fabric-analise)
  docs/            especificações .yaml, documentos .docx e alteracoes_*.yaml
  docs/revisado/   versões revisadas pelo usuário (fonte da verdade após revisão)
  planos/          planos do modo de planejamento do Claude Code
```

## Formato do projeto/projeto.yaml
Mantenha EXATAMENTE estas chaves. `workspace_alvo` e `workspaces_leitura_extra`
(lista em uma linha, entre colchetes) são lidos pela guarda (`scripts/guarda.py`).
```yaml
# Gerado pela entrevista (iniciar-projeto). Não versionar.
cliente: "<nome>"
projeto: "<nome do projeto>"
fase: "<fase ou vazio>"
autor: "<autor>"
classificacao: "RESTRITO"
workspace_alvo: "<gravado por escolher_workspace.py --definir>"
workspace_id: "<gravado por escolher_workspace.py --definir>"
workspaces_leitura_extra: []
workspace_legado: ""
conta_fabric: "<registrado por verificar_login.py --registrar>"
tenant_id: "<registrado por verificar_login.py --registrar>"
participantes:
  - {papel: "<papel>", nome: "<nome>"}
escopo:
  itens: []
nomenclatura: []            # - {antigo: "...", novo: "...", aplica_em: "tabelas"}
referencias: []             # - {arquivo: "referencias/x.xlsx", tipo: "mapeamento", abas: ["Tabelas"], uso: "..."}
decisoes: []                # decisões do usuário (o que documentar ou não)
```

## Ao final
- Resumo curto do que foi salvo (sem tokens) e próximo passo: skill `fabric-inventario`.
- Decisões de escopo tomadas depois (ex.: "não documentar X", "aba Y é interna") vão para
  `decisoes`, sem perguntar de novo.
