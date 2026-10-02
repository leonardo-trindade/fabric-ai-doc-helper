---
name: fabric-inventario
description: Levanta o inventário (somente metadados) do workspace alvo e lê definições de notebooks, pipelines e environments sob demanda, sem copiar nenhum arquivo do workspace. Use antes de analisar ou documentar a arquitetura.
---

# Inventário e leitura do workspace (sem cópias)

Regra central: **nada do workspace é copiado para a máquina.** Não use `fab export`,
`fab cp` nem `fab get -o`; não redirecione leituras para arquivo (`>`, `tee`, `Out-File`).
A guarda (`scripts/guarda.py`) bloqueia essas ações.

## Pré-requisitos
1. `projeto/projeto.yaml` existe (senão: skill `iniciar-projeto`).
2. Conta correta: `uv run python scripts/verificar_login.py` deve retornar `OK`. Qualquer
   outro resultado: siga o Passo 1 da skill `iniciar-projeto` (confirmar com o usuário,
   logout/login se necessário). Os scripts também param sozinhos se a conta não conferir.

## 1. Inventário (metadados)
```
uv run python scripts/inventario.py --colunas ouro
```
- Grava `projeto/inventario/<data_hora>.json` só com nomes, tipos, IDs, pastas, tabelas por
  schema, nomes de arquivos em Files e, para os schemas de `--colunas`, as colunas e tipos.
- Use `--colunas` apenas nos schemas que irão para o dicionário de dados (normalmente a camada
  de consumo, ex.: `ouro`/`gold`). Cada tabela custa uma chamada; não peça todos os schemas.
- Confere o tenant do login com `tenant_id` do projeto.yaml (se vazio, preencha após a 1ª execução).

## 2. Leitura de itens (sob demanda, só na tela)
```
uv run python scripts/ler_item.py "mn_pl.DataPipeline" "ou_nb_vendas.Notebook"
uv run python scripts/ler_item.py --tipo DataPipeline
uv run python scripts/ler_item.py --tipo Notebook
uv run python scripts/ler_item.py --tipo Environment
```
- Cada item leva ~20–30 s no Fabric; o script lê até 6 em paralelo.
- Saída resumida: notebooks → células; pipelines → parâmetros e árvore de atividades
  (IDs de pipelines/notebooks já convertidos em nomes, fonte/destino, modo de carga, chaves);
  environments → configuração Spark; agendamentos quando houver. `--bruto` mostra o JSON completo.
- Segredos aparecem como `***MASCARADO***` e geram um aviso: registre como ponto de atenção
  ("credenciais em texto no código de <item>"), sem reproduzir valores.
- Leia só o necessário para o documento; não repita leituras já feitas na conversa.
- Arquivos de configuração em Files: o inventário traz os nomes. O conteúdo não é baixado;
  deduza o papel pelo uso nos pipelines (ex.: atividade Lookup) ou pergunte ao usuário.

## Depois
Informe ao usuário os números (itens por tipo, tabelas por schema, segredos mascarados) e
siga para a skill `fabric-analise`, registrando o que for entendido no caderno de análise
(`projeto/analise/notas.md`) para não precisar reler itens em conversas futuras.
