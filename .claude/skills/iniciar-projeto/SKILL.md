---
name: iniciar-projeto
description: Entrevista inicial do projeto de documentação e verificação da conta logada no Fabric. Use quando projeto/projeto.yaml não existir, quando o usuário pedir para iniciar/reconfigurar o projeto, ou quando informações do cliente (nome, projeto, workspace, conta) mudarem. Cria projeto/projeto.yaml e a estrutura de pastas.
---

# Iniciar projeto (login + entrevista)

O repositório é neutro: nada de cliente fica versionado. Tudo que é específico do projeto é
coletado aqui e salvo em `projeto/projeto.yaml` (pasta ignorada pelo Git). O usuário nunca
precisa editar esse arquivo à mão.

## Passo 1 — Conta do Fabric (SEMPRE antes de qualquer acesso ao Fabric)
O login do `fab` é por usuário do Windows, não por pasta: a máquina pode estar logada no
cliente anterior. Rode:
```
uv run python scripts/verificar_login.py
```
| Saída | O que fazer |
|---|---|
| `SEM LOGIN` (código 3) | Peça ao usuário para rodar **no terminal dele**: `uv run fab auth login`. Aguarde e verifique de novo. |
| Mostra uma conta, projeto sem conta registrada (código 5) | Mostre conta e tenant e **pergunte**: "Esta é a conta do cliente <cliente>?" |
| `CONTA DIFERENTE` (código 4) | Mostre as duas contas e **pergunte** qual é a correta. |
| `OK` (código 0) | Informe a conta em uma linha e siga. |

- Usuário confirmou a conta: `uv run python scripts/verificar_login.py --registrar`
  (grava `conta_fabric` e `tenant_id` no projeto.yaml; se o projeto.yaml ainda não existe,
  registre logo após criá-lo no Passo 2).
- Usuário disse que NÃO é a conta certa: rode `uv run fab auth logout`, peça que ele rode
  `uv run fab auth login` com a conta do cliente, aguarde a confirmação, verifique de novo e
  então registre.
- Nunca rode `fab auth login` você mesmo (a guarda bloqueia) e nunca peça senha/token.

## Passo 2 — Entrevista (só se projeto/projeto.yaml não existir)
Use a ferramenta de perguntas quando disponível; senão, um único bloco numerado em texto.
Não invente respostas.

**Obrigatórias:** 1) nome do cliente · 2) nome do projeto/fase · 3) workspace alvo do Fabric
(somente leitura) · 4) autor do documento.

**Opcionais** (aceite "pular"): 5) participantes e papéis · 6) workspace legado (comparativo;
pergunte se o Claude pode LÊ-lo — só entra em `workspaces_leitura_extra` com "sim" explícito)
· 7) itens do escopo, se não houver levantamento · 8) renomeações de nomenclatura
· 9) classificação (padrão RESTRITO).

Verificações:
- Workspace: `uv run fab exists "<workspace>.Workspace"`. Se `false`, mostre `uv run fab ls`
  e peça o nome correto. Não liste o conteúdo de outros workspaces.
- Referências opcionais: liste `projeto/referencias/`; para cada arquivo pergunte o papel
  (levantamento | mapeamento | outro) e, em planilhas, quais abas considerar. Pasta vazia:
  informe que são opcionais e siga.

Se projeto.yaml JÁ existe: não entreviste. Leia-o, faça o Passo 1 e confirme em uma linha
("Continuando: <cliente> · <projeto> · workspace <alvo> · conta <conta>. Algo mudou?").

## Estrutura criada
```
projeto/
  projeto.yaml
  referencias/     arquivos opcionais do usuário (somente leitura para o Claude)
  inventario/      metadados gerados por scripts/inventario.py
  analise/         notas.md — caderno de análise (skill fabric-analise)
  docs/            especificações .yaml, documentos .docx e alteracoes_*.yaml
  docs/revisado/   versões revisadas pelo usuário (fonte da verdade após revisão)
```

## Formato do projeto/projeto.yaml
Mantenha EXATAMENTE estas chaves. `workspace_alvo` e `workspaces_leitura_extra`
(lista em uma linha, entre colchetes) são lidos pelo hook de guarda.
```yaml
# Gerado pela entrevista (iniciar-projeto). Não versionar.
cliente: "<nome>"
projeto: "<nome do projeto>"
fase: "<fase ou vazio>"
autor: "<autor>"
classificacao: "RESTRITO"
workspace_alvo: "<workspace>"
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
